"""signal_engine.py — bulk event recording + forward-horizon outcome measurement."""
import pandas as pd
import pytest
import signal_engine as se


@pytest.fixture
def hist(tmp_path, monkeypatch):
    """Isolate the signal-history store to a temp file and start it empty."""
    p = tmp_path / "history.json"
    monkeypatch.setattr(se, "SIGNAL_HISTORY_PATH", str(p))
    se._write_json(str(p), [])
    return str(p)


def _write_counter(monkeypatch, path):
    """Wrap _write_json to count writes to `path` (proves bulk does ONE write)."""
    calls = {"n": 0}
    orig = se._write_json
    def counting(p, data):
        if p == path:
            calls["n"] += 1
        return orig(p, data)
    monkeypatch.setattr(se, "_write_json", counting)
    return calls


def test_bulk_single_write_dedup_and_unique_ids(hist, monkeypatch):
    writes = _write_counter(monkeypatch, hist)
    specs = [dict(ticker=f"T{i}", category="Momentum Leaders", score=80, price=10.0 + i,
                  score_components={"x": i}, recommendation="BUY") for i in range(40)]
    specs.append(dict(ticker="T0", category="Momentum Leaders", score=99,
                      score_components={}, price=11.0))                  # dup key -> skipped
    specs.append(dict(ticker="T0", category="Breakout Watch", score=88,
                      score_components={}, price=12.0))                  # new cat -> kept

    added = se.record_signal_events_bulk(specs)
    events = se._read_json(hist, [])
    ids = [e["id"] for e in events]

    assert len(added) == 41                       # 40 unique + 1 second-category; dup skipped
    assert len(events) == 41
    assert writes["n"] == 1                        # the whole batch is ONE file write
    assert len(ids) == len(set(ids))               # ids unique (ms + counter)
    assert sum(1 for e in events if e["ticker"] == "T0") == 2


def test_bulk_rerun_is_fully_deduped(hist, monkeypatch):
    specs = [dict(ticker="AAA", category="Momentum Leaders", score=80,
                  score_components={}, price=10.0)]
    assert len(se.record_signal_events_bulk(specs)) == 1
    writes = _write_counter(monkeypatch, hist)
    assert se.record_signal_events_bulk(specs) == []   # 20h-deduped against existing
    assert writes["n"] == 0                            # nothing new -> no write


def test_bulk_skips_malformed_specs(hist):
    added = se.record_signal_events_bulk([
        None, {}, {"ticker": "X"}, {"category": "Y"},
        {"ticker": "BAD", "category": "Momentum Leaders"},   # passes filter, missing score/price
        dict(ticker="Z", category="Momentum Leaders", score=70, score_components={}, price=5.0),
    ])
    assert len(added) == 1 and added[0]["ticker"] == "Z"   # only the complete spec recorded


def test_build_signal_event_shape():
    ev = se._build_signal_event("AAA", "Momentum Leaders", 80, {"Momentum": 20}, 10.0)
    assert ev["ticker"] == "AAA" and ev["trigger_price"] == 10.0
    assert ev["lifecycle_stage"] == "candidate"
    assert ev["outcomes"]["label"] == "pending"
    assert all(ev["outcomes"][k] is None for k in
               ("1d_pct", "3d_pct", "5d_pct", "10d_pct", "20d_pct"))


def test_update_outcomes_measures_forward_from_trigger(hist):
    """The horizon returns (1d/3d/5d/10d/20d) must be measured n bars AFTER the
    trigger bar — not from the n most-recent bars (the bug this guards against)."""
    dates = pd.bdate_range(end=pd.Timestamp("2026-06-26"), periods=30)
    trig = 18                                   # 11 forward bars exist (idx 18..29)
    closes = [100.0 + (i - trig) for i in range(30)]   # trigger close=100; +k bars => 100+k
    df = pd.DataFrame({"datetime": dates, "close": closes})

    se._write_json(hist, [{
        "id": "T1", "ticker": "TEST", "category": "X",
        "triggered_at": dates[trig].to_pydatetime().isoformat(),
        "trigger_price": 100.0, "outcomes": {},
    }])
    se.update_signal_outcomes(lambda ticker, days: df.copy())
    out = se._read_json(hist, [])[0]["outcomes"]

    assert out["1d_pct"] == pytest.approx(1.0)
    assert out["3d_pct"] == pytest.approx(3.0)
    assert out["5d_pct"] == pytest.approx(5.0)
    assert out["10d_pct"] == pytest.approx(10.0)
    assert out.get("20d_pct") is None                   # 20 bars not elapsed yet (unfilled)
    assert out["current_pct"] == pytest.approx(11.0)    # last bar = 111
    assert out["max_upside"] == pytest.approx(11.0)
    assert out["max_drawdown"] == pytest.approx(0.0)    # min over [trig:] is the trigger bar
    assert out["1d_pct"] != out["current_pct"]          # old bug would make these equal
