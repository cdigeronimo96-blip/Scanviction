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

# Semantic up/down has two intentional tiers: GREEN/RED are the saturated brand accents
# (borders, fills, the score box); GREEN_TEXT/RED_TEXT are the lighter, on-dark-readable
# variants the design-system classes use for value/label text. AMBER/ORANGE are the
# WATCH/HOLD recommendation colors (previously hardcoded + orphaned from the palette).
GREEN_TEXT = "#4ade80"
RED_TEXT   = "#f87171"
AMBER      = "#fbbf24"
ORANGE     = "#fb923c"
CARD2      = "#080b14"   # darker surface (stat tiles); was an undocumented one-off
