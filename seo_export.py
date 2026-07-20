"""Project the warm scored universe into a slim JSON snapshot that the STANDALONE SEO site
generator (seo_generate.py) reads. Kept separate from app.py so it's pure + unit-testable and so
the generator never has to import the Streamlit app.

The app calls write_snapshot(...) from the warm worker (leader only). seo_generate.py then reads the
JSON with zero app/Streamlit dependency, so the static site can be built in CI / cron / locally.
"""
import os
import json
import tempfile
from datetime import datetime, timezone

try:                                   # scoring.py is import-safe (no Streamlit); fall back if absent
    from scoring import category_dir
except Exception:                      # pragma: no cover
    def category_dir(_cat):
        return "long"

# Default snapshot location mirrors the app's data dir; override with MSP_SEO_SNAPSHOT.
_DEFAULT_DIR = os.environ.get(
    "MSP_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".msp_data"))
SNAPSHOT_PATH = os.environ.get("MSP_SEO_SNAPSHOT", os.path.join(_DEFAULT_DIR, "universe_snapshot.json"))
# Also mirrored into the Streamlit static/ dir so the LIVE app can expose it publicly at
# /app/static/universe_snapshot.json (requires enableStaticServing in .streamlit/config.toml) — that
# URL is what the SEO GitHub Action fetches (SEO_SNAPSHOT_URL). See SEO_README.md.
STATIC_SNAPSHOT_PATH = os.environ.get("MSP_SEO_STATIC",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "universe_snapshot.json"))

# Master toggle for the app-side write (default on; the write is leader-gated + wrapped in try/except).
ENABLED = os.environ.get("SEO_SNAPSHOT", "1").strip().lower() not in ("0", "false", "no", "")


def _num(v):
    """Coerce to a JSON-friendly number or None (never NaN/inf, which break JSON + downstream)."""
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return round(f, 4)
    except (TypeError, ValueError):
        return None


def project_row(r):
    """One warm row -> the slim public projection the SEO pages need. Returns None for junk rows.
    Only fields that are safe to publish for logged-out visitors (the free teaser)."""
    t = (r.get("t") or "").strip().upper()
    if not t or not t.isascii() or not all(c.isalnum() or c in ".-" for c in t):
        return None
    q = r.get("q") or {}
    info = r.get("info") or {}
    cat = r.get("primary_cat") or ""
    row = {
        "t": t,
        "price": _num(q.get("price")),
        "pct": _num(q.get("pct")),
        "sc": int(r.get("sc") or 0),
        "conv": int(r.get("conviction") or r.get("sc") or 0),
        "cat": cat,
        "dir": category_dir(cat) if cat else "long",
        "why": (r.get("why") or "").strip()[:240],
    }
    # Real sub-stats ONLY when present (never fabricate — same rule as the app hero).
    dtc = _num(info.get("dtc"))
    ib = int(info.get("insider_buys") or 0)
    pe = _num(info.get("pe"))
    if dtc and dtc >= 3:
        row["dtc"] = dtc
    if ib >= 2:
        row["insider_buys"] = ib
    if pe and pe > 0:
        row["pe"] = pe
    return row


def build_snapshot(rows, generated_at=None):
    """Full snapshot dict from warm rows. generated_at is an ISO string (pass it in — callers that
    can't use wall clock, e.g. deterministic tests, supply their own)."""
    projected = [p for p in (project_row(r) for r in (rows or [])) if p]
    projected.sort(key=lambda p: p.get("conv", 0), reverse=True)
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(projected),
        "rows": projected,
    }


def _atomic_write_json(path, obj):
    """Atomic write (temp file + os.replace) so a reader never sees a half-written file."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def write_snapshot(rows, path=None, generated_at=None):
    """Atomically write the snapshot JSON. Returns the primary path written. On the real app write
    (path omitted) it ALSO mirrors into the static/ dir for public serving; a custom/test path does
    not, so tests never touch the repo's static dir."""
    is_default = path is None
    path = path or SNAPSHOT_PATH
    snap = build_snapshot(rows, generated_at=generated_at)
    _atomic_write_json(path, snap)
    if is_default:
        try:
            _atomic_write_json(STATIC_SNAPSHOT_PATH, snap)
        except Exception:
            pass
    return path
