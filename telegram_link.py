"""
telegram_link.py — one-tap "Connect Telegram" linking + an always-on bot listener.

The DELIVERY side already exists (alerts_worker.send_telegram → user['telegram_chat_id'],
premium-gated + subscription-matched). This module supplies the two missing pieces:

  1. CONNECT: make_link_token(email) → a one-time token + https://t.me/<bot>?start=<token>.
  2. LISTEN: start_listener(token) runs ONE background thread that long-polls getUpdates and
     reacts instantly — it auto-links "/start <token>" to the pending email (and stashes the
     chat_id in a "completed" store the app picks up), and replies to a bare "/start" with the
     user's chat_id. The bot therefore answers Start immediately instead of looking dead.

The app then calls pop_completed_link(email) (cheap local read) to finish the link in its own
users_db — so the app stays the single writer of user records.

No Streamlit dependency (only `requests` + the shared `msp_store`), so it is unit-testable and
safe to import anywhere. The caller supplies the bot token (app: st.secrets; worker: env).

SINGLE-CONSUMER: Telegram getUpdates allows only ONE poller advancing the offset. The listener
is that one consumer; while it runs the app uses pop_completed_link instead of polling itself
(poll_links stays for non-listener contexts, e.g. a worker one-shot, or as a fallback). At
multi-replica scale, move to a Telegram webhook or a single dedicated poller process.
"""
import os
import time
import json as _json
import secrets as _secrets
import threading

# Shared durable store (Postgres via DATABASE_URL, else .msp_data files) so the link token,
# getUpdates offset, and completed links survive restarts and are seen across components.
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
LISTEN_TIMEOUT = int(os.environ.get("TG_LISTEN_TIMEOUT", "25"))  # getUpdates long-poll seconds

_API = "https://api.telegram.org/bot{token}/{method}"
_BOT_USERNAME = None              # cached getMe().username (module global survives reruns)
_STATE_LOCK = threading.Lock()    # serialize read-modify-write of the JSON link state
_LISTENER_LOCK = threading.Lock()
_LISTENER_STARTED = False


def _state():
    s = _read(_LINKS_KEY, {}) or {}
    s.setdefault("tokens", {})     # token -> {"email": str, "created": float}
    s.setdefault("offset", 0)      # last processed getUpdates update_id
    s.setdefault("completed", {})  # email -> {"chat_id": str, "ts": float} (app picks up)
    return s


def _save_state(s):
    _write(_LINKS_KEY, s)


def make_link_token(email, bot_username=None):
    """Create a one-time connect token for `email`; return (token, deep_link).

    Prunes expired tokens and any prior token for the same email (one live link per user).
    deep_link is "" if bot_username is unknown — the caller can still surface the token.
    """
    with _STATE_LOCK:
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
    p = {k: v for k, v in params.items() if v is not None}
    # requests timeout must exceed Telegram's long-poll timeout, else the socket aborts mid-poll.
    rt = 15 + int(params.get("timeout", 0) or 0)
    r = requests.get(_API.format(token=token, method=method), params=p, timeout=rt)
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


def _process_updates(token, updates):
    """Process a batch of getUpdates results: auto-link "/start <token>" to its pending email
    (stashing chat_id in `completed`), reply to a bare "/start" with the chat id, and advance
    the stored offset so each update is handled once. Returns [(email, chat_id)] newly linked.

    State mutation happens under _STATE_LOCK; the network replies are sent AFTER the lock is
    released (never hold the lock across I/O).
    """
    linked, replies = [], []
    with _STATE_LOCK:
        s = _state()
        offset = int(s.get("offset", 0) or 0)
        max_id = offset
        changed = False
        for upd in updates:
            uid = int(upd.get("update_id", 0) or 0)
            if uid > max_id:
                max_id = uid
            msg = upd.get("message") or upd.get("edited_message") or {}
            text = (msg.get("text") or "").strip()
            chat = (msg.get("chat") or {}).get("id")
            if not chat or not text:
                continue
            # Accept the connect token either via "/start <token>" OR as a plain pasted code:
            # an already-started bot does NOT re-fire the /start deep-link payload, so a user who
            # has used the bot before can simply send the code to connect.
            tok = next((w for w in text.split() if w in s["tokens"]), "")
            if tok:
                email = s["tokens"].pop(tok, {}).get("email")
                changed = True
                if email:
                    s["completed"][email] = {"chat_id": str(chat), "ts": time.time()}
                    linked.append((email, str(chat)))
                    replies.append((chat,
                        "✅ <b>Scanviction connected!</b>\n\nYou'll get your signal alerts "
                        "right here. Manage which ones in Settings → Notifications."))
            elif text.startswith("/start"):
                replies.append((chat,
                    "👋 Welcome to <b>Scanviction</b>.\n\nTo connect, tap <b>Connect "
                    "Telegram</b> in the app (Settings → Profile) and send the connect code it "
                    f"shows. To link manually instead, your chat ID is <code>{chat}</code>."))
            # else: an ordinary message with no pending code — ignore (offset already advanced)
        if max_id > offset:
            s["offset"] = max_id
            changed = True
        if changed:
            _save_state(s)
    for chat, text in replies:
        _reply(token, chat, text)
    return linked


def poll_links(token):
    """One-shot: read new bot messages and process them (see _process_updates). For contexts
    WITHOUT the background listener (worker one-shot, or a fallback). Returns [(email, chat_id)].
    Do not call this while the listener is running — they'd compete for the same updates."""
    if not token:
        return []
    try:
        with _STATE_LOCK:
            offset = int(_state().get("offset", 0) or 0)
        d = _get(token, "getUpdates",
                 offset=(offset + 1) if offset else None, timeout=0, limit=50)
    except Exception:
        return []
    if not d.get("ok"):
        return []
    return _process_updates(token, d.get("result", []))


def pop_completed_link(email):
    """Return (and clear) the chat_id the listener linked for `email`, or None. The app calls
    this to finish the connection in its own users_db (app stays the single users_db writer)."""
    if not email:
        return None
    with _STATE_LOCK:
        s = _state()
        rec = s.get("completed", {}).pop(email, None)
        if rec is not None:
            _save_state(s)
    if not rec:
        return None
    return rec.get("chat_id") if isinstance(rec, dict) else str(rec)


def is_listening():
    """True if the background getUpdates listener thread is running in this process."""
    return _LISTENER_STARTED


def _listener_loop(token):
    while True:
        try:
            with _STATE_LOCK:
                offset = int(_state().get("offset", 0) or 0)
            d = _get(token, "getUpdates",
                     offset=(offset + 1) if offset else None, timeout=LISTEN_TIMEOUT, limit=50)
            if d.get("ok"):
                _process_updates(token, d.get("result", []))
            else:
                time.sleep(3)
        except Exception:
            time.sleep(3)  # network blip / rate limit — back off and retry


def start_listener(token):
    """Start the SINGLE background getUpdates consumer (idempotent). No-op without a token or
    when MSP_DISABLE_WORKER=1 (tests/tooling). Returns True if the listener is running."""
    global _LISTENER_STARTED
    if not token or os.environ.get("MSP_DISABLE_WORKER") == "1":
        return False
    with _LISTENER_LOCK:
        if _LISTENER_STARTED:
            return True
        threading.Thread(target=_listener_loop, args=(token,),
                         daemon=True, name="msp-tg-listener").start()
        _LISTENER_STARTED = True
    return True
