"""Durable funnel analytics — Postgres-backed so events survive Streamlit Cloud reboots.

The app's track_event() writes each funnel event here (INSERT into an append-only msp_events table)
when DATABASE_URL is set, in addition to the local events.jsonl (which stays as the no-DB fallback).
read_funnel reads aggregates back for the admin funnel view.

Reuses kvstore's Postgres connection (same pool + lock, so it serializes with the kv writes and
inherits its reconnect-on-idle-timeout handling). PURE module — no Streamlit — so it's unit-testable,
and it degrades gracefully to no-ops when there's no database (record→False, counts→None, recent→[]).
"""
import json as _json
import threading as _threading

try:                                   # share kvstore's connection + lock (one DB, one pool)
    from kvstore import _db_connect, _db_reset, _DB_LOCK
except Exception:                      # pragma: no cover - kvstore always importable in-app
    def _db_connect():
        return None
    def _db_reset():
        pass
    _DB_LOCK = _threading.Lock()

_TABLE_READY = False


def _ensure_table_locked(conn):
    """Create the events table + index once. CALLER MUST HOLD _DB_LOCK (we never nest the lock,
    since it's a plain Lock, not an RLock — nesting would deadlock)."""
    global _TABLE_READY
    if _TABLE_READY:
        return
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS msp_events ("
                    "id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT now(), "
                    "event TEXT NOT NULL, uid TEXT, props JSONB)")
        cur.execute("CREATE INDEX IF NOT EXISTS msp_events_event_idx ON msp_events (event)")
    _TABLE_READY = True


def _with_conn(fn):
    """Run fn(conn) under the shared lock, reconnecting once if the connection dropped
    (idle timeouts are common on Neon). Returns fn's result, or a sentinel on total failure."""
    conn = _db_connect()
    if not conn:
        return None, False
    try:
        return fn(conn), True
    except Exception:
        pass
    _db_reset()
    conn = _db_connect()
    if not conn:
        return None, False
    try:
        return fn(conn), True
    except Exception:
        return None, False


def record_event(event, uid=None, props=None):
    """Append one event to Postgres. Returns True if durably written, False if no DB / on failure
    (the caller keeps events.jsonl as the fallback so nothing is silently lost)."""
    payload = _json.dumps(props or {}, default=str)

    def _do(conn):
        with _DB_LOCK:
            _ensure_table_locked(conn)
            with conn.cursor() as cur:
                cur.execute("INSERT INTO msp_events(event, uid, props) VALUES (%s, %s, %s)",
                            (str(event)[:64], (uid or None), payload))
        return True

    res, ok = _with_conn(_do)
    return bool(ok and res)


def funnel_counts():
    """{event: {"n": total, "u": unique_uids}} from Postgres, or None if the DB isn't available
    (so the caller can fall back to the JSONL). An empty dict means the DB is up but has no events."""
    def _do(conn):
        with _DB_LOCK:
            _ensure_table_locked(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT event, COUNT(*), COUNT(DISTINCT uid) FROM msp_events GROUP BY event")
                rows = cur.fetchall()
        return {r[0]: {"n": int(r[1]), "u": int(r[2] or 0)} for r in rows}

    res, ok = _with_conn(_do)
    return res if ok else None


def recent_events(limit=40):
    """The most recent events (newest first) as [{ts, event, **props}], or [] if no DB."""
    def _do(conn):
        with _DB_LOCK:
            _ensure_table_locked(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT to_char(ts, 'YYYY-MM-DD\"T\"HH24:MI:SS'), event, props "
                            "FROM msp_events ORDER BY id DESC LIMIT %s", (int(limit),))
                rows = cur.fetchall()
        out = []
        for ts, ev, props in rows:
            rec = {"ts": ts, "event": ev}
            if isinstance(props, str):
                try:
                    props = _json.loads(props)
                except Exception:
                    props = {}
            if isinstance(props, dict):
                rec.update(props)
            out.append(rec)
        return out

    res, ok = _with_conn(_do)
    return res if ok else []


def enabled():
    """True when a Postgres backend is connected (analytics are durable)."""
    return _db_connect() is not None
