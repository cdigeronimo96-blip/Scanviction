"""perf_eval.py — pure performance math + the historical horizon-labeling framework."""
import time

import pandas as pd
import pytest

import perf_eval as pe


def _df(start="2025-01-02", n=15, base=100.0, step=1.0):
    """OHLCV-ish frame: business days from `start`, close = base + i*step."""
    dates = pd.bdate_range(start=start, periods=n)
    return pd.DataFrame({"datetime": dates, "close": [base + i * step for i in range(n)]})


# ── compute_performance ──────────────────────────────────────────────────────
def test_compute_performance_basic():
    p = pe.compute_performance(100.0, 110.0, 1000.0)
    assert p == {"pct": 10.0, "shares": 10.0, "invested": 1000.0,
                 "current_value": 1100.0, "gain": 100.0}

def test_compute_performance_loss_and_guard():
    assert pe.compute_performance(100.0, 90.0, 1000.0)["gain"] == -100.0
    assert pe.compute_performance(0, 100.0) is None        # entry<=0 -> None
    assert pe.compute_performance("x", 1.0) is None         # malformed -> None


# ── _humanize_age ────────────────────────────────────────────────────────────
def test_humanize_age():
    now = time.time()
    assert pe._humanize_age(now - 90) == "1m ago"
    assert pe._humanize_age(now - 3700) == "1h ago"
    assert pe._humanize_age(now - 90000) == "1d ago"
    assert pe._humanize_age("bad") == ""


# ── label helpers ────────────────────────────────────────────────────────────
def test_label_return_boundaries():
    assert pe._label_return(None) == "pending"
    assert pe._label_return(3.0) == "success"      # >= SUCCESS_PCT
    assert pe._label_return(2.99) == "neutral"
    assert pe._label_return(-3.0) == "failure"     # <= -FAILURE_PCT
    assert pe._label_return(-2.99) == "neutral"

def test_label_vs_benchmark():
    assert pe._label_vs_benchmark(None, 1.0) == "pending"
    assert pe._label_vs_benchmark(5.0, 1.0) == "outperform"   # diff 4 > margin 1
    assert pe._label_vs_benchmark(1.0, 5.0) == "underperform"
    assert pe._label_vs_benchmark(2.0, 1.5) == "inline"        # diff 0.5 within margin


# ── _close_n_trading_days_after ──────────────────────────────────────────────
def test_close_n_trading_days_after_uses_trading_rows():
    df = _df(n=15)                                   # close = 100,101,...,114
    trig = df["datetime"].iloc[0].timestamp()
    assert pe._close_n_trading_days_after(df, trig, 0) == 100.0
    assert pe._close_n_trading_days_after(df, trig, 5) == 105.0
    assert pe._close_n_trading_days_after(df, trig, 30) is None   # not elapsed
    assert pe._close_n_trading_days_after(None, trig, 1) is None


# ── evaluate_recommendation (full record) ────────────────────────────────────
def test_evaluate_recommendation_horizons_and_labels():
    df = _df(n=15)                                   # stock close 100..114
    bench = _df(n=15, base=200.0, step=0.5)          # SPY-ish, slow rise
    trig = df["datetime"].iloc[0].timestamp()
    snap = {"ticker": "AAA", "category": "Momentum", "entry_price": 100.0,
            "current_price": 114.0, "triggered_at": trig,
            "max_price": 120.0, "min_price": 98.0}

    out = pe.evaluate_recommendation(snap, df, bench)
    hz = out["horizons"]
    assert hz[1]["return_pct"] == 1.0 and hz[1]["label"] == "neutral"
    assert hz[3]["return_pct"] == 3.0 and hz[3]["label"] == "success"
    assert hz[5]["return_pct"] == 5.0 and hz[5]["label"] == "success"
    assert hz[30]["return_pct"] is None and hz[30]["label"] == "pending"   # not elapsed
    # vs benchmark at h=5: stock +5% vs SPY +~1.25% -> outperform
    assert hz[5]["rel_label"] == "outperform"
    # max upside/drawdown come from snapshot extremes
    assert out["max_upside_pct"] == 20.0 and out["max_drawdown_pct"] == -2.0
    # realized = longest elapsed horizon (h=10 -> 10%)
    assert out["realized_return_pct"] == 10.0 and out["profitable"] is True
    assert out["realized_label"] == "success"


def test_evaluate_recommendation_no_prices_is_pending():
    out = pe.evaluate_recommendation({"entry_price": 100.0, "current_price": 100.0,
                                      "triggered_at": time.time()})
    assert all(h["label"] == "pending" for h in out["horizons"].values())
    assert out["profitable"] is False


# ── category_hit_rates ───────────────────────────────────────────────────────
def test_category_hit_rates():
    evals = [
        {"category": "A", "horizons": {5: {"label": "success"}}},
        {"category": "A", "horizons": {5: {"label": "failure"}}},
        {"category": "A", "horizons": {5: {"label": "success"}}},
        {"category": "B", "horizons": {5: {"label": "pending"}}},   # excluded
    ]
    hr = pe.category_hit_rates(evals, horizon=5)
    assert hr["A"]["n"] == 3 and hr["A"]["wins"] == 2
    assert hr["A"]["hit_rate"] == 66.7
    assert "B" not in hr                                            # only pending -> dropped
