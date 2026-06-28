"""market_utils.py — market-hours status + countdown formatting (pure)."""
import market_utils as mu


def test_fmt_countdown():
    assert mu._fmt_countdown(0) == "00:00:00"
    assert mu._fmt_countdown(-5) == "00:00:00"            # clamped at 0
    assert mu._fmt_countdown(65) == "00:01:05"
    assert mu._fmt_countdown(3661) == "01:01:01"
    assert mu._fmt_countdown(90061) == "1d 01:01:01"      # 1d 1h 1m 1s


def test_fmt_mktcap():
    assert mu.fmt_mktcap(2.45e12) == "$2.45T"
    assert mu.fmt_mktcap(50.2e9) == "$50.2B"
    assert mu.fmt_mktcap(850e6) == "$850M"
    assert mu.fmt_mktcap(0) == "N/A" and mu.fmt_mktcap(None) == "N/A" and mu.fmt_mktcap("x") == "N/A"


def test_fmt_money():
    assert mu.fmt_money(2e9) == "~$2.0B"
    assert mu.fmt_money(2.5e6) == "~$2.5M"
    assert mu.fmt_money(500e3) == "~$500K"
    assert mu.fmt_money(50) == "~$50"


def test_fmt_pct():
    assert mu.fmt_pct(1.2) == "+1.20%"
    assert mu.fmt_pct(-3.4) == "-3.40%"
    assert mu.fmt_pct(0) == "+0.00%"                 # never "+-..."
    assert mu.fmt_pct(5.5, dp=1) == "+5.5%"
    assert mu.fmt_pct(5.5, signed=False) == "5.50%"
    assert mu.fmt_pct("x") == "—"


def test_market_status_shape_and_invariants():
    ms = mu.market_status()
    assert set(ms) == {"state", "label", "target", "seconds"}
    assert ms["state"] in ("open", "pre", "after", "closed")
    assert ms["target"] in ("opens", "closes")
    assert isinstance(ms["seconds"], int) and ms["seconds"] >= 0
    # when open the next event is the close; otherwise it's an open
    assert ms["target"] == ("closes" if ms["state"] == "open" else "opens")
