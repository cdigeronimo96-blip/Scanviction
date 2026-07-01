"""Bulk directional sentiment: _poly_bulk_sent merges the backfilled direction; the backfill
no-ops safely when disabled or when there's no buzz. (Network resolver itself isn't exercised —
that needs live news; here we verify the wiring/contract.)"""


def test_poly_bulk_sent_merges_direction(app):
    buzz = {"AAPL": {"mentions": 50}}
    s = app._poly_bulk_sent("AAPL", buzz, {"AAPL": {"bull": 78, "bear": 22}})
    assert s["bull"] == 78 and s["bear"] == 22 and s["msgs"] == 50   # direction filled, volume kept

    s2 = app._poly_bulk_sent("AAPL", buzz, {})                       # no resolved direction
    assert s2["bull"] == 50 and s2["bear"] == 50 and s2["msgs"] == 50  # stays neutral

    s3 = app._poly_bulk_sent("TSLA", {}, {"TSLA": {"bull": 30, "bear": 70}})  # direction but no buzz row
    assert s3["bull"] == 30 and s3["msgs"] == 0


def test_bulk_sent_map_gating(app, monkeypatch):
    monkeypatch.setattr(app, "BULK_SENT_ENABLED", False)
    assert app._bulk_sent_map({"AAPL": {"mentions": 99}}) == {}      # disabled -> no fetches
    monkeypatch.setattr(app, "BULK_SENT_ENABLED", True)
    assert app._bulk_sent_map({}) == {}                             # no buzz -> nothing to resolve


def test_direction_lifts_the_sentiment_score(app):
    """A buzzed name with bullish direction should score MORE sentiment than the neutral bulk case."""
    from scoring import compute_scores
    import pandas as pd
    df = pd.DataFrame({"close": [10 + i * 0.1 for i in range(60)],
                       "high": [10.2 + i * 0.1 for i in range(60)],
                       "low": [9.8 + i * 0.1 for i in range(60)],
                       "volume": [1_000_000] * 60})
    bull = {"bull": 78, "bear": 22, "msgs": 60}
    neutral = {"bull": 50, "bear": 50, "msgs": 60}
    sc_bull = compute_scores(df, {}, bull)[1].get("Sentiment", 0)
    sc_neu = compute_scores(df, {}, neutral)[1].get("Sentiment", 0)
    assert sc_bull > sc_neu
