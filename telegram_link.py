"""
telegram_link.py — one-tap "Connect Telegram" linking for MarketSignalPro.

The DELIVERY side already exists (alerts_worker.send_telegram → user['telegram_chat_id'],
premium-gated + subscription-matched). The piece that was MISSING — and left the whole
pipeline dark — is a way for a user to obtain/register their chat_id: the bot never
responded to /start, so "send /start and paste the Chat ID it replies with" could not
work. This module closes that gap with a deep-link auto-link:

  1. App calls make_link_token(email) → stores a one-time token → builds
       https://t.me/<bot>?start=<token>
  2. User taps it → Telegram delivers the bot "/start <token>".
  3. App calls poll_links(token) → reads getUpdates, matches "/start <token>" to the
     pending email, returns [(email, chat_id)], replies "✅ Connected", and advances the
     stored update offset so each message is processed exactly once.

No Streamlit dependency (only `requests` + the shared `msp_store`), so it is unit-testable
and safe to import anywhere. The caller supplies the bot token (the app reads it from
st.secrets; the worker from env) — this module never reads secrets itself.

SINGLE-CONSUMER NOTE: Telegram getUpdates is single-consumer — only ONE process may poll
it (advancing the offset), or pollers steal each other's updates. Here ONLY the app polls,
during the connect flow; the worker only SENDS. At multi-replica scale, switch to a
Telegram webhook or one dedicated poller. Fine for a single app replica.
"""
import os
import time
import json as _json
import secrets as _secrets

# Shared durable store (Postgres via DATABASE_URL, else .msp_data files) so the link
# token + getUpdates offset survive restarts and are seen across components.
try:
    import msp_store as _store
    _LINKS_KEY = _store._data_path("msp_tg_links.json", "TG_LINKS_PATH")
    _read = _store.read_json
    _write = _store.write_json
except Exception:  # pragma: no cover - exercised only without the shared store
    _LINKS_KEY = os.environ.get("TG_LINKS_PATH", "/tmp/msp_tg_links.json")

    def _read(key, default=None):
        try:
            with open(key) as f:
                return _json.load(f)
        except Exception:
            return default if default is not None else {}

    def _write(key, data):
        try:
            with open(key, "w") as f:
                _json.dump(data, f, default=str)
        except Exception:
            pass

# How long a generated connect link stays valid before the user must regenerate it.
LINK_TOKEN_TTL = int(os.environ.get("TG_LINK_TTL", "1800"))  # 30 min

_API = "https://api.telegram.org/bot{token}/{method}"
_BOT_USERNAME = None  # cached getMe().username (module global survives Streamlit reruns)


def _state():
    s = _read(_LINKS_KEY, {}) or {}
    s.setdefault("tokens", {})  # token -> {"email": str, "created": float}
    s.setdefault("offset", 0)   # last processed getUpdates update_id
    return s


def _save_state(s):
    _write(_LINKS_KEY, s)


def make_link_token(email, bot_username=None):
    """Create a one-time connect token for `email`; return (token, deep_link).

    Prunes expired tokens and any prior token for the same email (one live link per user).
    deep_link is "" if bot_username is unknown — the caller can still surface the token.
    """
    s = _state()
    now = time.time()
    s["tokens"] = {
        t: m for t, m in s["tokens"].items()
        if (now - float(m.get("created", 0) or 0)) < LINK_TOKEN_TTL and m.get("email") != email
    }
    token = "L" + _secrets.token_urlsafe(9)
    s["tokens"][token] = {"email": email, "created": now}
    _save_state(s)
    deep = f"https://t.me/{bot_username}?start={token}" if bot_username else ""
    return token, deep


def _get(token, method, **params):
    import requests
    params = {k: v for k, v in params.items() if v is not None}
    r = requests.get(_API.format(token=token, method=method), params=params, timeout=15)
    return r.json()


def _post(token, method, **payload):
    import requests
    r = requests.post(_API.format(token=token, method=method), json=payload, timeout=12)
    return r.json()


def bot_username(token):
    """Return the bot's @username (cached via getMe). None if token missing/invalid."""
    global _BOT_USERNAME
    if _BOT_USERNAME:
        return _BOT_USERNAME
    if not token:
        return None
    try:
        d = _get(token, "getMe")
        if d.get("ok"):
            _BOT_USERNAME = d["result"].get("username")
    except Exception:
        pass
    return _BOT_USERNAME


def _reply(token, chat_id, text):
    try:
        _post(token, "sendMessage", chat_id=chat_id, text=text,
              parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass


def poll_links(token):
    """Read new bot messages and link any "/start <token>" to its pending email.

    Returns a list of (email, chat_id) newly linked this call. Advances the stored
    getUpdates offset so each update is processed once. Bare/unknown "/start" gets a
    helpful reply (incl. the raw chat id as a manual fallback). No-op → [] without a token.
    """
    if not token:
        return []
    s = _state()
    offset = int(s.get("offset", 0) or 0)
    try:
        d = _get(token, "getUpdates",
                 offset=(offset + 1) if offset else None, timeout=0, limit=50)
    except Exception:
        return []
    if not d.get("ok"):
        return []

    linked, max_id, changed = [], offset, False
    for upd in d.get("result", []):
        uid = int(upd.get("update_id", 0) or 0)
        if uid > max_id:
            max_id = uid
        msg = upd.get("message") or upd.get("edited_message") or {}
        text = (msg.get("text") or "").strip()
        chat = (msg.get("chat") or {}).get("id")
        if not chat or not text.startswith("/start"):
            continue
        parts = text.split(maxsplit=1)
        tok = parts[1].strip() if len(parts) > 1 else ""
        if tok and tok in s["tokens"]:
            email = s["tokens"].pop(tok, {}).get("email")
            changed = True
            if email:
                linked.append((email, str(chat)))
                _reply(token, chat,
                       "✅ <b>MarketSignalPro connected!</b>\n\nYou'll get your signal "
                       "alerts right here. Manage which ones in Settings → Notifications.")
        else:
            _reply(token, chat,
                   "👋 Welcome to <b>MarketSignalPro</b>.\n\nTo connect, tap "
                   "<b>Connect Telegram</b> in the app (Settings → Profile). If you'd rather "
                   f"link manually, your chat ID is <code>{chat}</code>.")
    if max_id > offset:
        s["offset"] = max_id
        changed = True
    if changed:
        _save_state(s)
    return linked
