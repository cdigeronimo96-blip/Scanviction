"""Scanviction — recommendation performance & outcome evaluation (pure).

Extracted from app.py. Pure functions only: no Streamlit, no app state, no network —
everything operates on values / OHLCV frames passed in by the caller, so it is directly
unit-testable. Two concerns:

1) Performance math for a live signal (compute_performance) and a human age string.
2) Historical labeling framework: given a recommendation snapshot (frozen entry price +
   trigger timestamp) and the ticker's daily OHLCV, assign an outcome at each horizon
   (1/3/5/10/30 trading days): success (>= SUCCESS_PCT) / failure (<= -FAILURE_PCT) /
   neutral / pending; a benchmark-relative label vs SPY (outperform/underperform/inline);
   max upside & drawdown since signal; and per-category hit-rates.

The network driver (evaluate_all_recommendations, which pulls OHLCV) stays in app.py and
calls evaluate_recommendation() here.
"""
import time


def compute_performance(entry_price: float, current_price: float,
                        invested: float = 1000.0):
    """Performance math for a signal. Returns pct change, $ gain/loss, and the
    current value of a hypothetical `invested` (default $1000) stake."""
    try:
        entry = float(entry_price); cur = float(current_price)
        if entry <= 0:
            return None
        pct = (cur - entry) / entry * 100.0
        shares = invested / entry
        current_value = shares * cur
        gain = current_value - invested
        return {
            "pct": round(pct, 2),
            "shares": round(shares, 4),
            "invested": round(invested, 2),
            "current_value": round(current_value, 2),
            "gain": round(gain, 2),
        }
    except Exception:
        return None

def _humanize_age(triggered_at: float) -> str:
    """Relative age from an epoch timestamp: 'just now' / '5m ago' / '5h ago' / '3d ago' /
    '2w ago' / '5mo ago' / '1y ago' (so an old signal no longer reads '200d ago')."""
    try:
        secs = max(0, time.time() - float(triggered_at))
    except Exception:
        return ""
    if secs < 60:         return "just now"
    if secs < 3600:       return f"{int(secs//60)}m ago"
    if secs < 86400:      return f"{int(secs//3600)}h ago"
    if secs < 7*86400:    return f"{int(secs//86400)}d ago"
    if secs < 30*86400:   return f"{int(secs//(7*86400))}w ago"
    if secs < 365*86400:  return f"{int(secs//(30*86400))}mo ago"
    return f"{int(secs//(365*86400))}y ago"


# ── Historical recommendation labeling framework ─────────────────────────────
HORIZONS = [1, 3, 5, 10, 30]   # trading days
SUCCESS_PCT = 3.0              # >= +3% over horizon = success
FAILURE_PCT = 3.0              # <= -3% over horizon = failure
BENCH_MARGIN = 1.0             # +/-1% band counts as "inline" vs benchmark

def _label_return(ret_pct, success_pct=SUCCESS_PCT, failure_pct=FAILURE_PCT):
    """Map a return % to success / failure / neutral."""
    if ret_pct is None:
        return "pending"
    if ret_pct >= success_pct:
        return "success"
    if ret_pct <= -failure_pct:
        return "failure"
    return "neutral"

def _label_vs_benchmark(stock_ret, bench_ret, margin=BENCH_MARGIN):
    """Map a stock return vs benchmark return to outperform / underperform / inline."""
    if stock_ret is None or bench_ret is None:
        return "pending"
    diff = stock_ret - bench_ret
    if diff > margin:
        return "outperform"
    if diff < -margin:
        return "underperform"
    return "inline"

