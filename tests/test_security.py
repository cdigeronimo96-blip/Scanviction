"""security.py — auth hashing + HTML escaping, tested in isolation (no app import)."""
import security as sec


def test_new_hashes_are_bcrypt_and_verify():
    h = sec.hp("S3cret!pw")
    assert sec._is_bcrypt_hash(h)
    assert sec.verify_pw("S3cret!pw", h)
    assert not sec.verify_pw("wrong", h)


def test_legacy_sha256_verifies():
    legacy = sec._hp("oldpass")
    assert not sec._is_bcrypt_hash(legacy)
    assert sec.verify_pw("oldpass", legacy)
    assert not sec.verify_pw("nope", legacy)


def test_verify_pw_rejects_empty():
    assert not sec.verify_pw("", sec.hp("x"))
    assert not sec.verify_pw("x", "")
    assert not sec.verify_pw("x", None)


def test_bcrypt_hashes_are_salted_unique():
    # two hashes of the same password differ (random salt) yet both verify
    a, b = sec.hp("samepw"), sec.hp("samepw")
    assert a != b
    assert sec.verify_pw("samepw", a) and sec.verify_pw("samepw", b)


def test_esc_escapes_html():
    assert "<script>" not in sec._esc("<script>alert(1)</script>")
    assert sec._esc("<b>") == "&lt;b&gt;"
    assert sec._esc('a "q"') == "a &quot;q&quot;"
    assert sec._esc(None) == ""
    assert sec._esc(42) == "42"
