"""scoring.py — indicator reuse must not change any output, plus basic sanity."""
import scoring as S


def test_precompute_equivalence_byte_exact(make_ohlcv):
    """compute_scores / compute_factors must return BYTE-IDENTICAL results whether
    they self-compute indicators or reuse a precompute_indicators(df) bundle. This
    is the regression guard for the warm-loop "compute indicators once" optimization."""
    info = {"beta": 1.2, "sf": 0.1, "mktcap": 1e9}
    sent = {"bull": 62, "msgs": 50}
    for seed in range(25):
        for n in (14, 19, 20, 25, 40, 80, 130):
            df = make_ohlcv(seed, n)
            ind = S.precompute_indicators(df)
            assert S.compute_scores(df, info, sent) == S.compute_scores(df, info, sent, ind=ind)
            assert S.compute_factors(df) == S.compute_factors(df, ind=ind)


def test_precompute_returns_none_for_short_frame(make_ohlcv):
    assert S.precompute_indicators(make_ohlcv(0, 10)) is None
    assert S.precompute_indicators(None) is None


def test_compute_scores_short_frame_is_neutral(make_ohlcv):
    sc, bd, op, risk, conf = S.compute_scores(make_ohlcv(0, 10))
    assert sc == 0 and bd == {} and op == "N/A"


def test_compute_scores_shape_and_bounds(make_ohlcv):
    sc, bd, op, risk, conf = S.compute_scores(
        make_ohlcv(3, 80), {"beta": 1.1, "sf": 0.2, "mktcap": 1e9}, {"bull": 70, "msgs": 40})
    assert 0 <= sc <= 100
    assert isinstance(bd, dict) and bd  # at least one component scored
    assert conf in ("High", "Medium", "Low")


def test_compute_factors_defaults_present(make_ohlcv):
    f = S.compute_factors(make_ohlcv(1, 60))
    # the documented default keys must always exist (callers do no None-checks)
    for k in ("rsi", "trend_align", "macd_state", "vol_ratio", "roc20", "adx", "rel_strength"):
        assert k in f
    assert f["rel_strength"] is None             # filled later by assign_categories
    assert 0.0 <= f["rsi"] <= 100.0
