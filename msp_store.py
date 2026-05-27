"""
MarketSignalPro — shared storage layer
=======================================
ONE implementation of durable key→document storage, imported by BOTH the
Streamlit app (app.py) and the background alerts worker (alerts_worker.py) and
the signal engine (signal_engine.py).

Why this exists: previously the app stored users/alerts in one place
(Postgres via DATABASE_URL, or .msp_data/*.json) while the worker read raw
/tmp/sw_*.json files — so the worker never saw real users and sent no alerts,
and nothing survived a reboot. This module makes all three components read and
write the SAME rows, keyed by the SAME canonical key strings.

Backend: if DATABASE_URL is set AND a psycopg driver is importable, every
logical "file" becomes one row in kv_store(key TEXT PK, value JSONB). Otherwise
we fall back to JSON files under a shared data directory. Dropped connections
(idle timeouts on hosted Postgres / poolers) are detected and reconnected.

The kv_store schema and the key strings here are IDENTICAL to what app.py uses,
so the two are wire-compatible against the same database.
"""
import os as _os
import json as _json
import threading as _threading

# ── Canonical data directory (shared by app + worker) ──────────────────────
# Avoid /tmp by default (wiped on restart). Override with MSP_DATA_DIR.
_DEFAULT_DATA_DIR = _os.environ.get(
    "MSP_DATA_DIR",
    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".msp_data"),
)
try:
    _os.makedirs(_DEFAULT_DATA_DIR, exist_ok=True)
except Exception:
    _DEFAULT_DATA_DIR = "/tmp"


def _data_path(name, env_var):
    return _os.environ.get(env_var, _os.path.join(_DEFAULT_DATA_DIR, name))


# ── Canonical storage keys (MUST match app.py exactly) ─────────────────────
# These strings are used BOTH as filenames (file mode) AND as kv_store keys
# (Postgres mode). The app and worker must agree on them to share data.
USERS_DB_PATH  = _data_path("msp_users.json",  "USERS_DB_PATH")
ALERTS_DB_PATH = _data_path("msp_alerts.json", "ALERTS_DB_PATH")
SESS_DB_PATH   = _data_path("msp_sessions.json", "SESS_DB_PATH")
RECS_DB_PATH   = _data_path("msp_recommendations.json", "RECS_DB_PATH")
# Worker-private state (dedup of fired alerts, previous sentiment) — also shared
# so the Render cron's ephemeral /tmp doesn't lose dedup state between runs.
FIRED_DB_PATH  = _data_path("msp_fired.json", "FIRED_DB_PATH")
PREV_SENT_PATH = _data_path("msp_prev_sentiment.json", "PREV_SENT_PATH")
# Signal engine stores (shared so app + worker see the same signal history)
SIGNAL_HISTORY_PATH = _data_path("msp_signal_history.json", "SIGNAL_HISTORY_PATH")
SIGNAL_PERF_PATH    = _data_path("msp_signal_perf_cache.json", "SIGNAL_PERF_PATH")

DATABASE_URL = _os.environ.get("DATABASE_URL", "").strip()

# ── Postgres connection (lazy, reconnecting) ───────────────────────────────
_DB_CONN = None
_DB_OK = False
_DB_INIT_TRIED = False
_DB_LOCK = _threading.Lock()


def _db_connect():
    """Lazily connect to Postgres and ensure kv_store exists. psycopg v3 then
    v2. Returns a live connection or None (→ file fallback)."""
    global _DB_CONN, _DB_OK, _DB_INIT_TRIED
    if _DB_INIT_TRIED:
        return _DB_CONN if _DB_OK else None
    _DB_INIT_TRIED = True
    if not DATABASE_URL:
        return None
    try:
        try:
            import psycopg  # v3
            conn = psycopg.connect(DATABASE_URL, autocommit=True)
        except Exception:
            import psycopg2  # v2
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS kv_store ("
                        "key TEXT PRIMARY KEY, value JSONB NOT NULL, "
                        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        _DB_CONN = conn
        _DB_OK = True
        return conn
    except Exception:
        _DB_OK = False
        return None


def _db_reset():
    global _DB_CONN, _DB_OK, _DB_INIT_TRIED
    try:
        if _DB_CONN:
            _DB_CONN.close()
    except Exception:
        pass
    _DB_CONN = None
    _DB_OK = False
    _DB_INIT_TRIED = False


def _db_read(key):
    def _try(conn):
        with _DB_LOCK:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM kv_store WHERE key=%s", (key,))
                row = cur.fetchone()
        if row is None:
            return None, True
        val = row[0]
        if isinstance(val, str):
            val = _json.loads(val)
        return val, True
    conn = _db_connect()
    if not conn:
        return None, False
    try:
        return _try(conn)
    except Exception:
        pass
    _db_reset()
    conn = _db_connect()
    if not conn:
        return None, False
    try:
        return _try(conn)
    except Exception:
        return None, False


def _db_write(key, data):
    payload = _json.dumps(data, default=str)
    def _try(conn):
        with _DB_LOCK:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO kv_store(key,value,updated_at) VALUES(%s,%s,now()) "
                    "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now()",
                    (key, payload))
        return True
    conn = _db_connect()
    if not conn:
        return False
    try:
        return _try(conn)
    except Exception:
        pass
    _db_reset()
    conn = _db_connect()
    if not conn:
        return False
    try:
        return _try(conn)
    except Exception:
        return False


def storage_backend():
    """'postgres' if the DB is connected and working, else 'json-file'."""
    return "postgres" if _db_connect() else "json-file"


# ── Public API: read_json / write_json (DB-first, file fallback) ───────────
def read_json(key, default=None):
    val, found = _db_read(key)
    if found and val is not None:
        return val
    try:
        with open(key) as f:
            return _json.load(f)
    except Exception:
        return default if default is not None else {}


def write_json(key, data):
    wrote_db = _db_write(key, data)
    # Always also write the file as a local cache/fallback (best-effort).
    try:
        with open(key, "w") as f:
            _json.dump(data, f, default=str)
    except Exception:
        pass
    return wrote_db
