"""secguard.py — abuse guards, tested in isolation (no app import). Uses explicit `now` values
so the sliding windows are deterministic and don't depend on wall-clock time."""
import secguard as sg


def setup_function(_):
    sg._reset_state_for_tests()


# ── email validation ─────────────────────────────────────────────────────────
def test_valid_email_accepts_normal():
    assert sg.valid_email("jane@example.com")
    assert sg.valid_email("a.b+tag@sub.domain.co")


def test_valid_email_rejects_garbage_and_oversized():
    assert not sg.valid_email("")
    assert not sg.valid_email("no-at-sign")
    assert not sg.valid_email("two@@at.com")
    assert not sg.valid_email("spaces in@email.com")
    assert not sg.valid_email("nodot@domain")
    assert not sg.valid_email("x@y." )              # empty TLD
    assert not sg.valid_email("a@b.co" + "m" * 300)  # oversized


def test_valid_email_rejects_html_injection():
    assert not sg.valid_email("<script>@x.com")   # space/anglebrackets excluded by shape


# ── honeypot ─────────────────────────────────────────────────────────────────
def test_honeypot_empty_is_ok_filled_is_bot():
    assert sg.honeypot_ok("")
    assert sg.honeypot_ok(None)
    assert sg.honeypot_ok("   ")
    assert not sg.honeypot_ok("anything")


# ── generic sliding-window limiter ───────────────────────────────────────────
def test_rate_ok_blocks_over_cap_then_recovers():
    for i in range(3):
        assert sg.rate_ok("b", "k", 3, 100, now=1000 + i)
    assert not sg.rate_ok("b", "k", 3, 100, now=1003)      # 4th within window → blocked
    assert sg.rate_ok("b", "k", 3, 100, now=1200)          # window elapsed → allowed


def test_rate_ok_isolates_keys_and_buckets():
    assert sg.rate_ok("b", "k1", 1, 100, now=1)
    assert not sg.rate_ok("b", "k1", 1, 100, now=2)
    assert sg.rate_ok("b", "k2", 1, 100, now=2)            # different key unaffected
    assert sg.rate_ok("other", "k1", 1, 100, now=2)        # different bucket unaffected


def test_rate_ok_blank_key_coerced_and_still_throttles():
    assert sg.rate_ok("b", "", 1, 100, now=1)
    assert not sg.rate_ok("b", None, 1, 100, now=2)        # both fall into the shared "_" bucket


# ── signup gate ──────────────────────────────────────────────────────────────
def test_signup_per_client_cap():
    for i in range(sg.SIGNUP_MAX_PER_CLIENT):
        ok, _ = sg.signup_allowed("ip:1.2.3.4", now=1000 + i)
        assert ok
    ok, msg = sg.signup_allowed("ip:1.2.3.4", now=1000)
    assert not ok and "wait" in msg.lower()


def test_signup_global_circuit_breaker():
    # many distinct clients, each under the per-client cap, still trip the global breaker
    tripped = False
    for i in range(sg.SIGNUP_MAX_GLOBAL + 5):
        ok, _ = sg.signup_allowed(f"ip:10.0.0.{i}", now=2000)
        if not ok:
            tripped = True
            break
    assert tripped


# ── login lockout ────────────────────────────────────────────────────────────
def test_login_lockout_after_max_fails():
    e = "victim@example.com"
    assert sg.login_locked(e) == 0
    locked = 0
    for i in range(sg.LOGIN_MAX_FAILS):
        locked = sg.note_login_fail(e, now=5000 + i)
    assert locked == sg.LOGIN_LOCK_S
    assert sg.login_locked(e, now=5000) > 0
    # lock is anchored to the LAST failure timestamp (~5007); expires after LOCK_S beyond that
    assert sg.login_locked(e, now=5000 + sg.LOGIN_MAX_FAILS + sg.LOGIN_LOCK_S + 1) == 0


def test_login_fail_is_case_insensitive():
    sg.note_login_fail("MixedCase@Ex.com", now=1)
    # tracked under the lowercased key
    for i in range(sg.LOGIN_MAX_FAILS - 1):
        sg.note_login_fail("mixedcase@ex.com", now=2 + i)
    assert sg.login_locked("MIXEDCASE@EX.COM", now=3) > 0


def test_clear_login_fails_resets():
    e = "u@x.com"
    for i in range(sg.LOGIN_MAX_FAILS):
        sg.note_login_fail(e, now=1 + i)
    assert sg.login_locked(e, now=1) > 0
    sg.clear_login_fails(e)
    assert sg.login_locked(e, now=1) == 0


def test_login_fails_prune_outside_window():
    e = "slow@x.com"
    # spread failures further apart than the window → never accumulate to a lock
    for i in range(sg.LOGIN_MAX_FAILS + 3):
        locked = sg.note_login_fail(e, now=i * (sg.LOGIN_FAIL_WINDOW_S + 1))
        assert locked == 0


# ── reset gate ───────────────────────────────────────────────────────────────
def test_reset_per_email_cap():
    for i in range(sg.RESET_MAX_PER_EMAIL):
        ok, _ = sg.reset_allowed("a@x.com", "ip:9", now=100 + i)
        assert ok
    ok, msg = sg.reset_allowed("a@x.com", "ip:9", now=100)
    assert not ok and "sent" in msg.lower()


def test_reset_per_client_cap_across_emails():
    # same client hitting many different addresses is capped by the per-client limit
    blocked = False
    for i in range(sg.RESET_MAX_PER_CLIENT + 2):
        ok, _ = sg.reset_allowed(f"user{i}@x.com", "ip:same", now=200)
        if not ok:
            blocked = True
            break
    assert blocked


def test_reset_email_key_is_case_insensitive():
    for i in range(sg.RESET_MAX_PER_EMAIL):
        sg.reset_allowed("Case@X.com", "ip:1", now=1 + i)
    ok, _ = sg.reset_allowed("case@x.com", "ip:2", now=1)   # different client, same email
    assert not ok
