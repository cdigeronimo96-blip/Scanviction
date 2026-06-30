"""telegram_link.py — deep-link connect flow (token -> chat_id). Network is mocked so
the test is hermetic: we replace the module's _get/_post (the only Telegram I/O)."""
import pytest
import telegram_link as tg


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Isolate the link store to a temp file; clear the cached bot username."""
    monkeypatch.setattr(tg, "_LINKS_KEY", str(tmp_path / "tg_links.json"))
    monkeypatch.setattr(tg, "_BOT_USERNAME", None)


@pytest.fixture
def fake_api(monkeypatch):
    """In-memory stand-in for the Telegram Bot API (getMe / getUpdates / sendMessage)."""
    state = {"updates": [], "sent": []}

    def fake_get(token, method, **params):
        if method == "getMe":
            return {"ok": True, "result": {"username": "StockWinsAlertsBot"}}
        if method == "getUpdates":
            off = params.get("offset")
            ups = state["updates"]
            if off is not None:                       # Telegram confirms < offset
                ups = [u for u in ups if u["update_id"] >= off]
            return {"ok": True, "result": ups}
        return {"ok": False}

    def fake_post(token, method, **payload):
        if method == "sendMessage":
            state["sent"].append(payload)
        return {"ok": True}

    monkeypatch.setattr(tg, "_get", fake_get)
    monkeypatch.setattr(tg, "_post", fake_post)
    return state


def _start(uid, chat_id, text):
    return {"update_id": uid, "message": {"chat": {"id": chat_id}, "text": text}}


def test_make_link_token_stores_and_builds_deeplink(store, fake_api):
    tok, deep = tg.make_link_token("a@b.com", "StockWinsAlertsBot")
    assert tok.startswith("L")
    assert deep == f"https://t.me/StockWinsAlertsBot?start={tok}"
    assert tg._state()["tokens"][tok]["email"] == "a@b.com"


def test_poll_links_links_chat_id_and_replies(store, fake_api):
    tok, _ = tg.make_link_token("user@x.com", "Bot")
    fake_api["updates"] = [_start(101, 55501, f"/start {tok}")]

    linked = tg.poll_links("T")
    assert linked == [("user@x.com", "55501")]              # email matched, chat_id captured

    s = tg._state()
    assert tok not in s["tokens"]                           # one-time token consumed
    assert s["offset"] == 101                               # offset advanced
    assert any("connected" in (m.get("text", "").lower()) for m in fake_api["sent"])
    assert tg.poll_links("T") == []                         # nothing new on a second poll


def test_bare_start_replies_but_does_not_link(store, fake_api):
    fake_api["updates"] = [_start(5, 999, "/start")]
    assert tg.poll_links("T") == []
    assert tg._state()["offset"] == 5
    assert fake_api["sent"], "a bare /start should still get a helpful fallback reply"


def test_unknown_token_does_not_link(store, fake_api):
    tg.make_link_token("real@x.com", "Bot")
    fake_api["updates"] = [_start(7, 12345, "/start Lbogus")]
    assert tg.poll_links("T") == []


def test_no_token_is_noop(store, fake_api):
    assert tg.poll_links("") == []
    assert fake_api["sent"] == []


def test_offset_prevents_reprocessing(store, fake_api):
    tok, _ = tg.make_link_token("u@x.com", "Bot")
    fake_api["updates"] = [_start(20, 1, f"/start {tok}")]
    assert len(tg.poll_links("T")) == 1
    assert tg.poll_links("T") == []                         # same update, now below offset


def test_bot_username_cached(store, fake_api):
    assert tg.bot_username("T") == "StockWinsAlertsBot"


def test_completed_link_pickup(store, fake_api):
    tok, _ = tg.make_link_token("u@x.com", "Bot")
    fake_api["updates"] = [_start(30, 42424, f"/start {tok}")]
    assert tg.poll_links("T") == [("u@x.com", "42424")]   # processing stashes a completed link
    assert tg.pop_completed_link("u@x.com") == "42424"     # app picks it up
    assert tg.pop_completed_link("u@x.com") is None        # one-time


def test_pop_completed_link_absent(store, fake_api):
    assert tg.pop_completed_link("nobody@x.com") is None
    assert tg.pop_completed_link("") is None


def test_start_listener_noop_without_token(store, fake_api):
    assert tg.start_listener("") is False
    assert tg.is_listening() is False
