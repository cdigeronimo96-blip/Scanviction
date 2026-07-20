"""Scanviction — app.py's key->document storage seam (extracted from app.py).

All of app.py's persistence routes through _read_json / _write_json, keyed by a
"path" string. When DATABASE_URL is set AND a psycopg driver is importable, each
logical "file" becomes one row in kv_store(key TEXT PK, value JSONB); otherwise we
use JSON files. With STORAGE_DUAL_WRITE=1 we also mirror to the file during cutover.
Writes are atomic (temp file + os.replace). Dropped connections (idle timeouts on
hosted Postgres / poolers) are detected and reconnected.

This is a PURE module — no Streamlit, no app state — so it is independently
importable and unit-testable. It is intentionally a near-twin of msp_store.py (the
worker/shared layer) but keeps app.py's exact semantics: DB-first reads, indent=2,
and dual-write gated on STORAGE_DUAL_WRITE. app.py imports _read_json / _write_json /
_db_read / _db_write / storage_backend / DATABASE_URL / STORAGE_DUAL_WRITE from here.
"""
import os as _os
import json as _json
import secrets as _secrets
import threading as _db_threading

DATABASE_URL       = _os.environ.get("DATABASE_URL", "").strip()
STORAGE_DUAL_WRITE = _os.environ.get("STORAGE_DUAL_WRITE", "0") == "1"

_DB_CONN = None
_DB_OK = False
_DB_INIT_TRIED = False
_DB_LOCK = _db_threading.Lock()


def _db_connect():
    """Lazily connect to Postgres and ensure the kv_store table exists.
    Tries psycopg (v3) then psycopg2. Returns a live connection or None.
    Any failure disables the DB path and falls back to JSON files."""
    global _DB_CONN, _DB_OK, _DB_INIT_TRIED
    if _DB_INIT_TRIED:
        return _DB_CONN if _DB_OK else None
    _DB_INIT_TRIED = True
    if not DATABASE_URL:
        return None
    conn = None
    try:
        try:
            import psycopg  # psycopg v3
            conn = psycopg.connect(DATABASE_URL, autocommit=True)
        except Exception:
            import psycopg2  # psycopg v2
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS kv_store ("
                        "key TEXT PRIMARY KEY, value JSONB NOT NULL, "
                        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        _DB_CONN = conn; _DB_OK = True
        return conn
    except Exception:
        _DB_OK = False
        return None


def _db_reset():
    """Drop the cached connection so the next call reconnects. Used when a
    read/write hits a dead connection (idle timeouts are common on hosted
    Postgres / connection poolers like Supabase & Neon)."""
    global _DB_CONN, _DB_OK, _DB_INIT_TRIED
    try:
        if _DB_CONN: _DB_CONN.close()
    except Exception:
        pass
    _DB_CONN = None; _DB_OK = False; _DB_INIT_TRIED = False


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
    # Connection likely dropped (idle timeout) — reconnect once and retry.
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


def _read_json(path, default=None):
    # DB-first when available; fall back to the JSON file.
    val, found = _db_read(path)
    if found and val is not None:
        return val
    try:
        with open(path) as f: return _json.load(f)
    except: return default if default is not None else {}


def _write_json(path, data):
    wrote_db = _db_write(path, data)
    # Always write the file when there's no DB, or when dual-write is on, or if the DB
    # write failed (so we never silently lose data). Write ATOMICALLY (temp file +
    # os.replace) so a crash or an interleaved writer can't leave a truncated, half-written
    # file that the next read silently treats as empty.
    if (not wrote_db) or STORAGE_DUAL_WRITE:
        tmp = f"{path}.tmp.{_os.getpid()}.{_secrets.token_hex(4)}"
        try:
            with open(tmp, "w") as f:
                _json.dump(data, f, indent=2, default=str)
                f.flush()
                try: _os.fsync(f.fileno())
                except Exception: pass
            _os.replace(tmp, path)   # atomic on the same filesystem
        except Exception:
            try: _os.remove(tmp)
            except Exception: pass
