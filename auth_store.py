"""Scanviction — account & session persistence (extracted from app.py).

Owns the durable auth state: the shared users DB (seed accounts merged over disk),
per-user alerts, server-side session tokens (random bearer token + expiry, so a hard
refresh / new tab re-establishes login), and pending Stripe upgrades (claimed on the
buyer's next login). One process-wide _STORE_LOCK serializes the read-modify-write of
the users / alerts / sessions files so concurrent Streamlit sessions can't lose an
update.

Reads/writes route through kvstore (Postgres kv_store OR atomic JSON files). The file
paths are msp_store's canonical constants, so the app and the alerts worker share the
same rows/files. Pure of app UI state; imports Streamlit only for the cache_resource
lock and st.secrets (owner/admin seed). The st.session_state-coupled callers
(_toggle_watchlist, login/signup/settings UI) stay in app.py and use these via import.
"""
import os as _os
import time
import secrets as _secrets
from datetime import datetime

import streamlit as st

from kvstore import _read_json, _write_json
from msp_store import USERS_DB_PATH, ALERTS_DB_PATH, SESS_DB_PATH, _data_path
from security import _hp

SESSION_TTL_SECONDS = 30 * 24 * 3600

# Module-level shared users DB cache (rebuilt from seed+disk by _get_global_db).
_GLOBAL_USERS_DB: dict = {}


@st.cache_resource(show_spinner=False)
def _store_lock():
    """Process-wide lock serializing the read-modify-write of the shared JSON stores
    (users / alerts / sessions). Without it, concurrent Streamlit sessions (separate
    threads in ONE process) interleave load+save of the WHOLE file and the slower writer
    clobbers the other's change — a lost update. cache_resource keeps ONE lock across
    reruns/sessions/threads (a plain module global resets every rerun)."""
    import threading as __th
    return __th.Lock()
_STORE_LOCK = _store_lock()


# ── users + alerts ───────────────────────────────────────────────────────────
def save_alerts_to_file(email, alerts):
    with _STORE_LOCK:
        db = _read_json(ALERTS_DB_PATH, {}); db[email] = alerts   # fresh read INSIDE the lock
        _write_json(ALERTS_DB_PATH, db)

def save_user_to_file(email, user_data):
    """Save ALL user data to disk — full record so users persist across reboots. Locked +
    fresh-read so a concurrent save of a DIFFERENT user can't be lost."""
    with _STORE_LOCK:
        db = _read_json(USERS_DB_PATH, {})       # fresh read INSIDE the lock
        db[email] = dict(user_data)              # save EVERYTHING about the user
        _write_json(USERS_DB_PATH, db)

def load_all_users_from_file() -> dict:
    """Read full users database from disk."""
    return _read_json(USERS_DB_PATH, {})


# ── server-side session store (persistent auth across reloads) ───────────────
def _load_sessions() -> dict:
    return _read_json(SESS_DB_PATH, {})

def _save_sessions(d: dict):
    _write_json(SESS_DB_PATH, d)

def _prune_sessions(sessions: dict) -> dict:
    now = time.time()
    return {k: v for k, v in sessions.items() if v.get("expires", 0) > now}

def new_session_token(email: str, role: str) -> str:
    """Create + persist a new session token for this user. Returns the token."""
    tok = _secrets.token_urlsafe(32)   # ~256-bit CSPRNG bearer token (was non-crypto random)
    with _STORE_LOCK:
        sessions = _prune_sessions(_load_sessions())
        sessions[tok] = {"email": email, "role": role, "created": time.time(),
                         "expires": time.time() + SESSION_TTL_SECONDS}
        _save_sessions(sessions)
    return tok

def lookup_session(tok: str):
    """Return the session dict for a token if valid + unexpired, else None."""
    if not tok:
        return None
    sess = _load_sessions().get(tok)
    if sess and sess.get("expires", 0) > time.time():
        return sess
    return None

def destroy_session_token(tok: str):
    if not tok:
        return
    with _STORE_LOCK:
        sessions = _load_sessions()
        if tok in sessions:
            sessions.pop(tok, None)
            _save_sessions(sessions)


