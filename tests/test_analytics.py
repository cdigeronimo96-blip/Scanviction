"""analytics_store — durable funnel events. Tested with a fake DB connection (no real Postgres)
plus the graceful no-DB path. Pure module, no app import."""
import analytics_store as a


def setup_function(_):
    a._TABLE_READY = False


# ── fake psycopg connection ───────────────────────────────────────────────────
class _FakeCursor:
    def __init__(self, store): self.store = store; self._last = ""
    def __enter__(self): return self
    def __exit__(self, *x): return False
    def execute(self, sql, params=None):
        self.store["sql"].append((sql, params)); self._last = sql
    def fetchall(self):
        if "GROUP BY event" in self._last:
            return [("landing_view", 10, 0), ("signup_verified", 2, 2), ("payment_success", 1, 1)]
        if "ORDER BY id DESC" in self._last:
            return [("2026-07-02T12:00:00", "payment_success", '{"plan":"premium"}')]
        return []


class _FakeConn:
    def __init__(self, store): self.store = store
    def cursor(self): return _FakeCursor(self.store)


# ── with a (fake) database ────────────────────────────────────────────────────
def test_record_event_inserts(monkeypatch):
    store = {"sql": []}
    monkeypatch.setattr(a, "_db_connect", lambda: _FakeConn(store))
    assert a.record_event("payment_success", uid="abc123", props={"plan": "premium"}) is True
    sqls = " ".join(s for s, _ in store["sql"])
    assert "CREATE TABLE IF NOT EXISTS msp_events" in sqls   # table ensured
    assert any("INSERT INTO msp_events" in s for s, _ in store["sql"])
    # the INSERT carries event, uid, and json props
    ins = [p for s, p in store["sql"] if "INSERT" in s][0]
    assert ins[0] == "payment_success" and ins[1] == "abc123" and '"plan": "premium"' in ins[2]


def test_funnel_counts_aggregates(monkeypatch):
    monkeypatch.setattr(a, "_db_connect", lambda: _FakeConn({"sql": []}))
    fc = a.funnel_counts()
    assert fc["landing_view"] == {"n": 10, "u": 0}
    assert fc["signup_verified"] == {"n": 2, "u": 2}
    assert fc["payment_success"]["n"] == 1


def test_recent_events_merges_props(monkeypatch):
    monkeypatch.setattr(a, "_db_connect", lambda: _FakeConn({"sql": []}))
    rec = a.recent_events(5)
    assert rec[0]["event"] == "payment_success"
    assert rec[0]["ts"] == "2026-07-02T12:00:00"
    assert rec[0]["plan"] == "premium"          # JSONB props merged into the row


def test_event_name_truncated(monkeypatch):
    store = {"sql": []}
    monkeypatch.setattr(a, "_db_connect", lambda: _FakeConn(store))
    a.record_event("x" * 200, uid=None, props=None)
    ins = [p for s, p in store["sql"] if "INSERT" in s][0]
    assert len(ins[0]) == 64                     # event capped at 64 chars


# ── graceful degradation with NO database ─────────────────────────────────────
def test_no_db_is_safe(monkeypatch):
    monkeypatch.setattr(a, "_db_connect", lambda: None)
    assert a.record_event("landing_view") is False
    assert a.funnel_counts() is None             # None => caller falls back to JSONL
    assert a.recent_events() == []
    assert a.enabled() is False


def test_db_error_returns_safely(monkeypatch):
    class _Boom:
        def cursor(self): raise RuntimeError("connection dropped")
    monkeypatch.setattr(a, "_db_connect", lambda: _Boom())
    monkeypatch.setattr(a, "_db_reset", lambda: None)
    assert a.record_event("x") is False          # retries once, then gives up cleanly
    assert a.funnel_counts() is None
