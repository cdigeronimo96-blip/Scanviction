"""MarketSignalPro — design-system color palette (extracted from app.py).

Pure constants, no imports. Centralized so app.py and the logic modules (e.g.
advice.py) share ONE source of truth for the brand colors instead of re-hardcoding
hex values. app.py imports these names back, so its (pervasive) UI references are
unchanged.
"""
GOLD   = "#f59e0b"
GOLD2  = "#d97706"
BLUE   = "#6366f1"
GREEN  = "#22c55e"
RED    = "#ef4444"
BG     = "#07090f"
CARD   = "#0d1525"
BORDER = "rgba(255,255,255,0.08)"
