"""advice.py — recommendation label decision tree, risk color, insight badges (pure)."""
import pandas as pd

import advice
from theme import GOLD, GREEN, RED


def _rec(sc, bd, info=None):
    return advice.get_recommendation(sc, bd, info)


def test_recommendation_strong_buy():
    label, color, _ = _rec(70, {"Trend": 15, "Momentum": 15, "Volume": 12, "MACD": 10, "Squeeze": 0})
    assert label == "🟢 STRONG BUY" and color == GREEN

def test_recommendation_plain_buy():
    label, color, _ = _rec(70, {"Trend": 15, "Momentum": 15, "Volume": 5, "MACD": 5, "Squeeze": 0})
    assert label == "🟢 BUY" and color == GREEN

def test_recommendation_squeeze_via_breakdown():
    label, color, _ = _rec(70, {"Trend": 15, "Momentum": 15, "Squeeze": 8})
    assert label == "💥 SQUEEZE BUY" and color == GOLD

def test_recommendation_squeeze_via_short_float():
    label, color, _ = _rec(70, {"Trend": 15, "Momentum": 15, "Squeeze": 0}, {"sf": 0.20})
    assert label == "💥 SQUEEZE BUY" and color == GOLD       # sf 20% >= 18

def test_recommendation_buy_and_accumulate():
    # recalibrated (2026-06 backtest): sc>=65 (+confirmation) = BUY; the whole 40–64 technical band
    # is ONE actionable ACCUMULATE tier; a high score with no trend/momentum is NOT actionable.
    assert _rec(70, {"Trend": 15, "Momentum": 15})[0] == "🟢 BUY"
    assert _rec(55, {"Trend": 12, "Momentum": 14})[0] == "🟩 ACCUMULATE"
    assert _rec(45, {"Trend": 10})[0] == "🟩 ACCUMULATE"
    assert _rec(55, {"Momentum": 20})[0] == "🟩 ACCUMULATE"        # strong momentum, weak trend
    assert _rec(45, {"Volume": 4})[0] == "🟡 WATCH"                # 40+ but no trend/momentum

def test_recommendation_watch_and_avoid():
    assert _rec(35, {})[0] == "🟡 WATCH"                            # 30–39 band
    avoid = _rec(10, {})
    assert avoid[0] == "🔴 AVOID" and avoid[1] == RED


def test_risk_color_known_and_default():
    assert advice.risk_color("High") == "#ef4444"
    assert advice.risk_color("Low") == "#22c55e"
    assert advice.risk_color("nonsense") == "#64748b"        # default


def test_get_insights_shape(make_ohlcv):
    out = advice.get_insights(make_ohlcv(3, 60), {"sf": 0.25, "dtc": 6})
    assert isinstance(out, list) and out                      # produced some badges
    for title, desc, direction, conf in out:                  # each is a 4-tuple
        assert isinstance(title, str) and isinstance(desc, str)
        assert direction in ("bull", "bear", "neu")
        assert conf in ("Low", "Medium", "High")

def test_get_insights_guards():
    assert advice.get_insights(None) == []
    assert advice.get_insights(pd.DataFrame({"close": [1, 2, 3]})) == []   # < 14 rows -> []


def test_get_insights_ind_reuse_is_equivalent(make_ohlcv):
    """Passing a precomputed `ind` must give byte-identical insights to self-computing
    (the detail-page perf optimization shares one indicator pass)."""
    import scoring
    for seed in range(8):
        df = make_ohlcv(seed, 60)
        ind = scoring.precompute_indicators(df)
        info = {"sf": 0.25, "dtc": 6}
        assert advice.get_insights(df, info) == advice.get_insights(df, info, ind=ind)