def _close_n_trading_days_after(df, start_ts, n):
    """Close price `n` trading rows after the first row on/after start_ts.
    `df` is an OHLCV frame with 'datetime' and 'close'. Returns float or None.
    Uses trading rows (not calendar days), which is the correct horizon basis
    for daily bars."""
    if df is None or len(df) == 0:
        return None
    try:
        import datetime as _dt
        start = _dt.datetime.fromtimestamp(float(start_ts))
        dts = list(df["datetime"])
        # find first index on/after the trigger date
        start_idx = None
        for i, d in enumerate(dts):
            dd = d.to_pydatetime() if hasattr(d, "to_pydatetime") else d
            if getattr(dd, "tzinfo", None) is not None:
                dd = dd.replace(tzinfo=None)
            if dd >= start:
                start_idx = i
                break
        if start_idx is None:
            return None
        target = start_idx + n
        if target >= len(df):
            return None  # horizon hasn't elapsed in available data
        return float(df["close"].iloc[target])
    except Exception:
        return None

def evaluate_recommendation(snap, ohlcv_df=None, bench_df=None,
                            horizons=HORIZONS, success_pct=SUCCESS_PCT,
                            failure_pct=FAILURE_PCT):
    """Produce the full outcome record for one recommendation snapshot.

    Returns a dict with per-horizon labels/returns, benchmark-relative labels,
    max upside / max drawdown since signal, duration, current return, and a
    realized 'profitable' flag (based on the longest elapsed horizon)."""
    entry = snap.get("entry_price", 0) or 0
    trig = snap.get("triggered_at", 0) or 0
    cur = snap.get("current_price", entry) or entry
    out = {
        "ticker": snap.get("ticker", ""),
        "category": snap.get("category", ""),
        "entry_price": round(entry, 2),
        "current_price": round(cur, 2),
        "triggered_at": trig,
        "age": _humanize_age(trig),
        "duration_days": round(max(0, (time.time() - trig)) / 86400, 1) if trig else 0,
        "current_return_pct": round((cur - entry) / entry * 100, 2) if entry else None,
        "horizons": {},
    }
    # Max upside / drawdown since signal (from snapshot running extremes)
    mx = snap.get("max_price", cur); mn = snap.get("min_price", cur)
    out["max_upside_pct"] = round((mx - entry) / entry * 100, 2) if entry else None
    out["max_drawdown_pct"] = round((mn - entry) / entry * 100, 2) if entry else None

    realized_pct = None  # return at the longest elapsed horizon
    for h in horizons:
        price_h = _close_n_trading_days_after(ohlcv_df, trig, h) if ohlcv_df is not None else None
        ret = round((price_h - entry) / entry * 100, 2) if (price_h and entry) else None
        bench_ret = None
        if bench_df is not None:
            bprice0 = _close_n_trading_days_after(bench_df, trig, 0)
            bprice_h = _close_n_trading_days_after(bench_df, trig, h)
            if bprice0 and bprice_h:
                bench_ret = round((bprice_h - bprice0) / bprice0 * 100, 2)
        out["horizons"][h] = {
            "price": round(price_h, 2) if price_h else None,
            "return_pct": ret,
            "label": _label_return(ret, success_pct, failure_pct),
            "bench_return_pct": bench_ret,
            "rel_label": _label_vs_benchmark(ret, bench_ret),
        }
        if ret is not None:
            realized_pct = ret  # keep the longest elapsed horizon's return
    out["realized_return_pct"] = realized_pct
    out["profitable"] = (realized_pct is not None and realized_pct > 0)
    out["realized_label"] = _label_return(realized_pct, success_pct, failure_pct)
    return out

def category_hit_rates(evaluations, horizon=5):
    """Aggregate hit-rate (% success) by category at a given horizon over a
    list of evaluate_recommendation() results."""
    agg = {}
    for ev in evaluations:
        cat = ev.get("category", "?")
        hz = ev.get("horizons", {}).get(horizon, {})
        label = hz.get("label", "pending")
        if label == "pending":
            continue
        a = agg.setdefault(cat, {"n": 0, "wins": 0, "losses": 0, "neutral": 0})
        a["n"] += 1
        if label == "success": a["wins"] += 1
        elif label == "failure": a["losses"] += 1
        else: a["neutral"] += 1
    for cat, a in agg.items():
        a["hit_rate"] = round(a["wins"] / a["n"] * 100, 1) if a["n"] else 0.0
    return agg
