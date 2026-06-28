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
