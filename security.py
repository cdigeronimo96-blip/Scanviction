"""MarketSignalPro — security primitives (password hashing + HTML escaping).

Extracted from app.py so the auth-critical code is isolated, independently
importable, and unit-testable WITHOUT loading the Streamlit monolith. Pure module:
no Streamlit, no app state. New passwords use bcrypt; the legacy unsalted sha256
path exists ONLY to verify pre-existing hashes (login lazy-migrates them to bcrypt).
"""
import hashlib
import html as _html
import secrets as _secrets

try:
    import bcrypt as _bcrypt
    HAS_BCRYPT = True
except Exception:
    HAS_BCRYPT = False


def _esc(s):
    """HTML-escape a value before interpolating it into an unsafe_allow_html block.
    Use on ANY user-derived text (names, chat messages, notes, ticker labels) to stop
    stored/reflected XSS."""
    return _html.escape(str(s if s is not None else ""), quote=True)


def _hp(pw):
    """LEGACY unsalted sha256 — kept ONLY to verify pre-existing hashes. Never for new ones."""
    return hashlib.sha256(pw.encode()).hexdigest()


def hp(pw):
    """Hash a NEW password with bcrypt (salted, slow). Falls back to sha256 only if bcrypt
    is unavailable."""
    if HAS_BCRYPT:
        return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt(rounds=12)).decode()
    return _hp(pw)


def _is_bcrypt_hash(stored):
    return isinstance(stored, str) and stored.startswith(("$2a$", "$2b$", "$2y$"))


def verify_pw(pw, stored):
    """Verify a plaintext password against a stored hash — bcrypt OR legacy sha256
    (constant-time for the sha256 path). Returns bool."""
    if not pw or not stored:
        return False
    try:
        if _is_bcrypt_hash(stored):
            return HAS_BCRYPT and _bcrypt.checkpw(pw.encode(), stored.encode())
        return _secrets.compare_digest(_hp(pw), str(stored))
    except Exception:
        return False
