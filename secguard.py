"""Scanviction — abuse guards: rate limiting, signup honeypot, login lockout, email sanity.

Pure of Streamlit (the caller supplies a client key + optional `now`), so it's unit-testable and
importable anywhere. State is IN-PROCESS (module dicts) — a solid FIRST layer for a single-replica
deployment; it resets on restart, which is acceptable for velocity controls. At multi-replica scale,
back these with a shared store (Redis / the kv_store) keyed the same way.

Threat model this addresses:
  • MASS SIGNUPS / bot registration  → honeypot + min-fill-time + per-client & global rate limits.
  • LOGIN BRUTE-FORCE                 → per-email failure lockout (on top of bcrypt's slow verify).
  • RESET EMAIL-BOMBING / quota abuse → per-email & per-client reset rate limits.
  • Garbage/oversized input           → email-shape + length validation.
"""
import os
import re
import threading
import time as _time

_LOCK = threading.Lock()
_EVENTS = {}   # (bucket, key) -> [timestamps]   sliding-window rate limiter
_FAILS = {}    # email        -> [timestamps]    recent failed logins
_LOCKED = {}   # email        -> locked_until_ts

# ── tunables (env-overridable) ───────────────────────────────────────────────
def _int(name, d):
    try: return int(os.environ.get(name, d))
    except Exception: return d

SIGNUP_MAX_PER_CLIENT   = _int("SIGNUP_MAX_PER_CLIENT", 5)      # per client / window
SIGNUP_MAX_GLOBAL       = _int("SIGNUP_MAX_GLOBAL", 40)         # circuit breaker, all clients / window
SIGNUP_WINDOW_S         = _int("SIGNUP_WINDOW_S", 600)          # 10 min
SIGNUP_MIN_FILL_S       = _int("SIGNUP_MIN_FILL_S", 2)          # reject submits faster than a human can type

LOGIN_MAX_FAILS         = _int("LOGIN_MAX_FAILS", 8)            # failures before lockout
LOGIN_FAIL_WINDOW_S     = _int("LOGIN_FAIL_WINDOW_S", 900)      # 15 min
LOGIN_LOCK_S            = _int("LOGIN_LOCK_S", 900)             # lock duration 15 min

RESET_MAX_PER_EMAIL     = _int("RESET_MAX_PER_EMAIL", 3)        # reset emails per address / window
RESET_MAX_PER_CLIENT    = _int("RESET_MAX_PER_CLIENT", 6)       # reset requests per client / window
RESET_WINDOW_S          = _int("RESET_WINDOW_S", 900)

# Shape check only (not deliverability). Excludes whitespace, a second @, and the HTML/quote
# metacharacters <>"'`  so injection-ish input is rejected at the door (belt-and-suspenders on top
# of _esc at every render sink).
_EMAIL_RE = re.compile(r"""^[^@\s<>"'`]{1,64}@[^@\s<>"'`]{1,255}\.[^@\s<>"'`]{2,}$""")


def _prune(lst, cutoff):
    return [t for t in lst if t > cutoff]


def rate_ok(bucket, key, max_n, window_s, now=None):
    """Sliding-window rate limit: record this event and return True if at/under the cap. A blank
    key is coerced to a shared bucket so a missing client id still gets *some* throttling."""
    now = now if now is not None else _time.time()
    k = (bucket, str(key or "_"))
    with _LOCK:
        lst = _prune(_EVENTS.get(k, []), now - window_s)
        allowed = len(lst) < max_n
        if allowed:
            lst.append(now)
        _EVENTS[k] = lst
    return allowed


def honeypot_ok(value):
    """True when the hidden honeypot field is empty — a human never sees it; bots fill it."""
    return not (str(value or "").strip())


def valid_email(email):
    """Cheap shape + length check (not deliverability). Rejects garbage and oversized input."""
    e = (email or "").strip()
    return bool(e) and len(e) <= 254 and bool(_EMAIL_RE.match(e))


# ── signup gate ──────────────────────────────────────────────────────────────
def signup_allowed(client_key, now=None):
    """(ok, reason). Enforces a per-client cap AND a global circuit breaker so a flood of bots
    (even across many clients/emails) can't mass-register or drain the email quota."""
    now = now if now is not None else _time.time()
    if not rate_ok("signup_client", client_key, SIGNUP_MAX_PER_CLIENT, SIGNUP_WINDOW_S, now):
        return False, "Too many sign-ups from here. Please wait a few minutes and try again."
    if not rate_ok("signup_global", "*", SIGNUP_MAX_GLOBAL, SIGNUP_WINDOW_S, now):
        return False, "We're seeing unusually high sign-up volume. Please try again shortly."
    return True, ""


# ── login lockout ────────────────────────────────────────────────────────────
def login_locked(email, now=None):
    """Seconds remaining on a lockout for this email (0 = not locked)."""
    now = now if now is not None else _time.time()
    with _LOCK:
        until = _LOCKED.get((email or "").lower(), 0)
    return max(0, int(until - now)) if until > now else 0


def note_login_fail(email, now=None):
    """Record a failed login; lock the account temporarily after too many in the window.
    Returns seconds locked (0 if not yet locked). Slows credential-stuffing beyond bcrypt."""
    now = now if now is not None else _time.time()
    e = (email or "").lower()
    with _LOCK:
        lst = _prune(_FAILS.get(e, []), now - LOGIN_FAIL_WINDOW_S)
        lst.append(now)
        _FAILS[e] = lst
        if len(lst) >= LOGIN_MAX_FAILS:
            _LOCKED[e] = now + LOGIN_LOCK_S
            _FAILS[e] = []
            return LOGIN_LOCK_S
    return 0


def clear_login_fails(email):
    """Wipe failure/lock state on a successful login."""
    e = (email or "").lower()
    with _LOCK:
        _FAILS.pop(e, None)
        _LOCKED.pop(e, None)


# ── reset gate ───────────────────────────────────────────────────────────────
def reset_allowed(email, client_key, now=None):
    """(ok, reason). Caps reset emails per address (anti email-bombing) AND per client."""
    now = now if now is not None else _time.time()
    if not rate_ok("reset_email", (email or "").lower(), RESET_MAX_PER_EMAIL, RESET_WINDOW_S, now):
        return False, "A reset link was already sent recently. Check your inbox (and spam)."
    if not rate_ok("reset_client", client_key, RESET_MAX_PER_CLIENT, RESET_WINDOW_S, now):
        return False, "Too many reset requests from here. Please wait a few minutes."
    return True, ""


def _reset_state_for_tests():
    with _LOCK:
        _EVENTS.clear(); _FAILS.clear(); _LOCKED.clear()
