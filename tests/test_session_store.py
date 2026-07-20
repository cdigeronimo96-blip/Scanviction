"""Integration tests for the auth persistence layer in app.py — server-side session
tokens, user persistence (locked, no lost updates), pending-upgrade claim, and the
seed+disk merge. These run the REAL app functions against per-test temp files, and
form the safety net for refactoring the storage/session code out of the monolith.
"""
import threading
import time

import pytest


@pytest.fixture
def store(app, tmp_path, monkeypatch):
    """app with every persistence path redirected to this test's temp dir. The session/
    user functions live in auth_store and resolve THAT module's path globals, so patch
    there (app re-exports the same callables)."""
    import auth_store
    monkeypatch.setattr(auth_store, "USERS_DB_PATH", str(tmp_path / "users.json"))
    monkeypatch.setattr(auth_store, "ALERTS_DB_PATH", str(tmp_path / "alerts.json"))
    monkeypatch.setattr(auth_store, "SESS_DB_PATH", str(tmp_path / "sessions.json"))
    monkeypatch.setenv("PENDING_UPGRADES_PATH", str(tmp_path / "pending.json"))
    return app


# ── server-side session tokens ───────────────────────────────────────────────
def test_session_token_lifecycle(store):
    tok = store.new_session_token("a@b.com", "premium")
    assert isinstance(tok, str) and len(tok) >= 32       # CSPRNG bearer token
    sess = store.lookup_session(tok)
    assert sess and sess["email"] == "a@b.com" and sess["role"] == "premium"
    store.destroy_session_token(tok)
    assert store.lookup_session(tok) is None
    assert store.lookup_session("") is None


def test_session_tokens_are_unique(store):
    toks = {store.new_session_token("a@b.com", "free") for _ in range(20)}
    assert len(toks) == 20


def test_expired_session_not_returned_and_pruned(store):
    past = time.time() - 10
    store._save_sessions({"oldtok": {"email": "x@y.com", "role": "free",
                                     "created": past - 100, "expires": past}})
    assert store.lookup_session("oldtok") is None        # expired -> not returned
    store.new_session_token("z@y.com", "free")           # creating a token prunes expired
    assert "oldtok" not in store._load_sessions()


# ── user persistence (locked, no lost updates) ───────────────────────────────
def test_user_save_load_roundtrip(store):
    store.save_user_to_file("u@x.com", {"role": "premium", "name": "U", "pw": "h", "watchlist": ["AAPL"]})
    db = store.load_all_users_from_file()
    assert db["u@x.com"]["role"] == "premium" and db["u@x.com"]["watchlist"] == ["AAPL"]


def test_concurrent_user_saves_no_lost_update(store):
    """The _STORE_LOCK + fresh-read-merge must let 50 concurrent saves of DIFFERENT
    users all persist (the bug before the lock was last-writer-wins on the whole file)."""
    N = 50
    threads = [threading.Thread(target=store.save_user_to_file, args=(f"u{i}@x.com", {"i": i, "pw": "h"}))
               for i in range(N)]
    for t in threads: t.start()
    for t in threads: t.join()
    db = store.load_all_users_from_file()
    assert len(db) == N
    assert db["u37@x.com"]["i"] == 37


def test_get_global_db_merges_disk_over_seed(store, monkeypatch):
    monkeypatch.setenv("SEED_DEMO_ACCOUNTS", "0")
    store.save_user_to_file("disk@user.com", {"role": "free", "name": "Disk", "pw": "h"})
    db = store._get_global_db()
    assert "disk@user.com" in db and db["disk@user.com"]["name"] == "Disk"


# ── pending Stripe upgrade claimed on next login ─────────────────────────────
def test_pending_upgrade_grant_and_clear(store):
    email = "Buyer@Example.com"
    db = {email: {"role": "free", "plan": "Free", "pw": "h"}}
    assert store.apply_pending_upgrade(email, db) is False     # nothing pending yet
    store.remember_pending_upgrade(email, "Annual")
    assert store.apply_pending_upgrade(email, db) is True       # granted
    assert db[email]["role"] == "premium" and db[email]["plan"] == "Annual"
    assert store.apply_pending_upgrade(email, db) is False      # entry cleared -> idempotent


def test_pending_upgrade_noop_without_account(store):
    store.remember_pending_upgrade("ghost@x.com", "Monthly")
    db = {}                                                     # buyer has no account row
    assert store.apply_pending_upgrade("ghost@x.com", db) is False
    assert db == {}
