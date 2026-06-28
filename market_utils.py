"""MarketSignalPro — US market-hours status + countdown formatting (pure).

Extracted from app.py. No Streamlit, no app state. render_market_timer (the UI banner
that consumes these) stays in app.py and imports them. Used both there and by the warm
worker's market-hour-aware sleep cadence.
"""
from datetime import datetime, timedelta


def market_status():
    """US equity market state + countdown to the next open/close.

    Regular session = 9:30–16:00 America/New_York, Mon–Fri (US holidays are not
    modeled — close enough for a UI countdown). Returns a dict:
      state:    'open' | 'pre' | 'after' | 'closed'(weekend)
      label:    human label e.g. 'Market Open'
      target:   'closes' | 'opens'
      seconds:  seconds until that target (for the live countdown)
    Prices are still available when closed (last close); 'live' ticking only
    happens during the open session.
    """
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        # Fallback: assume server clock is ET (countdown still roughly right)
        now = datetime.now()
    wd = now.weekday()  # 0=Mon … 6=Sun
    open_t  = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)

    def _next_weekday_open(frm):
        d = frm
        # advance to next day until it's a weekday
        while True:
            d = (d + timedelta(days=1)).replace(hour=9, minute=30, second=0, microsecond=0)
            if d.weekday() < 5:
                return d

    is_weekend = wd >= 5
    if is_weekend:
        nxt = _next_weekday_open(now)
        return {"state": "closed", "label": "Weekend · Market Closed",
                "target": "opens", "seconds": int((nxt - now).total_seconds())}
    if now < open_t:
        return {"state": "pre", "label": "Pre-Market",
                "target": "opens", "seconds": int((open_t - now).total_seconds())}
    if now <= close_t:
        return {"state": "open", "label": "Market Open",
                "target": "closes", "seconds": int((close_t - now).total_seconds())}
    # after close → opens next weekday
    nxt = _next_weekday_open(now)
    return {"state": "after", "label": "After Hours · Market Closed",
            "target": "opens", "seconds": int((nxt - now).total_seconds())}

def _fmt_countdown(t):
    if t < 0: t = 0
    d = t // 86400; h = (t % 86400) // 3600; m = (t % 3600) // 60; sec = t % 60
    return (f"{d}d " if d > 0 else "") + f"{h:02d}:{m:02d}:{sec:02d}"


# ── Canonical value formatters (one rule each — replaces many inline variants) ──
def fmt_mktcap(v):
    """Compact market-cap / large-$ string with consistent tiers: $X.XXT / $X.XB / $XM /
    $XK. Returns 'N/A' for missing/zero. Use everywhere a market cap is shown so a name
    reads the same on a list card and on its detail page."""
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return "N/A"
    if v <= 0:        return "N/A"
    if v >= 1e12:     return f"${v/1e12:.2f}T"
    if v >= 1e9:      return f"${v/1e9:.1f}B"
    if v >= 1e6:      return f"${v/1e6:.0f}M"
    return f"${v/1e3:.0f}K"

def fmt_money(v):
    """Compact dollar amount for smaller sums (e.g. insider buy value): ~$X.XB / ~$X.XM /
    ~$XK / ~$X. Returns 'N/A' for non-numeric."""
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return "N/A"
    if v >= 1e9:      return f"~${v/1e9:.1f}B"
    if v >= 1e6:      return f"~${v/1e6:.1f}M"
    if v >= 1e3:      return f"~${v/1e3:.0f}K"
    return f"~${v:.0f}"

def fmt_pct(v, dp=2, signed=True):
    """Percent string with fixed decimals; signed=True always shows the sign (+1.20% /
    -3.40%) so a negative 'top mover' never renders as '+-1.2%'. Returns '—' for non-numeric."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "—"
    return f"{v:+.{dp}f}%" if signed else f"{v:.{dp}f}%"
