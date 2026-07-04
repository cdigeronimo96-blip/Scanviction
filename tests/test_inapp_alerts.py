"""In-app alert delivery (Yahoo-free, cron-free): price-alert evaluation against the warm
universe with a Polygon per-ticker fallback, and the two-lane signal delivery (events
immediate + category entries batched into one digest)."""


def _store(monkeypatch, alerts=None, users=None, fired_key="FIRED"):
    """Redirect msp_store's alert/fired reads+writes to an in-memory dict."""
    import msp_store as ms
    mem = {"alerts": alerts or {}, "users": users or {}, "fired": {}}

    def read_json(path, default=None):
        if path == ms.ALERTS_DB_PATH: return mem["alerts"]
        if path == ms.USERS_DB_PATH:  return mem["users"]
        if path == fired_key:         return mem["fired"]
        return {} if default is None else default

    def write_json(path, data):
        if path == fired_key: mem["fired"] = data

    monkeypatch.setattr(ms, "read_json", read_json)
    monkeypatch.setattr(ms, "write_json", write_json)
    monkeypatch.setattr(ms, "_data_path", lambda *a, **k: fired_key)
    return mem


def test_price_above_triggers_then_dedupes(app, monkeypatch):
    monkeypatch.setattr(app, "_worker_is_leader", lambda: True)
    app._UNIVERSE_CACHE["rows"] = [{"t": "AAPL", "q": {"price": 310.0, "pct": 2.0, "vol_ratio": 1.2},
                                    "factors": {"rsi": 61.0, "vol_ratio": 1.2}}]
    _store(monkeypatch,
           alerts={"u@x.com": [{"id": "a1", "ticker": "AAPL", "type": "price_above",
                                "threshold": 300.0, "active": True, "channels": ["email"]}]},
           users={"u@x.com": {"role": "premium", "notif_prefs": {"email_enabled": True}}})
    calls = []
    monkeypatch.setattr(app, "_deliver_user_alert",
                        lambda email, u, tkr, msg, price, pct, ch: calls.append((tkr, price, msg)))
    app._process_price_alerts()
    assert len(calls) == 1 and calls[0][0] == "AAPL" and calls[0][1] == 310.0 and "above" in calls[0][2]
    app._process_price_alerts()          # same hour → deduped
    assert len(calls) == 1


def test_price_below_does_not_trigger_when_above(app, monkeypatch):
    monkeypatch.setattr(app, "_worker_is_leader", lambda: True)
    app._UNIVERSE_CACHE["rows"] = [{"t": "AAPL", "q": {"price": 310.0, "pct": 2.0}, "factors": {}}]
    _store(monkeypatch,
           alerts={"u@x.com": [{"id": "a2", "ticker": "AAPL", "type": "price_below",
                                "threshold": 300.0, "active": True, "channels": ["email"]}]},
           users={"u@x.com": {"role": "free", "notif_prefs": {}}})
    calls = []
    monkeypatch.setattr(app, "_deliver_user_alert", lambda *a: calls.append(a))
    app._process_price_alerts()
    assert calls == []


def test_ticker_outside_warm_uses_polygon_fallback(app, monkeypatch):
    monkeypatch.setattr(app, "_worker_is_leader", lambda: True)
    app._UNIVERSE_CACHE["rows"] = []                       # empty warm universe
    monkeypatch.setattr(app, "_raw_quote", lambda t: {"price": 12.5, "pct": 1.0})   # Polygon fallback
    _store(monkeypatch,
           alerts={"u@x.com": [{"id": "a3", "ticker": "AEHR", "type": "price_above",
                                "threshold": 10.0, "active": True, "channels": ["email"]}]},
           users={"u@x.com": {"role": "free", "notif_prefs": {}}})
    seen = []
    monkeypatch.setattr(app, "_deliver_user_alert",
                        lambda email, u, tkr, msg, price, pct, ch: seen.append(tkr))
    app._process_price_alerts()
    assert seen == ["AEHR"]


def test_signal_delivery_two_lanes(app, monkeypatch):
    """3 category entries → ONE digest; 1 event filing → its own immediate message."""
    import msp_store as ms
    mem = {"users": {"p@x.com": {"role": "premium", "telegram_chat_id": "123",
                                 "notif_prefs": {"telegram_enabled": True, "email_enabled": False}}},
           "deliv": {}}
    monkeypatch.setattr(ms, "read_json",
                        lambda path, d=None: mem["users"] if path == ms.USERS_DB_PATH
                        else mem["deliv"] if path == "DELIV" else ({} if d is None else d))
    monkeypatch.setattr(ms, "write_json",
                        lambda path, data: mem.update(deliv=data) if path == "DELIV" else None)
    monkeypatch.setattr(ms, "_data_path", lambda *a, **k: "DELIV")
    monkeypatch.setattr(app, "_TG_TOKEN_CAPTURED", "tok")
    tg = []
    monkeypatch.setattr(app, "_tg_send_raw", lambda token, cid, msg: (tg.append(msg) or True))
    monkeypatch.setattr(app, "_alert_email", lambda *a, **k: False)
    added = [
        {"ticker": "AAA", "category": "Breakout Watch",   "id": "e1", "score_at_trigger": 80, "trigger_price": 10, "recommendation": "BUY"},
        {"ticker": "BBB", "category": "Relative Strength", "id": "e2", "score_at_trigger": 75, "trigger_price": 20, "recommendation": "BUY"},
        {"ticker": "CCC", "category": "Momentum Leaders",  "id": "e3", "score_at_trigger": 70, "trigger_price": 5,  "recommendation": "WATCH"},
        {"ticker": "DDD", "category": app.EVT_INSIDER,      "id": "e4", "score_at_trigger": 90, "trigger_price": 30, "recommendation": "Insider bought"},
    ]
    app._deliver_new_signals(added)
    assert len(tg) == 2                                   # 1 event msg + 1 digest
    digest = [m for m in tg if "new setup" in m]
    assert len(digest) == 1 and all(t in digest[0] for t in ("AAA", "BBB", "CCC"))
    assert any(app.EVT_INSIDER in m for m in tg)          # event delivered on its own
