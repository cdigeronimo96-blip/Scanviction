"""app.py security helpers — password hashing/verification, XSS escaping, seed
accounts, and recs-store pruning. Imports the monolith once via the `app` fixture
(storage redirected to a temp dir, worker disabled — see conftest)."""
import time


# ── password hashing / verification ──────────────────────────────────────────
def test_new_hashes_are_bcrypt_and_verify(app):
    h = app.hp("S3cret!pw")
    assert app._is_bcrypt_hash(h)                 # new passwords use bcrypt, not sha256
    assert app.verify_pw("S3cret!pw", h)
    assert not app.verify_pw("wrong", h)


def test_legacy_sha256_still_verifies(app):
    legacy = app._hp("oldpass")                   # a pre-existing unsalted sha256 hash
    assert not app._is_bcrypt_hash(legacy)
    assert app.verify_pw("oldpass", legacy)       # verifies (enables lazy migration on login)
    assert not app.verify_pw("nope", legacy)


def test_verify_pw_rejects_empty(app):
    assert not app.verify_pw("", app.hp("x"))
    assert not app.verify_pw("x", "")
    assert not app.verify_pw("x", None)


# ── no shipped default privileged credentials ────────────────────────────────
def test_no_default_privileged_credentials(app, monkeypatch):
    monkeypatch.setenv("SEED_DEMO_ACCOUNTS", "0")
    seed = app._load_seed_accounts()
    # showcase accounts only exist when explicitly enabled
    assert "demo@scanviction.com" not in seed
    assert "premium@scanviction.com" not in seed
    # whatever privileged accounts exist must NOT accept the old hardcoded defaults
    for acct in seed.values():
        assert not app.verify_pw("admin_change_me", acct.get("pw", ""))
        assert not app.verify_pw("owner_change_me", acct.get("pw", ""))


def test_demo_accounts_gated_on_env(app, monkeypatch):
    monkeypatch.setenv("SEED_DEMO_ACCOUNTS", "1")
    seed = app._load_seed_accounts()
    assert "demo@scanviction.com" in seed
    # the demo account is free-tier and its password verifies through verify_pw
    assert app.verify_pw("demo123", seed["demo@scanviction.com"]["pw"])
    assert seed["demo@scanviction.com"]["role"] == "free"


# ── XSS escaping at unsafe_allow_html sinks ──────────────────────────────────
def test_esc_escapes_html(app):
    out = app._esc("<script>alert('x')</script>")
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert app._esc(None) == ""
    assert app._esc('a "b" <c>') == "a &quot;b&quot; &lt;c&gt;"


# ── recs store pruning (bounds unbounded growth) ─────────────────────────────
def test_prune_recs_drops_stale_keeps_active(app):
    now = time.time()
    old = now - (app.RECS_RETENTION_DAYS + 5) * 86400
    recs = {
        "__universe__|||OLD": {"ticker": "OLD", "triggered_at": old,
                               "last_updated": old, "entry_price": 5.0},
        "__universe__|||ACT": {"ticker": "ACT", "triggered_at": old,
                               "last_updated": now - 3600, "entry_price": 5.0},
    }
    kept, dropped = app._prune_recs(recs)
    assert "__universe__|||OLD" not in kept        # abandoned snapshot aged out
    assert "__universe__|||ACT" in kept            # active signal kept...
    assert kept["__universe__|||ACT"]["entry_price"] == 5.0   # ...and NOT re-anchored
    assert dropped == 1


def test_prune_recs_enforces_hard_cap(app):
    now = time.time()
    big = {f"c|||T{i}": {"last_updated": now - i} for i in range(app.RECS_MAX_KEYS + 5000)}
    kept, dropped = app._prune_recs(big)
    assert len(kept) == app.RECS_MAX_KEYS
    assert dropped == 5000
