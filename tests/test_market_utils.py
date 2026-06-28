"""market_utils.py — market-hours status + countdown formatting (pure)."""
import market_utils as mu


def test_fmt_countdown():
    assert mu._fmt_countdown(0) == "00:00:00"
    assert mu._fmt_countdown(-5) == "00:00:00"            # clamped at 0
    assert mu._fmt_countdown(65) == "00:01:05"
    assert mu._fmt_countdown(3661) == "01:01:01"
    assert mu._fmt_countdown(90061) == "1d 01:01:01"      # 1d 1h 1m 1s


def test_market_status_shape_and_invariants():
    ms = mu.market_status()
    assert set(ms) == {"state", "label", "target", "seconds"}
    assert ms["state"] in ("open", "pre", "after", "closed")
    assert ms["target"] in ("opens", "closes")
    assert isinstance(ms["seconds"], int) and ms["seconds"] >= 0
    # when open the next event is the close; otherwise it's an open
    assert ms["target"] == ("closes" if ms["state"] == "open" else "opens")
