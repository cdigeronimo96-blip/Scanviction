"""Scanviction — self-hosted Web Push (VAPID), no OneSignal required.

WHY: OneSignal was an external dependency (account, SDK script, per-device IDs held by
a third party) for something browsers give us natively. The Push API + a VAPID key pair
+ pywebpush deliver the exact same "app-style" notifications with zero external service
and zero fees, straight from our own alert pipeline.

SETUP (one time)
----------------
1. Generate a VAPID key pair (pywebpush installs the `vapid` CLI via py-vapid):
       python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); \
                  print('VAPID_PRIVATE_KEY =', v.private_pem().decode()); \
                  print('VAPID_PUBLIC_KEY  =', v.public_key_urlsafe_base64())"
   (or `vapid --gen` which writes private_key.pem / public_key.pem)
2. Add to secrets.toml (Render → Environment → Secret Files):
       VAPID_PUBLIC_KEY  = "<urlsafe-base64 public key>"
       VAPID_PRIVATE_KEY = "<PEM private key, or path to the .pem>"
       VAPID_CLAIMS_EMAIL = "mailto:support@scanviction.com"
3. static/sw.js (committed in the repo) handles the `push` event; the Settings →
   Profile page runs the subscribe flow and hands the subscription JSON back to the
   app via a ?push_sub= query param, which app.py stores on the user record.

This module is PURE (no Streamlit): the worker thread and the alerts cron can both
import it. Secrets are read from env; app.py passes st.secrets values through env
capture the same way it does for the Polygon/Telegram keys.
"""
import base64
import json
import logging
import os

log = logging.getLogger("msp.webpush")

try:
    from pywebpush import webpush, WebPushException
    HAS_WEBPUSH = True
except Exception:                                    # pragma: no cover
    HAS_WEBPUSH = False

    class WebPushException(Exception):
        pass


def _get(name, default=""):
    v = os.environ.get(name, "") or default
    return v.strip() if isinstance(v, str) else v


def get_public_key():
    """The urlsafe-base64 VAPID public key handed to pushManager.subscribe()."""
    return _get("VAPID_PUBLIC_KEY")


def get_private_key():
    """PEM string or path to a PEM file."""
    return _get("VAPID_PRIVATE_KEY")


def claims_email():
    e = _get("VAPID_CLAIMS_EMAIL", "mailto:support@scanviction.com")
    return e if e.startswith("mailto:") else f"mailto:{e}"


def configured():
    """True when native Web Push can send (library + both keys present)."""
    return bool(HAS_WEBPUSH and get_public_key() and get_private_key())


def decode_subscription(b64: str):
    """Decode the urlsafe-base64 subscription JSON the browser handed back via the
    ?push_sub= param. Returns the subscription dict or None (never raises)."""
    try:
        pad = "=" * (-len(b64) % 4)
        sub = json.loads(base64.urlsafe_b64decode(b64 + pad).decode("utf-8"))
        if isinstance(sub, dict) and sub.get("endpoint"):
            return sub
    except Exception:
        pass
    return None


def send_push(subscription: dict, title: str, body: str, url: str = "/") -> bool:
    """Send one Web Push notification to one subscription. Returns True on success.
    A 404/410 from the push service means the subscription is dead — we return the
    special string 'gone' so callers can prune it."""
    if not configured() or not subscription:
        return False
    payload = json.dumps({"title": title[:120], "body": body[:400], "url": url})
    try:
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=get_private_key(),
            vapid_claims={"sub": claims_email()},
            ttl=3600,
        )
        return True
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code in (404, 410):
            return "gone"          # caller should drop this subscription
        log.warning(f"webpush failed ({code}): {e}")
        return False
    except Exception as e:                             # pragma: no cover
        log.warning(f"webpush error: {e}")
        return False


def send_to_user(user: dict, title: str, body: str, url: str = "/"):
    """Send to every stored subscription on a user record (user['push_subscriptions'],
    list of subscription dicts). Returns (sent_count, pruned_list) where pruned_list
    is the subscription list with dead endpoints removed (caller persists it if it
    changed)."""
    subs = list(user.get("push_subscriptions") or [])
    if not subs or not configured():
        return 0, subs
    sent, kept = 0, []
    for s in subs:
        res = send_push(s, title, body, url)
        if res == "gone":
            continue               # dead endpoint — drop
        kept.append(s)
        if res:
            sent += 1
    return sent, kept