# ── pending upgrades ─────────────────────────────────────────────────────────
# A buyer can finish Stripe checkout while logged out (the hosted-page round-trip can
# drop the session). We record the VERIFIED-paid email here and grant premium when that
# account next logs in or signs up — so a paying customer is never left without access.
def _pending_upgrades_path():
    return _data_path("msp_pending_upgrades.json", "PENDING_UPGRADES_PATH")

def remember_pending_upgrade(email, plan):
    if not email:
        return
    try:
        p = _pending_upgrades_path(); d = _read_json(p, {})
        d[email.strip().lower()] = {"plan": plan, "ts": time.time()}
        _write_json(p, d)
    except Exception:
        pass

def apply_pending_upgrade(email, db):
    """If `email` has a paid-but-unclaimed upgrade, grant premium on its db record (in
    place) and clear the pending entry. Returns True if applied."""
    if not email:
        return False
    try:
        p = _pending_upgrades_path(); d = _read_json(p, {})
        key = email.strip().lower()
        rec = d.get(key)
        if rec and email in db:
            db[email]["role"] = "premium"
            db[email]["plan"] = rec.get("plan", "Monthly")
            d.pop(key, None); _write_json(p, d)
            return True
    except Exception:
        pass
    return False


# ── shared users DB (seed accounts merged over disk) ─────────────────────────
def _get_global_db() -> dict:
    """Returns the shared user database — ALWAYS merges disk + seed accounts.
    This ensures users persist across reboots and across browser tabs."""
    global _GLOBAL_USERS_DB
    # Start with the seed accounts (always present)
    seed = _load_seed_accounts()
    # Merge with disk (disk wins for conflicts — that's the live data)
    disk = load_all_users_from_file()
    # Merge: seed first, then overlay disk
    merged = dict(seed)
    for email, user_data in disk.items():
        if email in merged:
            # Merge per-user dicts so we don't lose seed fields
            merged[email] = {**merged[email], **user_data}
        else:
            merged[email] = user_data
    _GLOBAL_USERS_DB = merged
    return _GLOBAL_USERS_DB

def _save_global_db(db: dict):
    """Sync session users_db back to global store AND write to disk for durability."""
    global _GLOBAL_USERS_DB
    _GLOBAL_USERS_DB = db
    # Persist every user to disk (serialized + atomic via _write_json)
    with _STORE_LOCK:
        _write_json(USERS_DB_PATH, db)

def _load_seed_accounts():
    today = datetime.now().strftime("%Y-%m-%d")
    seed = {}
    # Owner/Admin come ONLY from secrets — NEVER ship default privileged credentials.
    # (The old code shipped admin@/owner@ with hardcoded "admin_change_me"/"owner_change_me"
    #  passwords, an account-takeover risk on any default deploy.) Fail closed if unset.
    try:
        try:    accts = st.secrets["accounts"]
        except: accts = st.secrets
        oe = accts.get("owner_email",""); oh = accts.get("owner_pw_hash","")
        ae = accts.get("admin_email",""); ah = accts.get("admin_pw_hash","")
        if oe and oh:
            seed[oe] = {"pw":oh,"name":"Owner","role":"owner","verified":True,"joined":today,"plan":"Annual"}
        if ae and ah:
            seed[ae] = {"pw":ah,"name":"Admin","role":"admin","verified":True,"joined":today,"plan":"Annual"}
    except Exception:
        pass
    # Demo/premium SHOWCASE accounts (known passwords → premium for free) are seeded ONLY
    # when explicitly enabled, so they never exist in production. Set SEED_DEMO_ACCOUNTS=1
    # for local demos/testing.
    if _os.environ.get("SEED_DEMO_ACCOUNTS", "0").strip().lower() in ("1", "true", "yes"):
        seed["demo@scanviction.com"]    = {"pw":_hp("demo123"), "name":"Demo User",  "role":"free",   "verified":True,"joined":today,"plan":"Free"}
        seed["premium@scanviction.com"] = {"pw":_hp("premium1"),"name":"Alex Rivera","role":"premium","verified":True,"joined":today,"plan":"Monthly"}
    return seed
