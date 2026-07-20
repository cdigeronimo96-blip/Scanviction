"""Scanviction — recommendation snapshot store (extracted from app.py).

On-disk store of every recommendation the engine surfaces, keyed by
"<category>|||<ticker>". The FIRST time a (category, ticker) signal appears we
capture entry_price + triggered_at and NEVER overwrite them, so performance is
always measured from the original signal; each refresh updates the live fields
(current / max / min price). Powers the card's "performance since signal" /
"$1000 since signal" figures and the ML / evaluate_all training set (the
"__universe__" anchors). Bounded on write by _prune_recs so it can't grow forever.

Reads/writes route through kvstore (Postgres kv_store OR atomic JSON files). The
store path is the SAME constant msp_store exposes, so the app and the worker share
one row/file. Pure of app state; imports Streamlit only for the process-wide lock.
"""
import os as _os
import time
import streamlit as st

from kvstore import _read_json, _write_json
from msp_store import RECS_DB_PATH   # shared canonical path (env MSP_DATA_DIR / RECS_DB_PATH)


def _load_recs() -> dict:
    return _read_json(RECS_DB_PATH, {})

def _save_recs(d: dict):
    _write_json(RECS_DB_PATH, d)

def _rec_key(category: str, ticker: str) -> str:
    return f"{category}|||{ticker}"

# The recs store accumulates a snapshot per (category, ticker) — including a
# "__universe__" anchor for EVERY scored ticker each warm (the systematic ML /
# evaluate_all training set). Left unbounded it grows forever (delisted names,
# categories a ticker has left) and every warm pays a bigger read+write, while
# the ML sweep fetches OHLCV for each dead key. Bound it on write.
RECS_RETENTION_DAYS = float(_os.environ.get("RECS_RETENTION_DAYS", "180"))
RECS_MAX_KEYS       = int(_os.environ.get("RECS_MAX_KEYS", "20000"))

def _prune_recs(recs: dict):
    """Drop snapshots not updated within the retention window, then hard-cap by
    most-recently-updated. Keys on `last_updated`, so an ACTIVE signal (refreshed
    every warm → last_updated≈now) is never pruned or re-anchored; only abandoned
    snapshots (ticker left the universe/category) age out. Returns (kept, dropped)."""
    if not recs:
        return recs, 0
    cutoff = time.time() - RECS_RETENTION_DAYS * 86400
    def _ts(s): return s.get("last_updated") or s.get("triggered_at") or 0
    kept = {k: s for k, s in recs.items() if _ts(s) >= cutoff}
    if len(kept) > RECS_MAX_KEYS:
        top = sorted(kept.items(), key=lambda kv: _ts(kv[1]), reverse=True)[:RECS_MAX_KEYS]
        kept = dict(top)
    return kept, len(recs) - len(kept)

@st.cache_resource(show_spinner=False)
def _recs_lock():
    """Process-wide lock serializing the recommendation-store read-modify-write.
    Without it the background worker (writing __universe__ snapshots) and the
    request path (render_cat writing per-category snapshots) race on the whole-file
    load+save: a torn read makes record_*() treat every snapshot as new and
    RE-ANCHOR it — resetting the 'since signal' entry price + timestamp the user
    sees — and a lost write clobbers good anchors. cache_resource gives the SAME
    lock across reruns/sessions/threads (a plain module-global lock would reset per
    rerun and never actually mutually exclude)."""
    import threading as __th
    return __th.Lock()
_RECS_LOCK = _recs_lock()

def record_recommendation(category: str, ticker: str, price: float,
                          score=None, recommendation=None, why=None):
    """Idempotently record a recommendation snapshot and update live stats.

    Returns the snapshot dict. On first sighting it stores entry_price +
    triggered_at. On every call it refreshes current_price and the running
    max_price / min_price (for max-upside / max-drawdown), without ever
    mutating the entry price or timestamp.
    """
    if not ticker or not price or price <= 0:
        return None
    with _RECS_LOCK:
        recs = _load_recs()
        key = _rec_key(category, ticker)
        now = time.time()
        snap = recs.get(key)
        if snap is None:
            snap = {
                "category": category, "ticker": ticker,
                "entry_price": float(price), "triggered_at": now,
                "current_price": float(price),
                "max_price": float(price), "min_price": float(price),
                "score_at_trigger": score, "recommendation": recommendation,
                "why": why, "last_updated": now,
            }
        else:
            snap["current_price"] = float(price)
            snap["max_price"] = max(snap.get("max_price", price), float(price))
            snap["min_price"] = min(snap.get("min_price", price), float(price))
            snap["last_updated"] = now
            # keep latest score/why for display, but never touch entry price/time
            if score is not None: snap["score_at_trigger"] = snap.get("score_at_trigger", score)
            if recommendation is not None: snap["recommendation"] = recommendation
            if why is not None: snap["why"] = why
        recs[key] = snap
        _save_recs(recs)
        return snap

def record_recommendations_bulk(category: str, items):
    """Record many snapshots for one category in a SINGLE read + SINGLE write.

    `items` is an iterable of (ticker, price, score, recommendation, why). The
    old approach called record_recommendation() per stock, which did a full
    load+save of the store on each call — ~10 disk/DB round-trips per category
    click, contending with the background worker's lock. This batches them so a
    click costs one store write regardless of how many stocks matched.
    """
    if not items:
        return
    with _RECS_LOCK:
        recs = _load_recs()
        now = time.time()
        changed = False
        for (ticker, price, score, recommendation, why) in items:
            if not ticker or not price or price <= 0:
                continue
            key = _rec_key(category, ticker)
            snap = recs.get(key)
            if snap is None:
                recs[key] = {
                    "category": category, "ticker": ticker,
                    "entry_price": float(price), "triggered_at": now,
                    "current_price": float(price),
                    "max_price": float(price), "min_price": float(price),
                    "score_at_trigger": score, "recommendation": recommendation,
                    "why": why, "last_updated": now,
                }
                changed = True
            else:
                snap["current_price"] = float(price)
                snap["max_price"] = max(snap.get("max_price", price), float(price))
                snap["min_price"] = min(snap.get("min_price", price), float(price))
                snap["last_updated"] = now
                if recommendation is not None: snap["recommendation"] = recommendation
                if why is not None: snap["why"] = why
                changed = True
        if changed:
            recs, _ = _prune_recs(recs)   # bound store growth (runs every warm via the __universe__ bulk)
            _save_recs(recs)

def get_recommendation_snapshot(category: str, ticker: str):
    return _load_recs().get(_rec_key(category, ticker))
