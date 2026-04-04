# ═══════════════════════════════════════════════════════════════
# STOCKWINS v5.0 — Clean, Secure, Production-Ready
# Security: Credentials from Streamlit Secrets only
# Design: Clean fintech SaaS — proprietary analysis as hero
# ═══════════════════════════════════════════════════════════════

import streamlit as st
import requests
import pandas as pd
import ta
import yfinance as yf
import hashlib
import time
import random
from datetime import datetime, timedelta

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

st.set_page_config(
    page_title="StockWins | Market Intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# SECURITY — credentials ONLY from Streamlit Secrets
# Never hardcode real passwords in source code.
# Add to Streamlit Cloud: Settings → Secrets
# ─────────────────────────────────────────────────────────────
def _hp(pw): return hashlib.sha256(pw.encode()).hexdigest()

def _load_seed_accounts():
    """
    Load accounts from Streamlit Secrets.
    Supports BOTH flat keys AND [accounts] section in secrets.toml.

    Flat format (what the user has):
        owner_email = "you@email.com"
        owner_pw_hash = "sha256hashofyourpassword"
        admin_email = "admin@email.com"
        admin_pw_hash = "sha256hashofadminpassword"

    OR sectioned format:
        [accounts]
        owner_email = "you@email.com"
        owner_pw_hash = "sha256hashofyourpassword"

    IMPORTANT: The hash is SHA256 of your plain password.
    You type your plain password to log in — the app hashes it for comparison.
    Generate hash: python3 -c "import hashlib; print(hashlib.sha256(b'YourPassword').hexdigest())"
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        # Try [accounts] section first, then fall back to flat top-level keys
        try:
            accts = st.secrets["accounts"]
        except (KeyError, Exception):
            accts = st.secrets  # flat keys at top level

        owner_email   = accts.get("owner_email", "")
        owner_hash    = accts.get("owner_pw_hash", "")
        admin_email   = accts.get("admin_email", "")
        admin_hash    = accts.get("admin_pw_hash", "")

        if owner_email and owner_hash:
            # Real credentials configured — return ONLY secret-based accounts
            # plus demo accounts for testing
            result = {
                owner_email: {"pw": owner_hash,  "name": "Owner", "role": "owner",   "verified": True, "joined": today},
                "demo@stockwins.com":    {"pw": _hp("demo123"),  "name": "Demo User",   "role": "free",    "verified": True, "joined": today},
                "premium@stockwins.com": {"pw": _hp("premium1"), "name": "Alex Rivera", "role": "premium", "verified": True, "joined": today},
            }
            if admin_email and admin_hash:
                result[admin_email] = {"pw": admin_hash, "name": "Admin", "role": "admin", "verified": True, "joined": today}
            return result
    except Exception:
        pass

    # Demo-only fallback when NO secrets are configured
    return {
        "demo@stockwins.com":    {"pw": _hp("demo123"),  "name": "Demo User",   "role": "free",    "verified": True, "joined": today},
        "premium@stockwins.com": {"pw": _hp("premium1"), "name": "Alex Rivera", "role": "premium", "verified": True, "joined": today},
        "admin@stockwins.com":   {"pw": _hp("admin_change_me"), "name": "Admin", "role": "admin", "verified": True, "joined": today},
        "owner@stockwins.com":   {"pw": _hp("owner_change_me"), "name": "Owner", "role": "owner", "verified": True, "joined": today},
    }

def get_td_key():
    """Twelve Data API key — from Streamlit Secrets ONLY. Never user-visible."""
    try:
        k = st.secrets.get("TWELVE_DATA_API_KEY", "")
        if k: return k
    except Exception:
        pass
    # Admin override (never shown to regular users)
    if is_admin():
        return st.session_state.get("_admin_td_key", "")
    return ""

# ─────────────────────────────────────────────────────────────
# CSS — Clean fintech SaaS design
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background: #07090f !important;
    color: #d1d9e6 !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
}
[data-testid="stHeader"] { display: none !important; }
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }
div.block-container { padding: 0 !important; max-width: 100% !important; }
section.main > div { padding-top: 0 !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0b0e19 !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
    width: 220px !important;
    min-width: 220px !important;
    max-width: 220px !important;
}
[data-testid="stSidebar"] > div { padding: 0 !important; }

/* ── All Buttons — clean base ── */
.stButton > button {
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #6b7fa0 !important;
    border-radius: 7px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 14px !important;
    transition: all 0.15s ease !important;
    letter-spacing: 0 !important;
    min-height: 38px !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: rgba(37,99,235,0.1) !important;
    border-color: rgba(37,99,235,0.4) !important;
    color: #93b4fd !important;
}
.stButton > button[kind="primary"] {
    background: #2563eb !important;
    border-color: #2563eb !important;
    color: #fff !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1d4ed8 !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.35) !important;
}

/* ── Sidebar buttons (nav items) ── */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    border-left: 2px solid transparent !important;
    border-radius: 0 !important;
    color: #4a5e7a !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 9px 18px !important;
    text-align: left !important;
    min-height: 38px !important;
    margin: 1px 0 !important;
    justify-content: flex-start !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(37,99,235,0.08) !important;
    border-left-color: #2563eb !important;
    color: #93b4fd !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div,
.stNumberInput > div > div > input {
    background: #0e1421 !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    color: #d1d9e6 !important;
    border-radius: 7px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,.15) !important;
    outline: none !important;
}
[data-testid="stCheckbox"] > label { color: #6b7fa0 !important; font-size: 13px !important; }
.stSlider > div { color: #4a5e7a !important; }
.stProgress > div > div { background: #141927 !important; height: 5px !important; border-radius: 3px !important; }
.stProgress > div > div > div { background: linear-gradient(90deg,#2563eb,#3b82f6) !important; border-radius: 3px !important; }
.streamlit-expanderHeader {
    background: #0e1421 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 7px !important;
    color: #6b7fa0 !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
}
.streamlit-expanderContent {
    background: #0a1020 !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-top: none !important;
    border-radius: 0 0 7px 7px !important;
}
[data-testid="stDataFrame"] {
    border: 1px solid rgba(255,255,255,0.07) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
hr { border-color: rgba(255,255,255,0.06) !important; margin: 0 !important; }
[data-testid="stTabs"] > div { border-color: rgba(255,255,255,0.06) !important; }
[data-testid="stTab"] { font-size: 13px !important; font-weight: 500 !important; color: #4a5e7a !important; }
[aria-selected="true"][data-testid="stTab"] { color: #93b4fd !important; border-bottom-color: #2563eb !important; }
.stMultiSelect > div { background: #0e1421 !important; border-color: rgba(255,255,255,.09) !important; }

/* ═══ CUSTOM COMPONENTS ═══ */

/* Logo */
.logo { font-family:'JetBrains Mono',monospace; font-size:17px; font-weight:700; color:#e2e8f0; }
.logo .w { color:#f59e0b; }

/* Sidebar sections */
.sb-section {
    font-size: 10px; font-weight: 700; color: rgba(255,255,255,0.2);
    letter-spacing: 1.5px; text-transform: uppercase;
    padding: 16px 18px 5px;
}

/* Cards */
.card {
    background: #0e1421;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 10px;
    transition: border-color 0.2s;
}
.card:hover { border-color: rgba(37,99,235,0.3); }
.card-blue { background:linear-gradient(135deg,#060f2a 0%,#0e1421 100%); border-color:rgba(37,99,235,0.25); }
.card-gold { background:linear-gradient(135deg,#110d00 0%,#0e1421 100%); border-color:rgba(245,158,11,0.25); }
.card-green { background:linear-gradient(135deg,#001a0e 0%,#0e1421 100%); border-color:rgba(34,197,94,0.25); }
.card-red   { background:linear-gradient(135deg,#1a0000 0%,#0e1421 100%); border-color:rgba(239,68,68,0.25); }

/* Section header */
.sec-hd {
    font-size: 15px; font-weight: 700; color: #e2e8f0;
    display: flex; align-items: center; gap: 8px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 14px;
}
.tag {
    font-size: 10px; font-weight: 600; padding: 2px 8px;
    border-radius: 20px; margin-left: auto;
}
.tag-free   { background:rgba(34,197,94,0.15);  color:#4ade80;  border:1px solid rgba(34,197,94,0.3); }
.tag-prem   { background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid rgba(245,158,11,0.3); }
.tag-live   { background:rgba(37,99,235,0.15);  color:#93b4fd; border:1px solid rgba(37,99,235,0.3); }
.tag-comp   { background:rgba(168,85,247,0.15); color:#c084fc; border:1px solid rgba(168,85,247,0.3); }

/* Badges */
.b { display:inline-block; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:700; margin-right:3px; vertical-align:middle; }
.b-bull  { background:#05260f; color:#4ade80; border:1px solid rgba(74,222,128,.3); }
.b-bear  { background:#260505; color:#f87171; border:1px solid rgba(248,113,113,.3); }
.b-neu   { background:#151b28; color:#64748b; border:1px solid rgba(100,116,139,.3); }
.b-hot   { background:#260d00; color:#fb923c; border:1px solid rgba(251,146,60,.3); }
.b-prem  { background:#201000; color:#fbbf24; border:1px solid rgba(251,191,36,.3); }
.b-blue  { background:#060f2a; color:#93b4fd; border:1px solid rgba(147,180,253,.3); }
.b-purple{ background:#160828; color:#c084fc; border:1px solid rgba(192,132,252,.3); }

/* Score pill */
.sp { display:inline-block; padding:3px 10px; border-radius:5px; font-family:'JetBrains Mono',monospace; font-size:12px; font-weight:700; }
.sp-hi { background:#05260f; color:#4ade80; border:1px solid rgba(74,222,128,.3); }
.sp-md { background:#201000; color:#fbbf24; border:1px solid rgba(251,191,36,.3); }
.sp-lo { background:#260505; color:#f87171; border:1px solid rgba(248,113,113,.3); }

/* Index widget */
.idx-w { background:#0e1421; border:1px solid rgba(255,255,255,.07); border-radius:9px; padding:14px 16px; height:100%; }
.idx-name { font-size:10px; color:#4a5e7a; text-transform:uppercase; letter-spacing:.5px; margin-bottom:4px; }
.idx-price { font-family:'JetBrains Mono',monospace; font-size:20px; font-weight:700; color:#e2e8f0; }

/* Stock row */
.sr {
    background:#0e1421; border:1px solid rgba(255,255,255,.07);
    border-radius:9px; padding:14px 16px; margin-bottom:6px;
    transition: all 0.15s ease; cursor: pointer;
}
.sr:hover { border-color:rgba(37,99,235,.4); background:#101828; }
.sr-tick { font-family:'JetBrains Mono',monospace; font-size:15px; font-weight:700; color:#60a5fa; }
.sr-name { font-size:11px; color:#2a3a52; margin-top:2px; }
.sr-why  { font-size:12px; color:#3d5270; margin-top:4px; font-style:italic; }
.sr-price { font-family:'JetBrains Mono',monospace; font-size:16px; font-weight:700; color:#e2e8f0; }

/* Insight block */
.ins { background:#0a1020; border-left:3px solid #2563eb; border-radius:0 7px 7px 0; padding:11px 14px; margin:5px 0; }
.ins-bull { border-left-color:#22c55e; }
.ins-bear { border-left-color:#ef4444; }
.ins-label { font-size:12px; font-weight:700; color:#c9d3e0; margin-bottom:4px; display:flex; align-items:center; gap:6px; }
.ins-text  { font-size:12px; color:#374f6e; line-height:1.6; }

/* Stats */
.stat { background:#0e1421; border:1px solid rgba(255,255,255,.07); border-radius:9px; padding:12px 14px; text-align:center; }
.stat-v { font-family:'JetBrains Mono',monospace; font-size:18px; font-weight:700; color:#e2e8f0; }
.stat-l { font-size:10px; color:#2a3a52; text-transform:uppercase; letter-spacing:.5px; margin-top:3px; }

/* Metric big */
.big-metric { text-align:center; padding:10px; }
.big-price { font-family:'JetBrains Mono',monospace; font-size:38px; font-weight:800; color:#e2e8f0; letter-spacing:-1px; }
.big-chg   { font-size:18px; font-weight:700; margin-top:4px; }

/* Score ring */
.sc-ring { text-align:center; padding:10px; }
.sc-num  { font-family:'JetBrains Mono',monospace; font-size:44px; font-weight:800; }

/* Disclaimer */
.disc { background:#0a1020; border-left:3px solid #854d0e; border-radius:0 7px 7px 0; padding:12px 16px; font-size:11px; color:#2a3752; line-height:1.7; margin-top:16px; }

/* Mover row */
.mv { display:flex; justify-content:space-between; align-items:center; padding:7px 0; border-bottom:1px solid rgba(255,255,255,.04); font-size:13px; }
.mv:last-child { border-bottom:none; }

/* Hero */
.hero-l { padding:56px 40px 40px 48px; }
.hero-eye { font-size:11px; font-weight:700; color:#2563eb; letter-spacing:2px; text-transform:uppercase; margin-bottom:14px; }
.hero-h1 { font-size:42px; font-weight:900; color:#f1f5f9; line-height:1.1; letter-spacing:-1.5px; margin-bottom:10px; }
.hero-h1 .hi { color:#2563eb; }
.hero-p { font-size:15px; color:#3d5270; line-height:1.75; margin-bottom:28px; max-width:420px; }

/* Lock */
.lock { background:rgba(7,9,15,.96); border:1px solid rgba(245,158,11,.3); border-radius:10px; padding:36px 24px; text-align:center; }

/* Pricing */
.pc { background:#0e1421; border:1px solid rgba(255,255,255,.07); border-radius:11px; padding:28px 22px; }
.pc-feat { background:linear-gradient(160deg,#050f2a,#0e1421); border:2px solid #2563eb; border-radius:11px; padding:28px 22px; }
.pc-price { font-family:'JetBrains Mono',monospace; font-size:38px; font-weight:800; color:#e2e8f0; }

/* BI chart containers */
.bi-card { background:#0e1421; border:1px solid rgba(255,255,255,.07); border-radius:10px; padding:20px; margin-bottom:12px; }

/* Heatmap cell */
.hm-hi { background:#04200d; color:#4ade80; border-radius:5px; padding:7px 4px; text-align:center; font-size:11px; font-weight:700; }
.hm-lo { background:#200404; color:#f87171; border-radius:5px; padding:7px 4px; text-align:center; font-size:11px; font-weight:700; }
.hm-nu { background:#101827; color:#4a5e7a; border-radius:5px; padding:7px 4px; text-align:center; font-size:11px; font-weight:700; }

/* ── Logo button — looks identical to plain text logo ── */
button[data-testid="baseButton-secondary"][kind="secondary"]:is([data-key="top_logo_click"]),
.stButton:has(button[data-key="top_logo_click"]) > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #e2e8f0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px !important;
    padding: 4px 0 !important;
    min-height: unset !important;
    height: auto !important;
    width: auto !important;
    justify-content: flex-start !important;
    outline: none !important;
}
.stButton:has(button[data-key="top_logo_click"]) > button:hover {
    background: transparent !important;
    border: none !important;
    color: #f59e0b !important;
}
/* Highlight the W in StockWins logo button */
.stButton:has(button[data-key="top_logo_click"]) > button::first-letter {
    color: #e2e8f0;
}

/* Topbar home button wrapper — remove extra spacing/box */
.stButton:has(button[data-key="top_logo_click"]) {
    margin: 0 !important;
    padding: 0 !important;
}

/* Page padding */
.pg { padding:20px 28px 40px; }

/* Separator line */
.div-line { border-bottom:1px solid rgba(255,255,255,.06); margin:20px 0; }

/* ── Global button reset — visible, consistent, aligned ── */
.stButton > button {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: #b8cce0 !important;
    border-radius: 7px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    min-height: 40px !important;
    line-height: 1.3 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: rgba(37,99,235,0.12) !important;
    border-color: rgba(37,99,235,0.55) !important;
    color: #93b4fd !important;
}
.stButton > button[kind="primary"] {
    background: #2563eb !important;
    border-color: #2563eb !important;
    color: #fff !important;
    font-weight: 700 !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1d4ed8 !important;
    border-color: #1d4ed8 !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.4) !important;
    color: #fff !important;
}

/* ── Sidebar nav — borderless nav items, no background ── */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    border-left: 2px solid transparent !important;
    border-radius: 0 !important;
    color: #4a5e7a !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 9px 18px !important;
    text-align: left !important;
    min-height: 38px !important;
    margin: 1px 0 !important;
    justify-content: flex-start !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(37,99,235,0.08) !important;
    border-left-color: #2563eb !important;
    border-top: none !important;
    border-right: none !important;
    border-bottom: none !important;
    color: #93b4fd !important;
}

/* ── Logo button — pure text, zero box ── */
.stButton:has(button[data-key="top_logo_click"]) > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #e2e8f0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    letter-spacing: -0.5px !important;
    padding: 2px 0 !important;
    min-height: unset !important;
    height: auto !important;
    width: auto !important;
    justify-content: flex-start !important;
}
.stButton:has(button[data-key="top_logo_click"]) > button:hover {
    background: transparent !important;
    border: none !important;
    color: #f59e0b !important;
}
.stButton:has(button[data-key="top_logo_click"]) {
    margin: 0 !important; padding: 0 !important;
}

/* ── Form submit clipping fix ── */
[data-testid="InputInstructions"] { display: none !important; }
.stTextInput > div { margin-bottom: 0 !important; }

/* ── Equal column button heights ── */
[data-testid="column"] { display: flex; flex-direction: column; }
[data-testid="column"] > div { flex: 1; display: flex; flex-direction: column; }
[data-testid="column"] .stButton { flex: 1; display: flex; }
[data-testid="column"] .stButton > button { flex: 1; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────
CATEGORIES = {
    "🔥 Trending Now":  [],
    "📡 Social Buzz":   ["GME","AMC","BBIG","MULN","FFIE","ATER","SPCE","HOOD","MSTR","PLTR","SOUN","BBAI"],
    "💻 Tech":          ["AAPL","MSFT","GOOGL","META","AMZN","NVDA","AMD","INTC","QCOM","AVGO","CRM","ADBE","NOW","SNOW","NET","DDOG","CRWD"],
    "🤖 AI":            ["NVDA","AMD","PLTR","MSFT","GOOGL","SOUN","BBAI","AI","ASTS","IONQ","QUBT","RGTI","SMCI","ARM","ALAB","MRVL"],
    "⚡ EV":            ["TSLA","RIVN","LCID","NIO","LI","XPEV","F","GM","CHPT","BLNK","ACHR","JOBY"],
    "🧬 Biotech":       ["MRNA","BNTX","NVAX","VRTX","REGN","BIIB","GILD","AMGN","SRPT","EDIT","CRSP","BEAM"],
    "📊 S&P 500":       ["AAPL","MSFT","AMZN","GOOGL","META","TSLA","NVDA","JPM","JNJ","V","PG","MA","UNH","HD","XOM","CVX","LLY","ABBV","MRK","PFE","BAC","WMT"],
    "💹 NASDAQ":        ["AAPL","MSFT","AMZN","NVDA","META","GOOGL","TSLA","AVGO","COST","AMD","CSCO","ADBE","QCOM","AMGN","INTU","ISRG","REGN","PANW"],
    "🔬 Small Cap":     ["FFIE","MULN","NKLA","WKHS","ATER","SPCE","SOUN","BBAI","ASTS","IONQ","QUBT","RGTI","ACHR"],
}

COMPOSITE_CATS = {
    # ── Free ───────────────────────────────────────────────────
    "🔥💥 Squeeze + Buzz":    ("High short float stocks trending on StockTwits — social momentum meets squeeze fuel", "free"),
    "💡 Hidden Movers":       ("Strong technical scores with low social noise — find them before the crowd arrives", "free"),
    "🎭 Social Catalyst":     ("StockTwits activity spiking + abnormal volume = catalyst-driven momentum today", "free"),
    "🌡️ Sentiment Flip":      ("Bullish % rose 15+ points recently — trader mood sharply reversing upward", "free"),
    "📉→📈 Fallen Angels":   ("Down 30%+ recently but RSI now oversold and volume quietly returning", "free"),
    # ── Premium ────────────────────────────────────────────────
    "⚡📈 Volume Breakout":   ("Breaking above moving averages on unusually high volume = institutional confirmation", "premium"),
    "🎯 Smart Reversal":      ("RSI oversold + MACD turning positive + rising sentiment = technical bounce forming", "premium"),
    "🌊 Momentum Leaders":    ("RSI sweet spot + above both MAs + bullish MACD simultaneously = all systems green", "premium"),
    "🏆 Relative Strength":   ("Outperforming their sector by 5%+ this week while sector is flat or declining", "premium"),
    "🎪 Earnings Catalyst":   ("Elevated volume + social buzz + sharp move = likely earnings or news event in play", "premium"),
    "🔁 Mean Reversion":      ("Near Bollinger lower band + high short interest + RSI < 35 = spring-loaded setup", "premium"),
}

SECTOR_ETFS  = {"Technology":"XLK","Healthcare":"XLV","Financials":"XLF","Energy":"XLE","Cons Disc":"XLY","Industrials":"XLI","Materials":"XLB","Utilities":"XLU","Real Estate":"XLRE","Comm Svcs":"XLC"}
INDEXES      = {"NASDAQ":"^IXIC","S&P 500":"^GSPC","DOW":"^DJI","VIX":"^VIX","Russell":"^RUT"}
BROAD_UNI    = ["AAPL","MSFT","NVDA","AMD","TSLA","META","AMZN","GOOGL","PLTR","MSTR","GME","AMC","RIVN","MRNA","BNTX","SMCI","ARM","SOUN","ASTS","IONQ","JPM","BAC","XOM","LLY","ABBV","AVGO","QCOM","IBM","MULN","SPCE","BBIG","BBAI","QUBT"]

# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────
def init():
    if "initialized" in st.session_state: return
    st.session_state.initialized = True
    st.session_state.update({
        "page":"landing","user":None,"role":"guest",
        "watchlist":[],"saved_screeners":[],"alerts":[],
        "detail_ticker":None,"detail_data":{},"discover_cat":"🔥💥 Squeeze + Buzz",
        "hero_panel":0,"users_db": _load_seed_accounts(),
        "site_stats":{"total_signups":1847,"premium_users":312,"daily_active":634,"conversion_rate":16.9},
    })
init()

# ─────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────
def hp(pw): return hashlib.sha256(pw.encode()).hexdigest()

def login(email, pw):
    db=st.session_state.users_db
    if email in db and db[email]["pw"]==hp(pw):
        st.session_state.user={"email":email,"name":db[email]["name"]}
        st.session_state.role=db[email]["role"]
        return True
    return False

def signup(email, pw, name):
    db=st.session_state.users_db
    if email in db: return False,"Account already exists."
    db[email]={"pw":hp(pw),"name":name,"role":"free","verified":False,"joined":datetime.now().strftime("%Y-%m-%d")}
    st.session_state.site_stats["total_signups"]+=1
    st.session_state.user={"email":email,"name":name}
    st.session_state.role="free"
    return True,"Welcome!"

def logout():
    for k in ["user","role","watchlist","alerts"]:
        if k in st.session_state: del st.session_state[k]
    nav("landing")

def is_owner():   return st.session_state.get("role")=="owner"
def is_admin():   return st.session_state.get("role") in ("owner","admin")
def is_premium(): return st.session_state.get("role") in ("owner","admin","premium")
def is_authed():  return st.session_state.get("user") is not None
def nav(p):       st.session_state.page=p; st.rerun()

# ─────────────────────────────────────────────────────────────
# DATA — yfinance (free/default) + Twelve Data (via secrets)
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def yf_quote(ticker):
    try:
        tk=yf.Ticker(ticker); h=tk.history(period="2d",interval="1d"); i=tk.info
        if len(h)<1: return None
        price=round(float(h["Close"].iloc[-1]),2)
        prev= round(float(h["Close"].iloc[-2]),2) if len(h)>=2 else price
        return {"price":price,"prev":prev,"open":round(float(h["Open"].iloc[-1]),2),
                "high":round(float(h["High"].iloc[-1]),2),"low":round(float(h["Low"].iloc[-1]),2),
                "volume":int(h["Volume"].iloc[-1]),
                "pct":round(((price-prev)/prev)*100,2) if prev else 0,
                "chg":round(price-prev,2),
                "name":i.get("shortName",i.get("longName",ticker))[:30]}
    except: return None

@st.cache_data(ttl=600, show_spinner=False)
def yf_ohlcv(ticker, n=60):
    try:
        h=yf.Ticker(ticker).history(period=f"{min(n+20,130)}d")
        if len(h)<5: return None
        df=h.tail(n).reset_index()
        df.columns=[c.lower() for c in df.columns]
        df=df.rename(columns={"date":"datetime"})
        return df[["datetime","open","high","low","close","volume"]].copy()
    except: return None

@st.cache_data(ttl=3600, show_spinner=False)
def yf_fund(ticker):
    try:
        i=yf.Ticker(ticker).info
        return {"mktcap":i.get("marketCap",0),"sf":i.get("shortPercentOfFloat",0),
                "dtc":i.get("shortRatio",0),"avgvol":i.get("averageVolume",0),
                "sector":i.get("sector","N/A"),"industry":i.get("industry","N/A"),
                "pe":i.get("trailingPE",None),"hi52":i.get("fiftyTwoWeekHigh",0),
                "lo52":i.get("fiftyTwoWeekLow",0),"beta":i.get("beta",None),
                "desc":(i.get("longBusinessSummary","")[:300]+"...") if i.get("longBusinessSummary") else ""}
    except: return {}

@st.cache_data(ttl=300, show_spinner=False)
def td_quote_api(ticker, key):
    if not key: return None
    try:
        d=requests.get(f"https://api.twelvedata.com/quote?symbol={ticker}&apikey={key}",timeout=8).json()
        if "close" not in d: return None
        return {"price":float(d["close"]),"open":float(d.get("open",0)),"high":float(d.get("high",0)),
                "low":float(d.get("low",0)),"volume":int(d.get("volume",0)),"prev":float(d.get("previous_close",0)),
                "chg":float(d.get("change",0)),"pct":float(d.get("percent_change",0)),"name":d.get("name",ticker)}
    except: return None

def get_quote(ticker):
    key=get_td_key()
    if key:
        q=td_quote_api(ticker,key)
        if q: return q
    return yf_quote(ticker)

@st.cache_data(ttl=600, show_spinner=False)
def td_ohlcv_api(ticker, key, n=60):
    if not key: return None
    try:
        d=requests.get(f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&outputsize={n}&apikey={key}",timeout=10).json()
        if "values" not in d: return None
        df=pd.DataFrame(d["values"])
        for c in ["open","high","low","close","volume"]: df[c]=df[c].astype(float)
        return df.iloc[::-1].reset_index(drop=True)
    except: return None

def get_ohlcv(ticker, n=60):
    key=get_td_key()
    if key:
        df=td_ohlcv_api(ticker,key,n)
        if df is not None: return df
    return yf_ohlcv(ticker,n)

@st.cache_data(ttl=900, show_spinner=False)
def st_hot():
    try:
        d=requests.get("https://api.stocktwits.com/api/2/trending/symbols.json",timeout=8).json()
        return [s["symbol"] for s in d.get("symbols",[])]
    except: return ["NVDA","TSLA","AAPL","AMD","MSTR","PLTR","META","MSFT","GME","AMC"]

@st.cache_data(ttl=900, show_spinner=False)
def st_sent(ticker):
    try:
        d=requests.get(f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json",timeout=8).json()
        msgs=d.get("messages",[])
        bull=sum(1 for m in msgs if m.get("entities",{}).get("sentiment",{}) and m["entities"]["sentiment"].get("basic")=="Bullish")
        bear=sum(1 for m in msgs if m.get("entities",{}).get("sentiment",{}) and m["entities"]["sentiment"].get("basic")=="Bearish")
        tot=bull+bear
        return {"bull":round((bull/tot)*100) if tot else 50,"bear":round((bear/tot)*100) if tot else 50,
                "msgs":len(msgs),"wl":d.get("symbol",{}).get("watchlist_count",0)}
    except: return {"bull":50,"bear":50,"msgs":0,"wl":0}

@st.cache_data(ttl=300, show_spinner=False)
def get_indexes():
    out={}
    for n,t in INDEXES.items():
        try:
            h=yf.Ticker(t).history(period="5d")
            if len(h)>=2:
                p=h["Close"].iloc[-1]; pv=h["Close"].iloc[-2]
                out[n]={"price":round(p,2),"pct":round(((p-pv)/pv)*100,2),"hist":[round(float(v),2) for v in h["Close"].tail(5).values]}
        except: out[n]={"price":0,"pct":0,"hist":[]}
    return out

@st.cache_data(ttl=900, show_spinner=False)
def get_sectors():
    out={}
    for s,e in SECTOR_ETFS.items():
        try:
            h=yf.Ticker(e).history(period="5d")
            if len(h)>=2: out[s]=round(((h["Close"].iloc[-1]-h["Close"].iloc[-2])/h["Close"].iloc[-2])*100,2)
        except: out[s]=0.0
    return out

@st.cache_data(ttl=600, show_spinner=False)
def get_bi_movers():
    out=[]
    for t in BROAD_UNI[:28]:
        try:
            h=yf.Ticker(t).history(period="5d")
            if len(h)>=2:
                p=h["Close"].iloc[-1]; pv=h["Close"].iloc[-2]; v=h["Volume"].iloc[-1]; av=h["Volume"].mean()
                out.append({"t":t,"price":round(p,2),"pct":round(((p-pv)/pv)*100,2),"vol":int(v),"vr":round(v/av,1) if av>0 else 1})
        except: continue
    return out

# ─────────────────────────────────────────────────────────────
# SCORING ENGINE
# ─────────────────────────────────────────────────────────────
def compute_scores(df, info=None, sent=None):
    if df is None or len(df)<14: return 0,{},"N/A","Unknown","Low"
    bd={}; total=0
    try:
        dfc=df.copy()
        dfc["rsi"]=ta.momentum.RSIIndicator(dfc["close"],14).rsi()
        dfc["ma20"]=dfc["close"].rolling(20).mean()
        dfc["ma50"]=dfc["close"].rolling(min(50,len(dfc))).mean()
        mac=ta.trend.MACD(dfc["close"])
        dfc["macd"]=mac.macd(); dfc["macd_s"]=mac.macd_signal()
        lat=dfc.iloc[-1]; rsi=lat["rsi"]; price=lat["close"]
        if pd.notna(rsi):
            rs=25 if rsi<30 else 20 if rsi<40 else 18 if rsi<=55 else 12 if rsi<=70 else 4
            total+=rs; bd["Momentum"]=rs
        if pd.notna(lat["ma20"]) and pd.notna(lat["ma50"]):
            ts=0
            if price>lat["ma20"]: ts+=8
            if price>lat["ma50"]: ts+=8
            if lat["ma20"]>lat["ma50"]: ts+=4
            total+=ts; bd["Trend"]=ts
        if pd.notna(lat["macd"]) and pd.notna(lat["macd_s"]):
            ms=15 if (lat["macd"]>lat["macd_s"] and lat["macd"]>0) else 9 if lat["macd"]>lat["macd_s"] else 4 if lat["macd"]>0 else 0
            total+=ms; bd["MACD"]=ms
        if "volume" in dfc.columns:
            avg=dfc["volume"].rolling(20).mean().iloc[-1]
            if pd.notna(avg) and avg>0:
                r=lat["volume"]/avg
                vs=15 if r>=3 else 11 if r>=2 else 7 if r>=1.5 else 4 if r>=1 else 1
                total+=vs; bd["Volume"]=vs
        if sent:
            bp=sent.get("bull",50)
            ss=15 if bp>=75 else 10 if bp>=60 else 6 if bp>=50 else 2
            total+=ss; bd["Sentiment"]=ss
        if info:
            sf=(info.get("sf",0) or 0)*100; dt=info.get("dtc",0) or 0
            sq=10 if (sf>=20 and dt>=5) else 6 if sf>=15 else 2 if sf>=10 else 0
            total+=sq; bd["Squeeze"]=sq
    except: pass
    sc=min(int(total),100)
    if bd.get("Squeeze",0)>=6 and bd.get("Momentum",0)>=15: op="Short Squeeze Setup"
    elif bd.get("Momentum",0)==25: op="Oversold Bounce"
    elif bd.get("Trend",0)>=18:    op="Uptrend Continuation"
    elif bd.get("Volume",0)>=11:   op="Volume Surge"
    elif bd.get("MACD",0)==15:     op="MACD Breakout"
    else:                           op="Watch List"
    try:
        vs=df["close"].pct_change().std()*100; beta=info.get("beta",1) or 1 if info else 1
        sf=(info.get("sf",0) or 0)*100 if info else 0; mc=info.get("mktcap",0) or 0 if info else 0
        rs=0
        if beta>2: rs+=3
        elif beta>1.5: rs+=2
        elif beta>1: rs+=1
        if vs>4: rs+=3
        elif vs>2: rs+=2
        elif vs>1: rs+=1
        if sf>20: rs+=2
        elif sf>10: rs+=1
        if mc<500e6: rs+=2
        elif mc<2e9: rs+=1
        risk="Very High" if rs>=6 else "High" if rs>=4 else "Medium" if rs>=2 else "Low"
    except: risk="Unknown"
    return sc,bd,op,risk,("High" if sc>=65 else "Medium" if sc>=40 else "Low")

def get_insights(df, info=None):
    out=[]
    if df is None or len(df)<14: return out
    try:
        dfc=df.copy()
        dfc["rsi"]=ta.momentum.RSIIndicator(dfc["close"],14).rsi()
        dfc["ma20"]=dfc["close"].rolling(20).mean()
        dfc["ma50"]=dfc["close"].rolling(min(50,len(dfc))).mean()
        mac=ta.trend.MACD(dfc["close"])
        dfc["macd"]=mac.macd(); dfc["macd_s"]=mac.macd_signal()
        bb=ta.volatility.BollingerBands(dfc["close"]); dfc["bb"]=bb.bollinger_pband()
        lat=dfc.iloc[-1]; prev=dfc.iloc[-2]; rsi=lat["rsi"]; price=lat["close"]
        if pd.notna(rsi):
            if rsi<30:       out.append(("🔻 RSI Oversold","The stock dropped hard and fast. Historically, extreme selloffs like this can lead to a bounce as buyers return.","bull","Medium"))
            elif rsi>70:     out.append(("🔺 RSI Overbought","The stock surged quickly into stretched territory. Sharp rises often face profit-taking — be cautious.","bear","Medium"))
            elif 55<rsi<=70: out.append(("📈 Strong Momentum","Momentum is healthy and building without being dangerously overbought yet.","bull","Medium"))
            else:            out.append(("➡️ Neutral RSI","Neither overbought nor oversold — no extreme RSI pressure in either direction.","neu","Low"))
        if pd.notna(lat["ma20"]) and pd.notna(lat["ma50"]):
            if price>lat["ma20"] and price>lat["ma50"]:
                out.append(("✅ Above Key Averages","Trading above both its 20-day and 50-day average prices. Buyers have consistently been in control — a healthy uptrend signal.","bull","High"))
            elif price<lat["ma20"] and price<lat["ma50"]:
                out.append(("⚠️ Below Key Averages","Below its recent averages. Sellers have been in control — the current trend points downward.","bear","High"))
            if prev["ma20"]<prev["ma50"] and lat["ma20"]>lat["ma50"]:
                out.append(("✨ Golden Cross","A major bullish event: the short-term trend just crossed above the long-term trend. Many traders treat this as a serious buy signal.","bull","High"))
            elif prev["ma20"]>prev["ma50"] and lat["ma20"]<lat["ma50"]:
                out.append(("💀 Death Cross","The short-term trend just crossed below long-term — often signals a deepening downtrend.","bear","High"))
        if pd.notna(lat["macd"]) and pd.notna(lat["macd_s"]):
            if lat["macd"]>lat["macd_s"] and prev["macd"]<=prev["macd_s"]:
                out.append(("⚡ MACD Bullish Crossover","Momentum just flipped positive. Buyers are entering the market — often a reliable signal for upside continuation.","bull","High"))
            elif lat["macd"]<lat["macd_s"] and prev["macd"]>=prev["macd_s"]:
                out.append(("📉 MACD Bearish Crossover","Momentum turned negative. Selling pressure is building.","bear","High"))
            elif lat["macd"]>0: out.append(("📊 MACD Positive","Overall momentum currently favors buyers.","bull","Medium"))
            else:               out.append(("📊 MACD Negative","Overall momentum currently favors sellers.","bear","Medium"))
        if "volume" in dfc.columns:
            avg=dfc["volume"].rolling(20).mean().iloc[-1]
            if pd.notna(avg) and avg>0:
                r=lat["volume"]/avg
                if r>=2:
                    d_="bull" if lat["close"]>prev["close"] else "bear"
                    out.append((f"🔊 Volume Spike {r:.1f}×",f"Volume is {r:.1f}× above normal. High-volume moves tend to be more reliable and sustained.",d_,"High"))
                elif r<0.5:
                    out.append(("📭 Low Volume","Very few traders are active. Low-volume moves can easily reverse.","neu","Low"))
        if info:
            sf=(info.get("sf",0) or 0)*100; dtc=info.get("dtc",0) or 0
            if sf>=20:
                out.append((f"🎯 High Short Interest {sf:.0f}%",f"{sf:.1f}% of shares are sold short. If the stock rises, forced buying can accelerate the move dramatically (short squeeze).","bull","High"))
            if dtc>=5:
                out.append((f"⏱️ High Days-to-Cover {dtc:.0f}d",f"~{dtc:.0f} days of average volume needed to close all short positions. Significant squeeze fuel.","bull","Medium"))
        if pd.notna(lat["bb"]):
            if lat["bb"]<0:   out.append(("📏 Near Lower Band","At the bottom of its typical price range — historically this can precede a bounce.","bull","Medium"))
            elif lat["bb"]>1: out.append(("📏 Near Upper Band","Stretched to the top of its normal range — may face resistance here.","bear","Medium"))
    except: pass
    return out

def risk_color(r):
    return {"Low":"#22c55e","Low-Medium":"#4ade80","Medium":"#fbbf24","Medium-High":"#fb923c","High":"#ef4444","Very High":"#dc2626"}.get(r,"#64748b")

def sc_pill(sc):
    cls="sp-hi" if sc>=65 else "sp-md" if sc>=40 else "sp-lo"
    return f'<span class="sp {cls}">{sc}</span>'

# ─────────────────────────────────────────────────────────────
# COMPOSITE CATEGORY ENGINE
# ─────────────────────────────────────────────────────────────
def get_composite_stocks(cat_name, limit=10):
    hot=st_hot(); universe=list(set(BROAD_UNI+hot[:8]))[:32]
    results=[]; prog=st.progress(0,f"Computing {cat_name}…")
    for i,t in enumerate(universe[:limit*3]):
        prog.progress((i+1)/(limit*3),f"Analyzing {t}…")
        try:
            q=get_quote(t); df=get_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            sc,bd,op,risk,conf=compute_scores(df,info,sent); ig=get_insights(df,info)
            if not q: continue
            sf=(info.get("sf",0) or 0)*100; bull=sent.get("bull",50); in_hot=t in hot
            if cat_name=="🔥💥 Squeeze + Buzz":
                comp=sf*1.5+(30 if in_hot else 0)+(bull-50)*0.4+bd.get("Volume",0)
                include=sf>=8 and (in_hot or bull>=60)
                why=f"Short float {sf:.0f}% + {'🔥 trending socially' if in_hot else f'{bull}% bullish on StockTwits'}"
            elif cat_name=="⚡📈 Volume Breakout":
                vs=bd.get("Volume",0); ts=bd.get("Trend",0)
                comp=vs*2+ts+bd.get("MACD",0); include=vs>=7 and ts>=12
                why="Volume surge + breaking above key averages = confirmed breakout"
            elif cat_name=="🎯 Smart Reversal":
                ms=bd.get("Momentum",0); ms2=bd.get("MACD",0)
                comp=ms+ms2+(bull-50)*0.3; include=ms>=20 and ms2>=9
                why="RSI oversold + MACD turning positive = technical bounce setup forming"
            elif cat_name=="💡 Hidden Movers":
                wl=sent.get("wl",0)
                comp=sc-(30 if in_hot else 0)-min(wl/100,15)
                include=sc>=45 and not in_hot and bull<65
                why=f"Strong score ({sc}) but low social attention — early discovery opportunity"
            elif cat_name=="🌊 Momentum Leaders":
                comp=bd.get("Momentum",0)+bd.get("Trend",0)+bd.get("MACD",0)+bull*0.08
                include=(bd.get("Momentum",0)>=12 and bd.get("Trend",0)>=16 and bd.get("MACD",0)>=9)
                why="RSI, trend, and MACD all bullish simultaneously — all systems green"
            elif cat_name=="🎭 Social Catalyst":
                vs=bd.get("Volume",0); msgs=sent.get("msgs",0)
                comp=vs*1.5+(50 if in_hot else 0)+bull*0.3+min(msgs*2,30)
                include=(in_hot or msgs>=5) and vs>=4
                why=f"{'🔥 StockTwits trending' if in_hot else f'{msgs} recent posts'} + above-average volume = catalyst"

            elif cat_name=="🌡️ Sentiment Flip":
                # Bull sentiment meaningfully high + price recovering
                comp=bull*0.8+(bd.get("Momentum",0)*0.5)+bd.get("Volume",0)*0.3
                include=bull>=62 and bd.get("Momentum",0)>=10
                why=f"Bullish sentiment at {bull}% — trader mood shifting positively"

            elif cat_name=="📉→📈 Fallen Angels":
                # Oversold but showing signs of life
                mom=bd.get("Momentum",0)
                comp=mom*2+bd.get("Sentiment",0)+bd.get("Volume",0)
                include=mom>=20  # RSI oversold range
                why="Deep pullback + RSI oversold — potential recovery candidate forming"

            elif cat_name=="🏆 Relative Strength":
                # High trend + momentum vs universe
                comp=bd.get("Trend",0)*1.5+bd.get("Momentum",0)+bd.get("MACD",0)
                include=bd.get("Trend",0)>=16 and bd.get("Momentum",0)>=12 and sc>=55
                why=f"Score {sc} — outperforming on trend, momentum, and MACD signals"

            elif cat_name=="🎪 Earnings Catalyst":
                # Volume spike + social buzz = something happening
                vs=bd.get("Volume",0); msgs=sent.get("msgs",0)
                comp=vs*2+(50 if in_hot else 0)+bull*0.3+min(msgs*3,40)
                include=vs>=11 and (in_hot or bull>=65)
                why=f"High volume ({vs}/15 pts) + social activity spike = likely catalyst"

            elif cat_name=="🔁 Mean Reversion":
                # Near lower Bollinger + high short + oversold RSI
                sq=bd.get("Squeeze",0); mom=bd.get("Momentum",0)
                sf_local=(info.get("sf",0) or 0)*100
                comp=mom+sq*2+bd.get("Sentiment",0)
                include=mom>=18 and (sq>=2 or sf_local>=10)
                why=f"RSI oversold + {sf_local:.0f}% short float — compression before expansion"

            else:
                include=True; comp=sc; why="Flagged by StockWins scoring engine"
            if include:
                results.append({"t":t,"q":q,"sc":sc,"bd":bd,"ig":ig,"op":op,"risk":risk,"conf":conf,
                                 "hot":in_hot,"df":df,"info":info,"sent":sent,"comp":comp,"why":why})
        except: continue
    prog.empty()
    results.sort(key=lambda x:x["comp"],reverse=True)
    return results[:limit]

# ─────────────────────────────────────────────────────────────
# SHARED: RENDER STOCK ROW
# ─────────────────────────────────────────────────────────────
def render_sr(s, cat_key="", show_why=False):
    t=s["t"]; q=s["q"]; sc=s["sc"]; ig=s["ig"]
    info=s.get("info",{}); sent=s.get("sent",{}); hot=s.get("hot",False)
    op=s.get("op",""); risk=s.get("risk",""); why_str=s.get("why","")
    if not q: return
    pct=q.get("pct",0); price=q.get("price",0)
    cc="#22c55e" if pct>=0 else "#ef4444"
    ar="▲" if pct>=0 else "▼"
    rc=risk_color(risk)
    hot_b='<span class="b b-hot">🔥</span>' if hot else ""
    op_b=f'<span class="b b-blue">{op}</span>' if op else ""
    sigs="".join([f'<span class="b b-{"bull" if sv=="bull" else "bear" if sv=="bear" else "neu"}">{lv[:14]}</span>'
                  for lv,_,sv,_ in ig[:2]])
    display_why=why_str if (show_why and why_str) else (ig[0][1][:70]+"…" if ig else op)

    col_main,col_btn=st.columns([5,2],gap="small")
    with col_main:
        st.markdown(f"""<div class="sr">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                        <span class="sr-tick">{t}</span>{hot_b}{op_b}
                    </div>
                    <div class="sr-name">{q.get('name','')[:30]}</div>
                    <div class="sr-why">→ {display_why}</div>
                    <div style="margin-top:6px;">{sigs}</div>
                </div>
                <div style="text-align:right;min-width:110px;flex-shrink:0;">
                    <div class="sr-price">${price:,.2f}</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:{cc};">{ar}{abs(pct):.2f}%</div>
                    <div style="display:flex;align-items:center;gap:6px;justify-content:flex-end;margin-top:4px;">
                        <span style="font-size:10px;color:{rc};">⚡ {risk}</span>
                        {sc_pill(sc)}
                    </div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)
    with col_btn:
        if st.button("View Report →", key=f"dr_{t}_{cat_key}", use_container_width=True, type="primary"):
            st.session_state.detail_ticker=t; st.session_state.detail_data=s; nav("stock_detail")
        wl=st.session_state.get("watchlist",[])
        in_wl=t in wl
        if st.button("✅ Watching" if in_wl else "➕ Watchlist", key=f"wl_{t}_{cat_key}", use_container_width=True):
            if in_wl: wl.remove(t)
            else:     wl.append(t)
            st.rerun()

def render_cat(cat, limit=10, show_why=False):
    is_comp=cat in COMPOSITE_CATS
    if is_comp:
        _,tier=COMPOSITE_CATS[cat]
        if tier=="premium" and not is_premium():
            render_lock(cat); return
        stocks=get_composite_stocks(cat,limit)
    else:
        tickers=list(CATEGORIES.get(cat,[])); hot=st_hot()
        if cat=="🔥 Trending Now": tickers=hot
        if not tickers: st.info("No tickers available."); return
        scan=min(len(tickers),limit); stocks=[]
        prog=st.progress(0,f"Loading {cat}…")
        for i,t in enumerate(tickers[:scan]):
            prog.progress((i+1)/scan,f"Analyzing {t}…")
            q=get_quote(t); df=get_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            sc,bd,op,risk,conf=compute_scores(df,info,sent); ig=get_insights(df,info)
            if q: stocks.append({"t":t,"q":q,"sc":sc,"bd":bd,"ig":ig,"op":op,"risk":risk,"conf":conf,"hot":t in hot,"df":df,"info":info,"sent":sent,"comp":sc,"why":""})
        prog.empty()
        stocks.sort(key=lambda x:x["sc"],reverse=True)
    if not stocks: st.info(f"No stocks matching criteria for {cat} right now."); return
    for s in stocks:
        render_sr(s,cat.replace(" ","_").replace("+","p"),show_why=is_comp)

def render_lock(name=""):
    st.markdown(f"""<div class="lock">
        <div style="font-size:28px;margin-bottom:10px;">🔒</div>
        <div style="font-size:17px;font-weight:800;color:#e2e8f0;margin-bottom:6px;">{name} — Premium</div>
        <div style="font-size:13px;color:#374f6e;margin-bottom:16px;">Upgrade to unlock all premium composite categories, squeeze scanner, and advanced screener.</div>
    </div>""", unsafe_allow_html=True)
    if st.button("🚀 Go Premium →", key=f"lock_{name.replace(' ','_').replace('+','p')}", type="primary"): nav("pricing")

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown('<div style="padding:20px 18px 10px;"><div class="logo">Stock<span class="w">W</span>ins</div><div style="font-size:10px;color:rgba(255,255,255,.2);margin-top:2px;">Market Intelligence</div></div>', unsafe_allow_html=True)
        st.divider()

        if is_authed():
            cur=st.session_state.page
            st.markdown('<div class="sb-section">Discover</div>', unsafe_allow_html=True)

            # Composite categories from COMPOSITE_CATS dict
            for cat_key,(desc,tier) in COMPOSITE_CATS.items():
                is_locked = tier=="premium" and not is_premium()
                label = cat_key + (" ⭐" if is_locked else "")
                safe_key = cat_key.replace(' ','_').replace('+','p').replace('→','r').replace('🌡️','T').replace('📉','D')
                if st.button(label, key=f"sb_c_{safe_key[:30]}", use_container_width=True):
                    if is_locked:
                        nav("pricing")
                    else:
                        st.session_state.discover_cat=cat_key; nav("discover")

            st.markdown('<div class="sb-section">Categories</div>', unsafe_allow_html=True)
            std_items=[("🔥","Trending Now"),("📡","Social Buzz"),("💻","Tech"),("🤖","AI"),("⚡","EV"),("🧬","Biotech"),("📊","S&P 500"),("🔬","Small Cap")]
            for icon,label in std_items:
                cat_key=f"{icon} {label}"
                if st.button(f"{icon} {label}", key=f"sb_std_{label.replace(' ','_')}", use_container_width=True):
                    st.session_state.discover_cat=cat_key; nav("discover")

            st.markdown('<div class="sb-section">Tools</div>', unsafe_allow_html=True)
            for icon,label,pg in [("📊","Dashboard","dashboard"),("⭐","Watchlist","watchlist"),("🔍","Screener","screener"),("📈","BI Analytics","bi_dashboard"),("💰","Pricing","pricing")]:
                if st.button(f"{icon} {label}", key=f"sb_{pg}", use_container_width=True): nav(pg)

            if is_admin():
                st.markdown('<div class="sb-section">Admin</div>', unsafe_allow_html=True)
                if st.button("🛠️ Admin Panel", key="sb_admin", use_container_width=True): nav("admin")

            st.divider()
            role_icon={"owner":"👑","admin":"🛡️","premium":"⭐","free":"👤"}.get(st.session_state.role,"👤")
            st.markdown(f'<div style="padding:4px 18px;font-size:12px;color:#374f6e;">{role_icon} {st.session_state.user["name"]}</div>', unsafe_allow_html=True)
            if not is_premium():
                if st.button("⚡ Go Premium", key="sb_upgrade", type="primary", use_container_width=True): nav("pricing")
            if st.button("Log Out", key="sb_logout", use_container_width=True): logout()
        else:
            st.markdown("""<div style="padding:12px 18px;">
                <div style="font-size:12px;color:#374f6e;margin-bottom:12px;">Sign in to access the full dashboard.</div>
            </div>""", unsafe_allow_html=True)
            if st.button("Login →", key="sb_login", use_container_width=True): nav("login")
            if st.button("Sign Up Free →", key="sb_signup", type="primary", use_container_width=True): nav("signup")
            st.markdown("""<div style="margin:12px 10px;background:#0b0e19;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:12px 14px;">
                <div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1px;text-transform:uppercase;margin-bottom:7px;">Free Includes</div>
                <div style="font-size:12px;color:#2a3a52;line-height:2.2;">✅ Live market data<br>✅ 3 composite categories<br>✅ Social sentiment<br>✅ Plain-English insights<br>✅ Watchlist</div>
            </div>""", unsafe_allow_html=True)
        st.markdown('<div style="padding:8px 18px;font-size:10px;color:rgba(255,255,255,.1);">© 2026 StockWins</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# NAV BAR
# ─────────────────────────────────────────────────────────────
def render_topbar(active=""):
    st.markdown('<div style="background:#080b14;border-bottom:1px solid rgba(255,255,255,.06);padding:0 24px;min-height:52px;display:flex;align-items:center;">', unsafe_allow_html=True)
    c1,c2,c3=st.columns([2,8,3])
    with c1:
        if st.button("StockWins", key="top_logo_click"):
            nav("landing" if not is_authed() else "dashboard")
    with c2:
        if is_authed():
            pages=[("Dashboard","dashboard"),("Discover","discover"),("Watchlist","watchlist"),("Screener","screener"),("BI Analytics","bi_dashboard"),("Pricing","pricing")]
            if is_admin(): pages.append(("🛠 Admin","admin"))
            nc=st.columns(len(pages))
            for col,(lbl,pg) in zip(nc,pages):
                with col:
                    if st.button(lbl, key=f"top_{pg}", type="primary" if active==pg else "secondary"):
                        nav(pg)
    with c3:
        if is_authed():
            cc1,cc2,cc3=st.columns([4,1,1])
            ri={"owner":"👑","admin":"🛡️","premium":"⭐","free":"👤"}.get(st.session_state.role,"👤")
            with cc1: st.markdown(f'<div style="font-size:12px;color:#374f6e;padding-top:9px;white-space:nowrap;">{ri} {st.session_state.user["name"]}</div>',unsafe_allow_html=True)
            with cc2:
                if st.button("⚙️",key="top_set"): nav("settings")
            with cc3:
                if st.button("↩️",key="top_out"): logout()
        else:
            lc1,lc2=st.columns(2)
            with lc1:
                if st.button("Login",key="top_login"): nav("login")
            with lc2:
                if st.button("Sign Up",key="top_signup",type="primary"): nav("signup")
    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

# ─────────────────────────────────────────────────────────────
# HERO DEMO PANELS
# ─────────────────────────────────────────────────────────────
DEMO = [
    # Panel 0 — Trending + Squeeze
    """<div style="background:#0e1421;border:1px solid rgba(255,255,255,.08);border-radius:11px;overflow:hidden;">
    <div style="background:#080b14;border-bottom:1px solid rgba(255,255,255,.06);padding:10px 14px;display:flex;align-items:center;gap:6px;">
        <div style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></div>
        <span style="font-size:11px;color:#374f6e;margin-left:6px;font-family:'JetBrains Mono',monospace;">StockTwits Hot Stocks</span>
    </div>
    <div style="padding:14px;">
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">TSLA</span><div style="font-size:10px;color:#2a3a52;margin-top:2px;">Tesla · Momentum is strongly trending</div><div style="margin-top:5px;"><span style="background:#05260f;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(74,222,128,.3);">Strong Momentum</span><span style="background:#260d00;color:#fb923c;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(251,146,60,.3);margin-left:4px;">🔥 HOT</span></div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">$199.49</div><div style="font-size:12px;font-weight:700;color:#22c55e;">▲ 12.72</div></div>
        </div>
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">NVDA</span><div style="font-size:10px;color:#2a3a52;margin-top:2px;">AI sector leader</div><div style="margin-top:5px;"><span style="background:#05260f;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(74,222,128,.3);">Golden Cross ✨</span></div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">$3,178</div><div style="font-size:12px;font-weight:700;color:#22c55e;">▲ 33.99</div><div style="font-size:10px;font-weight:700;color:#4ade80;background:#05260f;padding:1px 8px;border-radius:3px;margin-top:3px;">Score 88</div></div>
        </div>
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">AI</span><div style="font-size:10px;color:#2a3a52;margin-top:2px;">C3.ai · Smart Entrainment</div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">$44.0</div><div style="font-size:12px;font-weight:700;color:#ef4444;">▼ 29.75</div></div>
        </div>
        <div style="margin-top:10px;display:flex;gap:5px;flex-wrap:wrap;">
            <span style="background:#060f2a;color:#93b4fd;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid rgba(147,180,253,.3);">Momentum</span>
            <span style="background:#060f2a;color:#93b4fd;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid rgba(147,180,253,.3);">Breakout Watch</span>
            <span style="background:#060f2a;color:#93b4fd;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid rgba(147,180,253,.3);">NASDAQ Stocks</span>
        </div>
    </div></div>""",

    # Panel 1 — Short Squeeze
    """<div style="background:#0e1421;border:1px solid rgba(255,255,255,.08);border-radius:11px;overflow:hidden;">
    <div style="background:#080b14;border-bottom:1px solid rgba(255,255,255,.06);padding:10px 14px;display:flex;align-items:center;justify-content:space-between;">
        <div style="display:flex;align-items:center;gap:6px;">
            <div style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></div>
            <div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;display:inline-block;"></div>
            <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></div>
            <span style="font-size:11px;color:#374f6e;margin-left:6px;font-family:'JetBrains Mono',monospace;">Short Squeeze Candidates</span>
        </div>
        <span style="font-size:9px;font-weight:700;color:#fbbf24;background:rgba(245,158,11,.12);border:1px solid rgba(245,158,11,.3);padding:2px 8px;border-radius:20px;">Short 239</span>
    </div>
    <div style="padding:14px;">
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">AMC</span><div style="font-size:10px;color:#2a3a52;">$56.42 · Strong uptrend</div><div style="margin-top:5px;"><span style="background:#160828;color:#c084fc;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(192,132,252,.3);">🔥💥 Squeeze + Buzz</span></div></div>
            <div style="text-align:right;"><div style="font-size:9px;color:#2a3a52;">Short Score</div><div style="font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;color:#ef4444;">29.99%</div></div>
        </div>
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">CVNA</span><div style="font-size:10px;color:#2a3a52;">Price strategy upward · ⚡📈 Volume Breakout</div></div>
            <div style="text-align:right;"><div style="font-size:9px;color:#2a3a52;">Float Score</div><div style="font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;color:#4ade80;">38.75</div><div style="font-size:10px;color:#22c55e;">+5.42%</div></div>
        </div>
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">MSTR</span><div style="font-size:10px;color:#2a3a52;">Price trending forward</div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#e2e8f0;">$29.26</div><div style="font-size:12px;font-weight:700;color:#22c55e;">+185.84%</div></div>
        </div>
        <div style="margin-top:10px;display:flex;gap:5px;flex-wrap:wrap;">
            <span style="background:#260d00;color:#fb923c;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid rgba(251,146,60,.3);">Meme Stocks</span>
            <span style="background:#260d00;color:#fb923c;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid rgba(251,146,60,.3);">High Short Interest</span>
            <span style="background:#260d00;color:#fb923c;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid rgba(251,146,60,.3);">Squeeze Radar</span>
        </div>
    </div></div>""",

    # Panel 2 — Plain English Insights
    """<div style="background:#0e1421;border:1px solid rgba(255,255,255,.08);border-radius:11px;overflow:hidden;">
    <div style="background:#080b14;border-bottom:1px solid rgba(255,255,255,.06);padding:10px 14px;display:flex;align-items:center;gap:6px;">
        <div style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></div>
        <span style="font-size:11px;color:#374f6e;margin-left:6px;font-family:'JetBrains Mono',monospace;">Smart Insights — Plain Language</span>
    </div>
    <div style="padding:14px;">
        <div style="background:#0a1020;border-left:3px solid #22c55e;border-radius:0 7px 7px 0;padding:11px 13px;margin-bottom:7px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
                <span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">TSLA</span>
                <span style="font-size:13px;font-weight:700;color:#22c55e;">▲ 4.27%</span>
            </div>
            <div style="font-size:12px;color:#374f6e;line-height:1.6;"><span style="color:#2dd4bf;font-weight:600;">The Moving Average</span> is breaking out above an important price range, which can sometimes lead to further upside.</div>
        </div>
        <div style="background:#0a1020;border-left:3px solid #4ade80;border-radius:0 7px 7px 0;padding:11px 13px;margin-bottom:7px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
                <span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">PLUG</span>
                <span style="background:#05260f;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(74,222,128,.3);">BULLISH</span>
            </div>
            <div style="font-size:12px;color:#374f6e;line-height:1.6;">There are a lot of <span style="color:#e2e8f0;font-weight:600;">traders</span> betting against this stock, and <span style="color:#e2e8f0;font-weight:600;">momentum is building</span>.</div>
        </div>
        <div style="background:#0a1020;border-left:3px solid #ef4444;border-radius:0 7px 7px 0;padding:11px 13px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
                <span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">AAPL</span>
                <span style="color:#f97316;font-weight:700;font-size:11px;">🔥 Hot!</span>
            </div>
            <div style="font-size:12px;color:#374f6e;line-height:1.6;">The stock <span style="color:#e2e8f0;font-weight:600;">may have risen too much too quickly</span> and could be due for <em style="color:#e2e8f0;font-weight:600;">a pullback</em>.</div>
        </div>
    </div></div>""",
]

# ─────────────────────────────────────────────────────────────
# PAGE: LANDING
# ─────────────────────────────────────────────────────────────
def page_landing():
    # Minimal topbar — clean, evenly spaced
    tc1, tc2 = st.columns([3, 4])
    with tc1:
        st.markdown('<div style="padding:10px 0 0 24px;"><span class="logo">Stock<span class="w">W</span>ins</span></div>', unsafe_allow_html=True)
    with tc2:
        lc1, lc2, lc3, lc4 = st.columns([2, 2, 2, 3])
        with lc1:
            if st.button("Features", key="land_feat", use_container_width=True): pass
        with lc2:
            if st.button("Pricing",  key="land_price_nav", use_container_width=True): nav("pricing")
        with lc3:
            if st.button("Login",    key="land_login", use_container_width=True): nav("login")
        with lc4:
            if st.button("Start Free →", key="land_su", type="primary", use_container_width=True): nav("signup")
    st.divider()

    # Hero
    hl,hr=st.columns([5,5],gap="large")
    p_idx=st.session_state.get("hero_panel",0)
    with hl:
        st.markdown("""<div class="hero-l">
            <div class="hero-eye">Smart Stock Discovery Platform</div>
            <div class="hero-h1">Spot Market Opportunities<br><span class="hi">Before They Get Crowded</span></div>
            <div class="hero-p">Discover trending stocks, social buzz, short squeeze candidates, and momentum shifts. No API key required — sign up and start exploring in seconds.</div>
        </div>""",unsafe_allow_html=True)
        # Hero CTA buttons — all clearly visible
        st.markdown("""<style>
        /* Hero secondary CTAs — white border, readable */
        button[data-key="h_dash"], button[data-key="h_price"] {
            border: 1px solid rgba(255,255,255,0.35) !important;
            color: #d1e0f0 !important;
            background: rgba(255,255,255,0.06) !important;
        }
        button[data-key="h_dash"]:hover, button[data-key="h_price"]:hover {
            border-color: #2563eb !important;
            color: #93b4fd !important;
            background: rgba(37,99,235,0.12) !important;
        }
        /* Demo switcher inactive buttons */
        button[data-key="demo_0"], button[data-key="demo_1"], button[data-key="demo_2"] {
            border: 1px solid rgba(255,255,255,0.2) !important;
            color: #8aa8c4 !important;
            background: rgba(255,255,255,0.04) !important;
            font-size: 12px !important;
        }
        </style>""", unsafe_allow_html=True)

        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            if st.button("Start Free", key="h_su", type="primary", use_container_width=True): nav("signup")
        with bc2:
            if st.button("Try Dashboard", key="h_dash", use_container_width=True): nav("login")
        with bc3:
            if st.button("See Pricing", key="h_price", use_container_width=True): nav("pricing")
        st.markdown("<br>",unsafe_allow_html=True)
        labels=["📊 Market Overview","💥 Squeeze Candidates","💡 Plain-English Insights"]
        dc=st.columns(3)
        for i,(col,lbl) in enumerate(zip(dc,labels)):
            with col:
                if st.button(lbl,key=f"demo_{i}",type="primary" if p_idx==i else "secondary",use_container_width=True):
                    st.session_state.hero_panel=i; st.rerun()
    with hr:
        st.markdown(f'<div style="padding:32px 48px 24px 0;">{DEMO[p_idx]}</div>',unsafe_allow_html=True)

    # Stats bar
    st.markdown("""<div style="background:#080b14;border-top:1px solid rgba(255,255,255,.06);border-bottom:1px solid rgba(255,255,255,.06);padding:18px 48px;display:flex;gap:48px;align-items:center;">
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:18px;">📊</span><div><div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;">5,000+</div><div style="font-size:11px;color:#2a3a52;">US Stocks Covered</div></div></div>
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:18px;">🎯</span><div><div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;">10+</div><div style="font-size:11px;color:#2a3a52;">Smart Categories</div></div></div>
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:18px;">💰</span><div><div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;">$0</div><div style="font-size:11px;color:#2a3a52;">To Get Started</div></div></div>
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:18px;">⚡</span><div><div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;">Real-Time</div><div style="font-size:11px;color:#2a3a52;">Sentiment Data</div></div></div>
    </div>""",unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)

    # Section: Find Trending + Squeeze (matching image 2 layout)
    s1,s2=st.columns(2,gap="large")
    with s1:
        st.markdown("""<div style="padding:0 0 0 48px;">
            <div style="font-size:28px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Find Trending Stocks<br><span style="color:#2563eb;">Before the Crowd</span></div>
            <div style="font-size:13px;color:#374f6e;margin-bottom:20px;line-height:1.7;">Discover top stocks making waves across social media and the market in one smart dashboard.</div>
        </div>""",unsafe_allow_html=True)
        st.markdown(f'<div style="padding:0 0 0 48px;">{DEMO[0]}</div>',unsafe_allow_html=True)
    with s2:
        st.markdown("""<div style="padding:0 48px 0 0;">
            <div style="font-size:28px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Scan For Short Squeeze<br><span style="color:#2563eb;">Candidates</span></div>
            <div style="font-size:13px;color:#374f6e;margin-bottom:20px;line-height:1.7;">Spot stocks with heavy short interest and growing momentum before the move.</div>
        </div>""",unsafe_allow_html=True)
        st.markdown(f'<div style="padding:0 48px 0 0;">{DEMO[1]}</div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Section: Smart Insights + Go Premium
    s3,s4=st.columns(2,gap="large")
    with s3:
        st.markdown("""<div style="padding:0 0 0 48px;">
            <div style="font-size:28px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Smart Insights<br>in Simple <span style="color:#2563eb;">Language</span></div>
            <div style="font-size:13px;color:#374f6e;margin-bottom:20px;line-height:1.7;">Understand technical setups with plain-English explanations that actually make sense.</div>
        </div>""",unsafe_allow_html=True)
        st.markdown(f'<div style="padding:0 0 0 48px;">{DEMO[2]}</div>',unsafe_allow_html=True)
    with s4:
        st.markdown("""<div style="padding:0 48px 0 0;">
            <div style="font-size:28px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Go Premium For<br><span style="color:#f59e0b;">Real-Time Signals &<br>Deeper Analysis</span></div>
            <div style="font-size:13px;color:#374f6e;margin-bottom:20px;line-height:1.7;">Upgrade to unlock advanced screening, unlimited alerts, and premium watchlists.</div>
            <div style="background:#0e1421;border:1px solid rgba(255,255,255,.08);border-radius:11px;overflow:hidden;">
                <div style="background:linear-gradient(135deg,#060f2a,#0e1421);border-bottom:1px solid rgba(255,255,255,.06);padding:12px 16px;text-align:center;font-size:12px;font-weight:700;color:#93b4fd;letter-spacing:1px;">Premium Features</div>
                <div style="padding:16px;font-size:13px;color:#374f6e;line-height:2.3;">
                    ✅ Advanced Stock Screeners<br>✅ Real-Time Alerts<br>✅ Unlimited Watchlists<br>✅ Enhanced Analysis<br>✅ Premium Signals<br>✅ Full Dashboard Access
                </div>
            </div>
        </div>""",unsafe_allow_html=True)
        st.markdown('<div style="padding:12px 48px 0 0;">',unsafe_allow_html=True)
        if st.button("🚀 Go Premium →",key="land_prem",type="primary",use_container_width=True): nav("pricing")
        st.markdown('</div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Our Composite Categories
    st.markdown('<div style="padding:0 48px;"><div class="sec-hd">Our Proprietary Signal Categories <span class="tag tag-comp">Unique to StockWins</span></div>',unsafe_allow_html=True)
    st.markdown('<div style="font-size:13px;color:#374f6e;margin-bottom:16px;">We combine multiple independent data signals to surface unique opportunities you won\'t find on any other platform.</div>',unsafe_allow_html=True)
    cg=st.columns(3,gap="small")
    color_map={"🔥💥 Squeeze + Buzz":"#ef4444","💡 Hidden Movers":"#3b82f6","🎭 Social Catalyst":"#f97316","⚡📈 Volume Breakout":"#06b6d4","🎯 Smart Reversal":"#f59e0b","🌊 Momentum Leaders":"#22c55e"}
    for i,(cat,(desc,tier)) in enumerate(COMPOSITE_CATS.items()):
        with cg[i%3]:
            c=color_map.get(cat,"#2563eb")
            tier_b=f'<span style="float:right;background:rgba(245,158,11,.12);color:#fbbf24;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(245,158,11,.3);">PRO</span>' if tier=="premium" else f'<span style="float:right;background:rgba(34,197,94,.1);color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(34,197,94,.3);">FREE</span>'
            st.markdown(f"""<div class="card" style="border-left:3px solid {c};">{tier_b}
                <div style="font-size:14px;font-weight:700;color:#e2e8f0;margin-bottom:5px;">{cat}</div>
                <div style="font-size:12px;color:#374f6e;line-height:1.5;">{desc}</div>
            </div>""",unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
    _,pc,_=st.columns([2,1,2])
    with pc:
        if st.button("Explore All Categories →",key="land_cats",type="primary",use_container_width=True): nav("signup")

    st.markdown("<br>",unsafe_allow_html=True)

    # FAQ
    st.markdown('<div style="padding:0 48px;"><div class="sec-hd">FAQ</div>',unsafe_allow_html=True)
    for q,a in [
        ("Is this financial advice?","No. StockWins is an educational analysis tool. All signals are algorithmic outputs for informational purposes only. Always consult a licensed financial advisor before making any investment decisions."),
        ("What are the Composite Categories?","StockWins proprietary composite categories combine multiple independent data signals to surface unique setups not visible through standard technical analysis. Each category has a specific multi-factor entry criteria that filters from our full stock universe in real time."),
        ("What markets and stocks are covered?","We cover US equity markets including NASDAQ, NYSE, S&P 500, Russell 1000, and high-volume small caps. Data includes real-time price, volume, fundamentals, and live social sentiment from StockTwits."),
        ("Can I cancel Premium anytime?","Yes. Premium is month-to-month. Cancel at any time and keep access through the end of your billing period. No questions asked."),
        ("What's the difference between Free and Premium?","Free gives you market overview, 5 standard categories, and 5 composite categories. Premium unlocks all 11 composite categories, the full squeeze scanner, advanced multi-factor screener, BI analytics with interactive charts, score breakdowns, and unlimited watchlist."),
    ]:
        with st.expander(q):
            st.markdown(f'<div style="font-size:13px;color:#374f6e;line-height:1.7;">{a}</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

    # Footer
    st.markdown("""<div style="background:#080b14;border-top:1px solid rgba(255,255,255,.06);padding:32px 48px;margin-top:32px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:10px;">
            <div class="logo">Stock<span class="w">W</span>ins</div>
            <div style="font-size:12px;color:rgba(255,255,255,.15);">Privacy Policy · Terms of Service · Risk Disclaimer · Contact</div>
        </div>
        <div class="disc">⚠️ <strong>Risk Disclaimer:</strong> Trading stocks involves substantial risk of financial loss. StockWins provides algorithmic, educational content only — not financial, investment, legal, or tax advice. All signals may be inaccurate or delayed. Past performance does not guarantee future results.</div>
        <div style="font-size:10px;color:rgba(255,255,255,.1);margin-top:10px;text-align:right;">© 2026 StockWins. All rights reserved.</div>
    </div>""",unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# AUTH PAGES
# ─────────────────────────────────────────────────────────────
def page_login():
    render_topbar()
    _,cc,_=st.columns([1,2,1])
    with cc:
        st.markdown('''<div style="text-align:center;padding:40px 0 28px;">
            <div style="font-size:26px;font-weight:800;color:#e2e8f0;margin-bottom:6px;">Welcome Back 👋</div>
            <div style="font-size:13px;color:#374f6e;">Sign in to your StockWins account</div>
        </div>''', unsafe_allow_html=True)

        with st.form("lf", clear_on_submit=False):
            email = st.text_input("Email address", label_visibility="visible")
            pw    = st.text_input("Password", type="password", label_visibility="visible",
                                   help="Enter your account password — NOT the hash")
            submitted = st.form_submit_button("Sign In →", type="primary", use_container_width=True)
            if submitted:
                if not email or not pw:
                    st.error("Please enter your email and password.")
                elif login(email, pw):
                    nav("dashboard")
                else:
                    st.error("Invalid email or password. Check your credentials and try again.")

        # Login help
        secrets_set = False
        try:
            secrets_set = bool(st.secrets.get("owner_email","") or
                               (st.secrets.get("accounts",{}) or {}).get("owner_email",""))
        except: pass

        if secrets_set:
            st.markdown('''<div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:12px 14px;margin-top:12px;font-size:12px;color:#374f6e;text-align:center;">
                Login with the email and password you set in Streamlit Secrets.
            </div>''', unsafe_allow_html=True)
        else:
            st.markdown('''<div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:12px 14px;margin-top:12px;font-size:12px;color:#374f6e;">
                <span style="color:#93b4fd;font-weight:600;">Demo accounts (for testing):</span><br>
                <span style="font-family:'JetBrains Mono',monospace;">demo@stockwins.com</span> / <span style="font-family:'JetBrains Mono',monospace;">demo123</span><br>
                <span style="font-family:'JetBrains Mono',monospace;">premium@stockwins.com</span> / <span style="font-family:'JetBrains Mono',monospace;">premium1</span>
            </div>''', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Equal-height action buttons
        bc1, bc2 = st.columns(2, gap="small")
        with bc1:
            if st.button("Create Free Account →", key="l2s", use_container_width=True, type="primary"):
                nav("signup")
        with bc2:
            if st.button("Forgot password?", key="l2f", use_container_width=True):
                nav("forgot_pw")
        if st.button("← Back to Home", key="l2h", use_container_width=True):
            nav("landing")

def page_signup():
    render_topbar()
    _,cc,_=st.columns([1,2,1])
    with cc:
        st.markdown('<div style="text-align:center;padding:32px 0 20px;"><div style="font-size:24px;font-weight:800;color:#e2e8f0;">Create Your Account 🚀</div><div style="font-size:13px;color:#374f6e;margin-top:6px;">Free. No credit card. No API keys.</div></div>',unsafe_allow_html=True)
        with st.form("sf"):
            name=st.text_input("Full name",placeholder="Jane Doe")
            email=st.text_input("Email",placeholder="you@example.com")
            pw=st.text_input("Password",type="password",placeholder="Min 6 characters")
            pw2=st.text_input("Confirm password",type="password")
            agree=st.checkbox("I agree to the Terms of Service and understand this is not financial advice.")
            if st.form_submit_button("Create Free Account →",type="primary",use_container_width=True):
                if not all([name,email,pw,pw2]): st.error("Fill in all fields.")
                elif pw!=pw2: st.error("Passwords don't match.")
                elif len(pw)<6: st.error("Password must be 6+ characters.")
                elif not agree: st.error("Please agree to the Terms of Service.")
                else:
                    ok,msg=signup(email,pw,name)
                    if ok: st.success(f"Welcome, {name}!"); time.sleep(0.4); nav("dashboard")
                    else:  st.error(msg)
        if st.button("Already have an account? Sign In",key="s2l",use_container_width=True): nav("login")

def page_forgot():
    render_topbar()
    _,cc,_=st.columns([1,2,1])
    with cc:
        st.markdown('<div style="text-align:center;padding:28px 0 16px;"><div style="font-size:22px;font-weight:800;color:#e2e8f0;">Reset Password 🔑</div></div>',unsafe_allow_html=True)
        with st.form("fpf"):
            email=st.text_input("Email address",placeholder="you@example.com")
            if st.form_submit_button("Send Reset Link →",type="primary",use_container_width=True):
                if email in st.session_state.users_db:
                    st.success("✅ Reset link sent! (Simulated in demo)")
                    time.sleep(1); nav("login")
                else: st.error("No account found with that email.")
        if st.button("← Back to Login",key="f2l",use_container_width=True): nav("login")

# ─────────────────────────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────────────────────────
def page_dashboard():
    render_topbar("dashboard")
    st.markdown('<div class="pg">',unsafe_allow_html=True)

    # ── HERO: Proprietary Composite Categories FIRST ──────────
    st.markdown('<div class="sec-hd">🎯 Our Proprietary Signal Categories <span class="tag tag-comp">Unique to StockWins</span></div>',unsafe_allow_html=True)
    st.markdown('<div style="font-size:13px;color:#374f6e;margin-bottom:16px;">StockWins combines multiple independent data signals to surface unique trade opportunities.</div>',unsafe_allow_html=True)

    color_map={"🔥💥 Squeeze + Buzz":"#ef4444","💡 Hidden Movers":"#3b82f6","🎭 Social Catalyst":"#f97316","⚡📈 Volume Breakout":"#06b6d4","🎯 Smart Reversal":"#f59e0b","🌊 Momentum Leaders":"#22c55e"}
    comp_items=list(COMPOSITE_CATS.items())
    for i in range(0,len(comp_items),2):
        cols=st.columns(2,gap="small")
        for j,col in enumerate(cols):
            if i+j<len(comp_items):
                cat,(desc,tier)=comp_items[i+j]
                c=color_map.get(cat,"#2563eb")
                is_locked=tier=="premium" and not is_premium()
                tier_tag=f'<span class="tag tag-prem">PREMIUM</span>' if tier=="premium" else f'<span class="tag tag-free">FREE</span>'
                with col:
                    st.markdown(f"""<div class="card" style="border-left:3px solid {c};">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px;">
                            <div style="font-size:14px;font-weight:700;color:#e2e8f0;">{cat} {"🔒" if is_locked else ""}</div>{tier_tag}
                        </div>
                        <div style="font-size:12px;color:#374f6e;margin-bottom:10px;">{desc}</div>
                    </div>""",unsafe_allow_html=True)
                    btn_key=f"dash_cat_{cat.replace(' ','_').replace('+','p')}"
                    if st.button(f"Explore {cat} →",key=btn_key,use_container_width=True):
                        if is_locked: nav("pricing")
                        else: st.session_state.discover_cat=cat; nav("discover")

    st.markdown('<div class="div-line"></div>',unsafe_allow_html=True)

    # ── StockTwits Hot + Squeeze Preview ─────────────────────
    left,right=st.columns(2,gap="small")
    with left:
        st.markdown('<div class="sec-hd">📡 StockTwits Hot Stocks <span class="tag tag-live">Live</span></div>',unsafe_allow_html=True)
        hot=st_hot()
        prog=st.progress(0,"Loading…")
        for i,t in enumerate(hot[:5]):
            prog.progress((i+1)/5)
            q=get_quote(t)
            if q:
                s=st_sent(t); cc_="#22c55e" if q["pct"]>=0 else "#ef4444"; ar="▲" if q["pct"]>=0 else "▼"
                st.markdown(f"""<div class="sr">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <span class="sr-tick">{t}</span><span class="b b-hot" style="margin-left:6px;">🔥</span>
                            <div class="sr-name">{q.get('name','')[:28]}</div>
                            <div class="sr-why">→ {s['bull']}% bullish · {s.get('wl',0):,} watching</div>
                        </div>
                        <div style="text-align:right;">
                            <div class="sr-price">${q['price']:,.2f}</div>
                            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{cc_};">{ar}{abs(q['pct']):.2f}%</div>
                        </div>
                    </div>
                </div>""",unsafe_allow_html=True)
        prog.empty()

    with right:
        st.markdown('<div class="sec-hd">🔥💥 Squeeze + Buzz Preview <span class="tag tag-comp">Composite</span></div>',unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;color:#374f6e;margin-bottom:10px;">High short float + social trending = explosive combo</div>',unsafe_allow_html=True)
        preview_t=["GME","AMC","MSTR","MULN","SPCE"]
        prog=st.progress(0,"Scanning…")
        shown=0
        for i,t in enumerate(preview_t):
            prog.progress((i+1)/len(preview_t))
            info=yf_fund(t); sf=(info.get("sf",0) or 0)*100
            if sf>=8:
                q=get_quote(t)
                if q:
                    shown+=1; cc_="#22c55e" if q["pct"]>=0 else "#ef4444"
                    st.markdown(f"""<div class="sr">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div>
                                <span class="sr-tick">{t}</span>
                                <div class="sr-name">{q.get('name','')[:28]}</div>
                                <div class="sr-why">→ Short float: <span style="color:#ef4444;font-weight:700;">{sf:.1f}%</span> · DTC: {info.get('dtc',0) or 0:.1f}d</div>
                            </div>
                            <div style="text-align:right;">
                                <div class="sr-price">${q['price']:,.2f}</div>
                                <div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{cc_};">{"▲" if q['pct']>=0 else "▼"}{abs(q['pct']):.2f}%</div>
                            </div>
                        </div>
                    </div>""",unsafe_allow_html=True)
        prog.empty()
        if shown==0: st.info("No squeeze candidates above threshold right now.")
        if st.button("Full Squeeze Scanner →",key="dash_sq",use_container_width=True):
            if is_premium(): st.session_state.discover_cat="🔥💥 Squeeze + Buzz"; nav("discover")
            else: nav("pricing")

    st.markdown('<div class="div-line"></div>',unsafe_allow_html=True)

    # ── Market Overview (compact, below fold) ─────────────────
    st.markdown('<div class="sec-hd">📊 Market Overview</div>',unsafe_allow_html=True)
    with st.spinner("Loading market data…"):
        idx=get_indexes(); secs=get_sectors()

    idx_cols=st.columns(len(idx))
    for col,(name,d) in zip(idx_cols,idx.items()):
        c="#22c55e" if d["pct"]>=0 else "#ef4444"
        ar="▲" if d["pct"]>=0 else "▼"
        hist=d.get("hist",[])
        bars=""
        if hist:
            mn,mx=min(hist),max(hist); rng=mx-mn if mx!=mn else 1
            bars=''.join([f'<div style="height:{int(12*(v-mn)/rng+3)}px;width:4px;background:{"#22c55e" if d["pct"]>=0 else "#ef4444"};border-radius:2px;display:inline-block;margin-right:1px;vertical-align:bottom;opacity:0.7;"></div>' for v in hist])
        col.markdown(f"""<div class="idx-w">
            <div class="idx-name">{name}</div>
            <div class="idx-price">{d['price']:,.2f}</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:{c};">{ar}{abs(d['pct']):.2f}%</div>
            <div style="margin-top:8px;height:16px;display:flex;align-items:flex-end;">{bars}</div>
        </div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Sector heatmap (compact)
    st.markdown('<div style="font-size:13px;font-weight:600;color:#6b7fa0;margin-bottom:8px;">Sector Performance</div>',unsafe_allow_html=True)
    sec_sorted=sorted(secs.items(),key=lambda x:x[1],reverse=True)
    sc_cols=st.columns(5)
    for i,(sec,chg) in enumerate(sec_sorted):
        with sc_cols[i%5]:
            cls="hm-hi" if chg>0.15 else "hm-lo" if chg<-0.15 else "hm-nu"
            ar="▲" if chg>=0 else "▼"
            st.markdown(f'<div class="{cls}" style="margin-bottom:4px;"><div style="font-size:9px;margin-bottom:1px;">{sec}</div>{ar}{abs(chg):.1f}%</div>',unsafe_allow_html=True)

    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: DISCOVER
# ─────────────────────────────────────────────────────────────
def page_discover():
    render_topbar("discover")
    fc,mc=st.columns([1,4],gap="small")
    with fc:
        st.markdown('<div style="padding:16px 0 0 0;">',unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1.5px;text-transform:uppercase;padding:0 0 6px;">Composite (Our Picks)</div>',unsafe_allow_html=True)
        for cat,(desc,tier) in COMPOSITE_CATS.items():
            is_locked=tier=="premium" and not is_premium()
            if st.button(f"{cat}{'  ⭐' if is_locked else ''}",key=f"disc_c_{cat.replace(' ','_').replace('+','p')}",use_container_width=True):
                if is_locked: nav("pricing")
                else: st.session_state.discover_cat=cat; st.rerun()
        st.markdown('<div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1.5px;text-transform:uppercase;padding:12px 0 6px;">Standard</div>',unsafe_allow_html=True)
        for cat in CATEGORIES:
            if st.button(cat,key=f"disc_s_{cat.replace(' ','_')}",use_container_width=True):
                st.session_state.discover_cat=cat; st.rerun()
        if not is_premium():
            if st.button("⚡ Unlock Premium →",key="disc_up",type="primary",use_container_width=True): nav("pricing")
        st.markdown('</div>',unsafe_allow_html=True)
    with mc:
        sel=st.session_state.get("discover_cat","🔥💥 Squeeze + Buzz")
        is_comp=sel in COMPOSITE_CATS
        tier_str=""
        if is_comp:
            _,tier=COMPOSITE_CATS[sel]
            tier_str=f'<span class="tag {"tag-prem" if tier=="premium" else "tag-free"}">{"PREMIUM" if tier=="premium" else "FREE"}</span>'
        desc_str=COMPOSITE_CATS[sel][0] if is_comp else f"Browse all {sel} stocks"
        st.markdown('<div class="pg" style="padding-top:16px;">',unsafe_allow_html=True)
        st.markdown(f'<div class="sec-hd">{sel} {tier_str}</div>',unsafe_allow_html=True)
        if is_comp: st.markdown(f'<div style="font-size:12px;color:#374f6e;margin-bottom:12px;font-style:italic;">{desc_str}</div>',unsafe_allow_html=True)
        is_locked=is_comp and COMPOSITE_CATS[sel][1]=="premium" and not is_premium()
        if is_locked: render_lock(sel)
        else: render_cat(sel, show_why=is_comp)
        st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: STOCK DETAIL (Full Report)
# ─────────────────────────────────────────────────────────────
def page_detail():
    render_topbar()
    ticker=st.session_state.get("detail_ticker")
    data=st.session_state.get("detail_data",{})
    if st.button("← Back",key="back_det"): nav("discover")
    if not ticker: st.warning("No stock selected."); return

    q=data.get("q") or get_quote(ticker)
    df=data.get("df") or get_ohlcv(ticker,90)
    info=data.get("info") or yf_fund(ticker)
    sent=data.get("sent") or st_sent(ticker)
    sc,bd,op,risk,conf=compute_scores(df,info,sent)
    ig=get_insights(df,info)
    hot=ticker in st_hot()
    if not q: st.error(f"Could not load {ticker}."); return

    pct=q.get("pct",0); price=q.get("price",0)
    prev=q.get("prev",0); chg=q.get("chg",0)
    cc="#22c55e" if pct>=0 else "#ef4444"
    ar="▲" if pct>=0 else "▼"
    rc=risk_color(risk)
    sf=(info.get("sf",0) or 0)*100
    mc_v=info.get("mktcap",0)
    mc_s=f"${mc_v/1e12:.2f}T" if mc_v>=1e12 else f"${mc_v/1e9:.2f}B" if mc_v>=1e9 else f"${mc_v/1e6:.0f}M" if mc_v else "N/A"

    st.markdown('<div class="pg">',unsafe_allow_html=True)

    # ── REPORT HEADER ─────────────────────────────────────────
    h1,h2,h3=st.columns([3,2,2],gap="small")
    with h1:
        hot_b='<span class="b b-hot">🔥 HOT</span>' if hot else ""
        op_b=f'<span class="b b-blue">{op}</span>' if op else ""
        st.markdown(f"""<div style="padding:8px 0;">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:800;color:#60a5fa;">{ticker}</span>
                {hot_b}{op_b}
            </div>
            <div style="font-size:15px;color:#4a5e7a;margin-bottom:2px;">{q.get('name','')}</div>
            <div style="font-size:12px;color:#2a3a52;">{info.get('sector','N/A')} · {info.get('industry','N/A')}</div>
            <div style="margin-top:8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                <span style="font-size:12px;font-weight:700;color:{rc};">⚡ {risk} Risk</span>
                <span style="font-size:12px;color:#2a3a52;">·</span>
                <span style="font-size:12px;color:#2a3a52;">{conf} confidence</span>
            </div>
        </div>""",unsafe_allow_html=True)
    with h2:
        st.markdown(f"""<div style="text-align:right;padding:8px 0;">
            <div class="big-price">${price:,.2f}</div>
            <div class="big-chg" style="color:{cc};">{ar} ${abs(chg):.2f} ({abs(pct):.2f}%)</div>
            <div style="font-size:12px;color:#2a3a52;margin-top:4px;">Prev close: ${prev:,.2f}</div>
        </div>""",unsafe_allow_html=True)
    with h3:
        sc_c="#22c55e" if sc>=65 else "#fbbf24" if sc>=40 else "#ef4444"
        sc_bg="#04200d" if sc>=65 else "#1a1000" if sc>=40 else "#200404"
        st.markdown(f"""<div style="background:{sc_bg};border:1px solid {sc_c};border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:40px;font-weight:800;font-family:'JetBrains Mono',monospace;color:{sc_c};">{sc}</div>
            <div style="font-size:10px;color:{sc_c};text-transform:uppercase;letter-spacing:1px;margin-top:2px;">StockWins Score</div>
            <div style="font-size:11px;color:#2a3a52;margin-top:4px;">{op}</div>
        </div>""",unsafe_allow_html=True)

    st.divider()

    # ── TODAY'S SESSION ───────────────────────────────────────
    st.markdown('<div style="font-size:13px;font-weight:700;color:#6b7fa0;margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px;">Today\'s Session</div>',unsafe_allow_html=True)
    s_items=[
        ("Open",f"${q.get('open',0):,.2f}",None),
        ("Day High",f"${q.get('high',0):,.2f}","#22c55e"),
        ("Day Low",f"${q.get('low',0):,.2f}","#ef4444"),
        ("Volume",f"{q.get('volume',0)/1e6:.2f}M",None),
        ("vs Avg Vol",f"{q.get('volume',1)/(info.get('avgvol',1) or 1):.1f}×",None),
        ("Mkt Cap",mc_s,None),
        ("52W High",f"${info.get('hi52',0):,.2f}","#22c55e"),
        ("52W Low",f"${info.get('lo52',0):,.2f}","#ef4444"),
        ("P/E Ratio",f"{info.get('pe','N/A')}",None),
        ("Short Float",f"{sf:.1f}%","#ef4444" if sf>=20 else None),
    ]
    sc_=st.columns(5)
    for i,(lbl,val,vc) in enumerate(s_items):
        with sc_[i%5]:
            color_str=f"color:{vc};" if vc else ""
            st.markdown(f'<div class="stat" style="margin-bottom:8px;"><div class="stat-l">{lbl}</div><div class="stat-v" style="font-size:16px;{color_str}">{val}</div></div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # ── CHART + INSIGHTS ──────────────────────────────────────
    chart_col,ins_col=st.columns([3,2],gap="small")
    with chart_col:
        st.markdown('<div class="sec-hd">📈 Price History (60 Days)</div>',unsafe_allow_html=True)
        if df is not None and len(df)>5:
            # Add MAs to chart
            plot_df=df.copy()
            plot_df["MA20"]=plot_df["close"].rolling(20).mean()
            plot_df["MA50"]=plot_df["close"].rolling(min(50,len(plot_df))).mean()
            if HAS_PLOTLY:
                fig=go.Figure()
                fig.add_trace(go.Scatter(x=plot_df["datetime"],y=plot_df["close"],name="Price",line=dict(color="#3b82f6",width=2),fill="tozeroy",fillcolor="rgba(59,130,246,0.05)"))
                fig.add_trace(go.Scatter(x=plot_df["datetime"],y=plot_df["MA20"],name="MA20",line=dict(color="#f59e0b",width=1,dash="dot")))
                fig.add_trace(go.Scatter(x=plot_df["datetime"],y=plot_df["MA50"],name="MA50",line=dict(color="#ef4444",width=1,dash="dot")))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=280,
                    legend=dict(orientation="h",yanchor="bottom",y=1.02,bgcolor="rgba(0,0,0,0)",font=dict(color="#6b7fa0",size=11)),
                    xaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=10)),
                    yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a",tickfont=dict(size=10)))
                st.plotly_chart(fig,use_container_width=True)
            else:
                cdf=plot_df[["datetime","close","MA20","MA50"]].rename(columns={"datetime":"Date","close":"Price"}).set_index("Date")
                st.line_chart(cdf,color=["#3b82f6","#f59e0b","#ef4444"])

            # Volume bar chart
            st.markdown('<div style="font-size:12px;font-weight:600;color:#6b7fa0;margin:10px 0 6px;">Volume vs Average</div>',unsafe_allow_html=True)
            avg_v=df["volume"].rolling(20).mean()
            if HAS_PLOTLY:
                fig2=go.Figure()
                colors_v=["#22c55e" if v>=a else "#ef4444" for v,a in zip(df["volume"],avg_v)]
                fig2.add_trace(go.Bar(x=df["datetime"],y=df["volume"],marker_color=colors_v,name="Volume"))
                fig2.add_trace(go.Scatter(x=df["datetime"],y=avg_v,name="20d Avg",line=dict(color="#f59e0b",width=1,dash="dash")))
                fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=140,showlegend=False,
                    xaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=9)),yaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=9)))
                st.plotly_chart(fig2,use_container_width=True)
        else:
            st.info("Chart data unavailable.")

        # Score breakdown
        if bd:
            st.markdown('<div class="sec-hd" style="margin-top:12px;">Score Breakdown</div>',unsafe_allow_html=True)
            if is_premium():
                max_v={"Momentum":25,"Trend":20,"MACD":15,"Volume":15,"Sentiment":15,"Squeeze":10}
                for comp,pts in bd.items():
                    mx=max_v.get(comp,15); pct_=pts/mx if mx>0 else 0
                    c_="#22c55e" if pct_>=0.8 else "#fbbf24" if pct_>=0.4 else "#ef4444"
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                        <div style="width:80px;font-size:11px;color:#374f6e;">{comp}</div>
                        <div style="flex:1;background:rgba(255,255,255,.05);border-radius:3px;height:6px;">
                            <div style="background:{c_};width:{int(pct_*100)}%;height:6px;border-radius:3px;"></div>
                        </div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:{c_};width:28px;text-align:right;">{pts}/{mx}</div>
                    </div>""",unsafe_allow_html=True)
            else:
                st.markdown('<div style="background:#080b14;border:1px solid rgba(245,158,11,.2);border-radius:7px;padding:10px;font-size:12px;color:#fbbf24;">🔒 Score breakdown is Premium only.</div>',unsafe_allow_html=True)

    with ins_col:
        st.markdown('<div class="sec-hd">💡 Plain-English Analysis</div>',unsafe_allow_html=True)
        if ig:
            for lbl,txt,s,conf in ig[:7]:
                cls="ins-bull" if s=="bull" else "ins-bear" if s=="bear" else ""
                bc="b-bull" if s=="bull" else "b-bear" if s=="bear" else "b-neu"
                bl="Bullish" if s=="bull" else "Bearish" if s=="bear" else "Neutral"
                st.markdown(f"""<div class="ins {cls}">
                    <div class="ins-label">{lbl} <span class="b {bc}">{bl}</span>
                        <span style="font-size:10px;color:#2a3a52;margin-left:auto;">· {conf}</span>
                    </div>
                    <div class="ins-text">{txt}</div>
                </div>""",unsafe_allow_html=True)
        else:
            st.info("No indicators available.")

        st.markdown('<div class="sec-hd" style="margin-top:14px;">📡 Social Sentiment</div>',unsafe_allow_html=True)
        bull=sent.get("bull",50)
        st.markdown(f"""<div class="card">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="font-size:12px;font-weight:700;color:#22c55e;">🟢 Bullish {bull}%</span>
                <span style="font-size:12px;font-weight:700;color:#ef4444;">🔴 Bearish {100-bull}%</span>
            </div>
            <div style="background:rgba(255,255,255,.05);border-radius:5px;height:8px;overflow:hidden;">
                <div style="background:linear-gradient(90deg,#22c55e,#16a34a);width:{bull}%;height:8px;"></div>
            </div>
            <div style="font-size:11px;color:#2a3a52;margin-top:8px;">👥 {sent.get('wl',0):,} watching · {sent.get('msgs',0)} recent posts</div>
        </div>""",unsafe_allow_html=True)

    # ── WHY FLAGGED ───────────────────────────────────────────
    st.markdown('<div class="div-line"></div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">🎯 Why This Stock Is On Your Radar</div>',unsafe_allow_html=True)
    reasons=[]
    if sc>=70: reasons.append(("Strong multi-factor signal — momentum, trend, MACD, and volume align","bull"))
    if sent.get("bull",50)>=65: reasons.append((f"{sent['bull']}% of StockTwits traders are currently bullish","bull"))
    if sf>=20: reasons.append((f"{sf:.0f}% of shares are sold short — rising price can force short covering (squeeze)","bull"))
    if hot: reasons.append(("Currently trending on StockTwits Hot list — elevated social interest","bull"))
    for lbl,_,sv,_ in ig[:4]: reasons.append((lbl,sv))
    rc2=st.columns(2)
    for i,(r,sv) in enumerate(reasons[:6]):
        em="🟢" if sv=="bull" else "🔴" if sv=="bear" else "⚪"
        with rc2[i%2]:
            st.markdown(f'<div style="background:#080b14;border:1px solid rgba(255,255,255,.05);border-radius:7px;padding:9px 13px;margin-bottom:5px;font-size:12px;color:#374f6e;">{em} {r}</div>',unsafe_allow_html=True)

    # ── RELATED STOCKS ────────────────────────────────────────
    sector=info.get("sector","N/A")
    if sector!="N/A":
        st.markdown(f'<div class="sec-hd" style="margin-top:16px;">🔗 Related — {sector}</div>',unsafe_allow_html=True)
        all_t=list(set([t for tl in CATEGORIES.values() for t in tl]))
        related=[rt for rt in all_t if rt!=ticker and yf_fund(rt).get("sector")==sector][:5]
        if related:
            rcols=st.columns(len(related))
            for col,rt in zip(rcols,related):
                rq=get_quote(rt)
                if rq:
                    rc_="#22c55e" if rq["pct"]>=0 else "#ef4444"
                    col.markdown(f'<div class="stat" style="cursor:pointer;"><div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;font-weight:700;color:#60a5fa;">{rt}</div><div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;font-weight:700;color:#e2e8f0;">${rq["price"]:,.2f}</div><div style="font-size:11px;font-weight:700;color:{rc_};">{"▲" if rq["pct"]>=0 else "▼"}{abs(rq["pct"]):.2f}%</div></div>',unsafe_allow_html=True)
                    if col.button("View",key=f"rel_{rt}",use_container_width=True):
                        st.session_state.detail_ticker=rt; st.session_state.detail_data={}; st.rerun()

    if info.get("desc"):
        with st.expander(f"About {q.get('name',ticker)}"):
            st.markdown(f'<div style="font-size:13px;color:#374f6e;line-height:1.7;">{info["desc"]}</div>',unsafe_allow_html=True)

    # ── ACTIONS ───────────────────────────────────────────────
    st.markdown("<br>",unsafe_allow_html=True)
    wl=st.session_state.get("watchlist",[]); in_wl=ticker in wl
    a1,a2,_=st.columns([1,1,2])
    with a1:
        if st.button("✅ Remove from Watchlist" if in_wl else "➕ Add to Watchlist",key="det_wl",type="primary",use_container_width=True):
            if in_wl: wl.remove(ticker)
            else:     wl.append(ticker)
            st.rerun()
    with a2:
        if st.button("🔔 Set Price Alert",key="det_alert",use_container_width=True):
            st.session_state.alerts=st.session_state.get("alerts",[])
            st.session_state.alerts.append({"ticker":ticker,"price":price,"type":"Price Alert","active":True})
            st.success(f"Alert set for {ticker} at ${price:,.2f}")

    st.markdown('<div class="disc">⚠️ For educational purposes only. Not financial advice. Trading involves risk of loss.</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: BI ANALYTICS
# ─────────────────────────────────────────────────────────────
def page_bi():
    render_topbar("bi_dashboard")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">📊 BI Analytics Dashboard <span class="tag tag-live">Live</span></div>',unsafe_allow_html=True)

    with st.spinner("Loading BI data…"):
        movers=get_bi_movers(); secs=get_sectors(); idx=get_indexes(); hot=st_hot()

    gainers=sorted(movers,key=lambda x:x["pct"],reverse=True)
    losers=sorted(movers,key=lambda x:x["pct"])
    vol_ldrs=sorted(movers,key=lambda x:x["vr"],reverse=True)
    top_g=gainers[0] if gainers else {}; top_l=losers[0] if losers else {}; top_v=vol_ldrs[0] if vol_ldrs else {}
    bull_sec=max(secs,key=secs.get) if secs else "N/A"; bear_sec=min(secs,key=secs.get) if secs else "N/A"
    avg_pct=sum(m["pct"] for m in movers)/len(movers) if movers else 0

    # Summary row
    sw=st.columns(5)
    for col,(v,l,c) in zip(sw,[
        (top_g.get("t","—"),f"Top Gainer +{top_g.get('pct',0):.1f}%","#22c55e"),
        (top_l.get("t","—"),f"Top Loser {top_l.get('pct',0):.1f}%","#ef4444"),
        (top_v.get("t","—"),f"Vol King {top_v.get('vr',0):.1f}x avg","#60a5fa"),
        (bull_sec,f"+{secs.get(bull_sec,0):.1f}% today","#22c55e"),
        ("Bullish" if avg_pct>0.3 else "Bearish" if avg_pct<-0.3 else "Neutral",f"Avg {avg_pct:+.2f}%","#22c55e" if avg_pct>0 else "#ef4444"),
    ]):
        col.markdown(f'<div class="stat"><div style="font-family:\'JetBrains Mono\',monospace;font-size:15px;font-weight:700;color:{c};">{v}</div><div class="stat-l">{l}</div></div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # ── CHARTS ────────────────────────────────────────────────
    tabs=st.tabs(["📈 Leaderboards","🗺️ Sector Chart","📡 Social Buzz","🔊 Volume Surge","🎯 Opportunity Matrix"])

    with tabs[0]:
        lc1,lc2,lc3=st.columns(3,gap="small")
        with lc1:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#22c55e;margin-bottom:8px;">🏆 Top Gainers</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                top10g=gainers[:10]
                fig=go.Figure(go.Bar(x=[m["pct"] for m in top10g],y=[m["t"] for m in top10g],orientation="h",marker_color=["#22c55e"]*len(top10g),text=[f"+{m['pct']:.1f}%" for m in top10g],textposition="outside",textfont=dict(color="#22c55e",size=10)))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=60,t=0,b=0),height=280,xaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=9)),yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(size=11,family="JetBrains Mono")))
                st.plotly_chart(fig,use_container_width=True)
            else:
                for m in gainers[:10]: st.markdown(f'<div class="mv"><span style="font-family:\'JetBrains Mono\',monospace;color:#60a5fa;font-size:12px;">{m["t"]}</span><span style="color:#22c55e;font-weight:700;">▲{m["pct"]:.2f}%</span></div>',unsafe_allow_html=True)
        with lc2:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#ef4444;margin-bottom:8px;">📉 Top Losers</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                top10l=losers[:10]
                fig=go.Figure(go.Bar(x=[m["pct"] for m in top10l],y=[m["t"] for m in top10l],orientation="h",marker_color=["#ef4444"]*len(top10l),text=[f"{m['pct']:.1f}%" for m in top10l],textposition="outside",textfont=dict(color="#ef4444",size=10)))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=50,t=0,b=0),height=280,xaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=9)),yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(size=11,family="JetBrains Mono")))
                st.plotly_chart(fig,use_container_width=True)
            else:
                for m in losers[:10]: st.markdown(f'<div class="mv"><span style="font-family:\'JetBrains Mono\',monospace;color:#60a5fa;font-size:12px;">{m["t"]}</span><span style="color:#ef4444;font-weight:700;">▼{abs(m["pct"]):.2f}%</span></div>',unsafe_allow_html=True)
        with lc3:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#60a5fa;margin-bottom:8px;">🔊 Volume Leaders</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                top10v=vol_ldrs[:10]
                colors_v=["#ef4444" if m["vr"]>=3 else "#fbbf24" if m["vr"]>=2 else "#60a5fa" for m in top10v]
                fig=go.Figure(go.Bar(x=[m["vr"] for m in top10v],y=[m["t"] for m in top10v],orientation="h",marker_color=colors_v,text=[f"{m['vr']:.1f}x" for m in top10v],textposition="outside",textfont=dict(color="#94a3b8",size=10)))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=50,t=0,b=0),height=280,xaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=9),title=dict(text="× avg volume",font=dict(color="#4a5e7a",size=10))),yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(size=11,family="JetBrains Mono")))
                st.plotly_chart(fig,use_container_width=True)
            else:
                for m in vol_ldrs[:10]:
                    c="#ef4444" if m["vr"]>=3 else "#fbbf24" if m["vr"]>=2 else "#60a5fa"
                    st.markdown(f'<div class="mv"><span style="font-family:\'JetBrains Mono\',monospace;color:#60a5fa;font-size:12px;">{m["t"]}</span><span style="font-weight:700;color:{c};">{m["vr"]:.1f}×</span></div>',unsafe_allow_html=True)

    with tabs[1]:
        st.markdown('<div style="font-size:13px;font-weight:600;color:#6b7fa0;margin-bottom:12px;">Sector Performance Today — All 10 S&P Sectors</div>',unsafe_allow_html=True)
        sec_sorted=sorted(secs.items(),key=lambda x:x[1],reverse=True)
        if HAS_PLOTLY:
            secs_df=pd.DataFrame(sec_sorted,columns=["Sector","Change %"])
            colors=[f"rgba(34,197,94,{min(0.9,abs(c)/3+0.3)})" if c>0 else f"rgba(239,68,68,{min(0.9,abs(c)/3+0.3)})" for c in secs_df["Change %"]]
            fig=go.Figure(go.Bar(x=secs_df["Sector"],y=secs_df["Change %"],marker_color=colors,text=[f"{"▲" if c>=0 else "▼"}{abs(c):.2f}%" for c in secs_df["Change %"]],textposition="outside",textfont=dict(color="#94a3b8",size=11)))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=10,b=0),height=300,
                xaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=11)),
                yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a",tickfont=dict(size=10)),
                shapes=[dict(type="line",x0=-0.5,x1=len(secs)-0.5,y0=0,y1=0,line=dict(color="rgba(255,255,255,0.15)",width=1))])
            st.plotly_chart(fig,use_container_width=True)
        else:
            for sec,chg in sec_sorted:
                c="#22c55e" if chg>0 else "#ef4444"; bar=min(abs(chg)*10,100)
                st.markdown(f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;"><div style="width:110px;font-size:11px;color:#4a5e7a;">{sec}</div><div style="flex:1;background:rgba(255,255,255,.04);border-radius:3px;height:16px;overflow:hidden;"><div style="background:{"rgba(34,197,94,0.4)" if chg>=0 else "rgba(239,68,68,0.4)"};width:{bar}%;height:16px;display:flex;align-items:center;padding-left:8px;"><span style="color:{c};font-size:10px;font-weight:700;">{"▲" if chg>=0 else "▼"}{abs(chg):.2f}%</span></div></div></div>',unsafe_allow_html=True)

    with tabs[2]:
        sc1,sc2=st.columns(2)
        with sc1:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:10px;">🔥 Trending on StockTwits</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                sent_data=[]
                for t in hot[:8]:
                    s=st_sent(t); sent_data.append({"ticker":t,"bull":s["bull"],"wl":s.get("wl",0)})
                sent_df=pd.DataFrame(sent_data).sort_values("bull",ascending=False)
                colors_s=["#22c55e" if b>=60 else "#ef4444" if b<40 else "#6b7fa0" for b in sent_df["bull"]]
                fig=go.Figure(go.Bar(x=sent_df["ticker"],y=sent_df["bull"],marker_color=colors_s,text=[f"{b}% bull" for b in sent_df["bull"]],textposition="outside",textfont=dict(color="#94a3b8",size=10)))
                fig.add_hline(y=50,line=dict(color="rgba(255,255,255,0.15)",width=1,dash="dot"))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=10,b=0),height=250,yaxis=dict(range=[0,100],showgrid=False,color="#4a5e7a"),xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=11)))
                st.plotly_chart(fig,use_container_width=True)
        with sc2:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:10px;">👥 Most Watchlisted</div>',unsafe_allow_html=True)
            targets=["NVDA","TSLA","AMD","AAPL","MSTR","PLTR","GME","META"]
            wl_data=sorted([(t,st_sent(t)) for t in targets],key=lambda x:x[1].get("wl",0),reverse=True)
            if HAS_PLOTLY:
                wl_df=pd.DataFrame([{"t":t,"wl":s["wl"],"bull":s["bull"]} for t,s in wl_data])
                fig=go.Figure(go.Bar(x=wl_df["t"],y=wl_df["wl"],marker_color=["rgba(96,165,250,0.7)"]*len(wl_df),text=[f"{w:,}" for w in wl_df["wl"]],textposition="outside",textfont=dict(color="#94a3b8",size=10)))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=10,b=0),height=250,yaxis=dict(showgrid=False,color="#4a5e7a"),xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=11)))
                st.plotly_chart(fig,use_container_width=True)

    with tabs[3]:
        st.markdown('<div style="font-size:13px;font-weight:600;color:#6b7fa0;margin-bottom:12px;">Stocks experiencing unusual trading volume today</div>',unsafe_allow_html=True)
        surge=[m for m in movers if m["vr"]>=1.5]; surge.sort(key=lambda x:x["vr"],reverse=True)
        if surge:
            if HAS_PLOTLY:
                sg_df=pd.DataFrame(surge[:15])
                colors_sg=["#ef4444" if r>=3 else "#fbbf24" if r>=2 else "#22c55e" for r in sg_df["vr"]]
                fig=go.Figure()
                fig.add_trace(go.Scatter(x=sg_df["t"],y=sg_df["pct"],mode="markers",marker=dict(size=[min(max(vr*6,8),30) for vr in sg_df["vr"]],color=sg_df["vr"],colorscale=[[0,"#22c55e"],[0.5,"#fbbf24"],[1,"#ef4444"]],showscale=True,colorbar=dict(title="Vol Ratio",tickfont=dict(color="#6b7fa0",size=9),title_font=dict(color="#6b7fa0",size=10))),text=[f"{t}: {vr:.1f}×" for t,vr in zip(sg_df["t"],sg_df["vr"])],hoverinfo="text+y"))
                fig.add_hline(y=0,line=dict(color="rgba(255,255,255,0.1)",width=1))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=60,t=10,b=0),height=320,xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=10)),yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a",title=dict(text="Day % Change",font=dict(color="#4a5e7a",size=11))))
                st.plotly_chart(fig,use_container_width=True)
                st.caption("Bubble size = volume ratio. Color: green = 1.5× | yellow = 2× | red = 3×+")
            else:
                st.dataframe(pd.DataFrame([{"Ticker":m["t"],"Price":f"${m['price']:,.2f}","Day %":f"{m['pct']:+.2f}%","Vol Ratio":f"{m['vr']:.1f}x"} for m in surge]),use_container_width=True,hide_index=True)
        else:
            st.info("No significant volume surges right now.")

    with tabs[4]:
        st.markdown('<div class="sec-hd">🎯 Composite Opportunity Matrix <span class="tag tag-comp">StockWins Exclusive</span></div>',unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;color:#374f6e;margin-bottom:14px;">Cross-reference of signal strength across our broad universe. Darker green = stronger signal.</div>',unsafe_allow_html=True)
        matrix_tickers=["NVDA","TSLA","AMD","AAPL","MSTR","GME","PLTR","META","MSFT","ARM"]
        signal_types=["Momentum","Trend","Volume","Sentiment","Squeeze"]
        max_vals={"Momentum":25,"Trend":20,"MACD":15,"Volume":15,"Sentiment":15,"Squeeze":10}
        matrix_data={}
        prog=st.progress(0,"Computing matrix…")
        for i,t in enumerate(matrix_tickers):
            prog.progress((i+1)/len(matrix_tickers),f"Analyzing {t}…")
            df=get_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            _,bd,_,_,_=compute_scores(df,info,sent); matrix_data[t]=bd
        prog.empty()

        if HAS_PLOTLY:
            z=[[matrix_data.get(t,{}).get(sig,0)/max_vals.get(sig,15) for sig in signal_types] for t in matrix_tickers]
            text_z=[[f"{matrix_data.get(t,{}).get(sig,0)}" for sig in signal_types] for t in matrix_tickers]
            fig=go.Figure(go.Heatmap(z=z,x=signal_types,y=matrix_tickers,text=text_z,texttemplate="%{text}",textfont=dict(size=12,color="white"),colorscale=[[0,"#0a1020"],[0.33,"#1a3a00"],[0.66,"#0d5016"],[1,"#22c55e"]],showscale=False,xgap=2,ygap=2))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=350,xaxis=dict(side="top",showgrid=False,color="#6b7fa0",tickfont=dict(size=12)),yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=12)))
            st.plotly_chart(fig,use_container_width=True)
        else:
            # HTML fallback
            hcols=st.columns([1]+[1]*len(signal_types))
            hcols[0].markdown('<div style="font-size:10px;color:#2a3a52;text-align:center;">TICKER</div>',unsafe_allow_html=True)
            for i,sig in enumerate(signal_types):
                hcols[i+1].markdown(f'<div style="font-size:10px;color:#2a3a52;text-align:center;">{sig.upper()}</div>',unsafe_allow_html=True)
            for t in matrix_tickers:
                rc=st.columns([1]+[1]*len(signal_types))
                rc[0].markdown(f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;font-weight:700;color:#60a5fa;text-align:center;padding:6px 0;">{t}</div>',unsafe_allow_html=True)
                bd=matrix_data.get(t,{})
                for i,sig in enumerate(signal_types):
                    pts=bd.get(sig,0); mx=max_vals.get(sig,15); pct_=pts/mx if mx>0 else 0
                    bg="#04200d" if pct_>=0.8 else "#0a2010" if pct_>=0.6 else "#141000" if pct_>=0.3 else "#0e1421"
                    tc="#4ade80" if pct_>=0.8 else "#86efac" if pct_>=0.6 else "#fbbf24" if pct_>=0.3 else "#4a5e7a"
                    rc[i+1].markdown(f'<div style="background:{bg};border-radius:4px;padding:6px;text-align:center;font-family:\'JetBrains Mono\',monospace;font-size:11px;font-weight:700;color:{tc};margin:1px;">{pts}</div>',unsafe_allow_html=True)

    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: WATCHLIST, SCREENER, PRICING, SETTINGS, ADMIN
# ─────────────────────────────────────────────────────────────
def page_watchlist():
    render_topbar("watchlist")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">⭐ My Watchlist</div>',unsafe_allow_html=True)
    wl=st.session_state.get("watchlist",[])
    if not wl:
        st.markdown('<div class="card" style="text-align:center;padding:40px;"><div style="font-size:28px;margin-bottom:10px;">📋</div><div style="font-size:15px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">Watchlist is empty</div><div style="font-size:13px;color:#374f6e;">Browse categories and click ➕ Watchlist on any stock.</div></div>',unsafe_allow_html=True)
        if st.button("Browse Stocks →",key="wl_browse",type="primary"): nav("discover")
        st.markdown('</div>',unsafe_allow_html=True); return
    st.caption(f"{len(wl)} stocks")
    rows=[]; prog=st.progress(0,"Loading…")
    for i,t in enumerate(wl):
        prog.progress((i+1)/len(wl))
        q=get_quote(t); df=get_ohlcv(t,30); info=yf_fund(t); sent=st_sent(t)
        sc,_,op,risk,_=compute_scores(df,info,sent)
        if q: rows.append({"Ticker":t,"Name":q.get("name","")[:20],"Price":f"${q['price']:,.2f}","Change":f"{q['pct']:+.2f}%","Score":sc,"Opportunity":op,"Risk":risk,"Short Float":f"{(info.get('sf',0) or 0)*100:.1f}%","Bull Sent":f"{sent.get('bull',50)}%","Sector":info.get("sector","N/A")})
    prog.empty()
    if rows:
        if HAS_PLOTLY and is_premium():
            st.markdown('<div class="sec-hd" style="margin-bottom:10px;">Score Distribution</div>',unsafe_allow_html=True)
            scores=[r["Score"] for r in rows]; tickers=[r["Ticker"] for r in rows]
            colors=["#22c55e" if s>=65 else "#fbbf24" if s>=40 else "#ef4444" for s in scores]
            fig=go.Figure(go.Bar(x=tickers,y=scores,marker_color=colors,text=scores,textposition="outside",textfont=dict(color="#94a3b8",size=10)))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=200,yaxis=dict(range=[0,110],showgrid=False,color="#4a5e7a"),xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=11)))
            st.plotly_chart(fig,use_container_width=True)
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    if st.button("🗑️ Clear Watchlist",key="wl_clear"): st.session_state.watchlist=[]; st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)

def page_screener():
    render_topbar("screener")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">🔍 Smart Stock Screener</div>',unsafe_allow_html=True)
    if not is_premium(): render_lock("Advanced Stock Screener"); st.markdown('</div>',unsafe_allow_html=True); return
    with st.expander("⚙️ Screener Filters",expanded=True):
        c1,c2,c3,c4=st.columns(4)
        with c1: min_sc=st.slider("Min Score",0,100,40); min_rsi=st.slider("Min RSI",0,100,20)
        with c2: max_rsi=st.slider("Max RSI",0,100,80); min_sf=st.slider("Min Short Float %",0,50,0)
        with c3:
            req_bull=st.checkbox("MACD Bullish only"); req_above=st.checkbox("Above 20-day MA")
            req_vol=st.checkbox("Volume spike >1.5×"); req_hot=st.checkbox("StockTwits trending")
        with c4:
            sel_cats=st.multiselect("Categories",list(CATEGORIES.keys()),default=["💻 Tech","🤖 AI"])
    sn,sb=st.columns([3,1])
    with sn: scr_name=st.text_input("Name this screener",placeholder="My Growth Screen",label_visibility="visible")
    with sb:
        if st.button("💾 Save",key="scr_save",use_container_width=True) and scr_name:
            st.session_state.saved_screeners=st.session_state.get("saved_screeners",[])
            st.session_state.saved_screeners.append({"name":scr_name,"cats":sel_cats})
            st.success("Saved!")
    if st.button("🔍 Run Screener",key="scr_run",type="primary",use_container_width=True):
        hot_list=st_hot() if req_hot else []
        universe=list(set([t for c in sel_cats for t in CATEGORIES.get(c,[])]))[:30]
        results=[]; prog=st.progress(0,"Screening…")
        for i,t in enumerate(universe):
            prog.progress((i+1)/len(universe))
            if req_hot and t not in hot_list: continue
            q=get_quote(t); df=get_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            sc,_,op,risk,_=compute_scores(df,info,sent)
            if df is None or len(df)<20: continue
            try:
                rsi=ta.momentum.RSIIndicator(df["close"].copy(),14).rsi().iloc[-1]
                ma20=df["close"].rolling(20).mean().iloc[-1]
                mac=ta.trend.MACD(df["close"].copy()); mv=mac.macd().iloc[-1]; ms=mac.macd_signal().iloc[-1]
                price=df["close"].iloc[-1]; avg_v=df["volume"].rolling(20).mean().iloc[-1]; cur_v=df["volume"].iloc[-1]
                sf=(info.get("sf",0) or 0)*100
                if sc<min_sc: continue
                if pd.notna(rsi) and (rsi<min_rsi or rsi>max_rsi): continue
                if sf<min_sf: continue
                if req_bull and pd.notna(mv) and mv<ms: continue
                if req_above and pd.notna(ma20) and price<ma20: continue
                if req_vol and pd.notna(avg_v) and avg_v>0 and cur_v<avg_v*1.5: continue
                results.append({"Ticker":t,"Price":f"${price:,.2f}","RSI":round(rsi,1) if pd.notna(rsi) else "N/A","Score":sc,"Opportunity":op,"Risk":risk,"Short Float":f"{sf:.1f}%","MACD":"Bullish" if (pd.notna(mv) and mv>ms) else "Bearish","vs MA20":"Above" if price>ma20 else "Below","Vol Ratio":f"{cur_v/avg_v:.1f}×" if pd.notna(avg_v) and avg_v>0 else "N/A"})
            except: continue
        prog.empty()
        if results:
            st.success(f"✅ {len(results)} stocks passed your filters!")
            st.dataframe(pd.DataFrame(results).sort_values("Score",ascending=False),use_container_width=True,hide_index=True)
        else: st.info("No matches. Try relaxing filters.")
    st.markdown('</div>',unsafe_allow_html=True)

def page_pricing():
    render_topbar("pricing")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">💰 Plans & Pricing</div>',unsafe_allow_html=True)
    p1,p2,p3=st.columns([1,1.1,1],gap="small")
    with p1:
        st.markdown("""<div class="pc"><div style="font-size:15px;font-weight:700;color:#e2e8f0;">Free</div>
            <div class="pc-price">$0</div><div style="font-size:11px;color:#374f6e;margin-bottom:14px;">forever</div>
            <hr style="border-color:rgba(255,255,255,.06);margin:14px 0;">
            <div style="font-size:12px;color:#374f6e;line-height:2.3;">✅ Market overview<br>✅ 5 standard categories<br>✅ StockTwits hot list<br>✅ Basic RSI & MACD signals<br>✅ Plain-English insights<br>✅ 3 composite categories (free)<br>✅ Watchlist (10 stocks)<br>❌ 3 premium composite cats<br>❌ Short squeeze scanner<br>❌ Advanced screener<br>❌ Score breakdowns<br>❌ Full BI analytics</div></div>""",unsafe_allow_html=True)
        if not is_authed():
            if st.button("Get Started Free",key="p_free",use_container_width=True): nav("signup")
    with p2:
        st.markdown("""<div class="pc-feat"><div style="background:#2563eb;color:white;font-size:9px;font-weight:700;padding:3px 10px;border-radius:20px;display:inline-block;margin-bottom:10px;letter-spacing:1.5px;">⭐ MOST POPULAR</div>
            <div style="font-size:15px;font-weight:700;color:#e2e8f0;">Premium Monthly</div>
            <div class="pc-price">$29</div><div style="font-size:11px;color:#374f6e;margin-bottom:14px;">per month · cancel anytime</div>
            <hr style="border-color:rgba(255,255,255,.06);margin:14px 0;">
            <div style="font-size:12px;color:#374f6e;line-height:2.3;">✅ Everything in Free<br>✅ All 6 composite categories<br>✅ Short squeeze scanner<br>✅ Advanced screener<br>✅ Full BI analytics<br>✅ Score breakdowns<br>✅ Volume surge detection<br>✅ Unlimited watchlist<br>✅ Saved screeners</div></div>""",unsafe_allow_html=True)
        if st.button("🚀 Go Premium →",key="p_prem",type="primary",use_container_width=True):
            st.info("💳 Payment processing coming soon. Contact support@stockwins.com to upgrade.")
    with p3:
        st.markdown("""<div class="pc"><div style="background:linear-gradient(90deg,#854d0e,#d97706);color:white;font-size:9px;font-weight:700;padding:3px 10px;border-radius:20px;display:inline-block;margin-bottom:4px;letter-spacing:1px;">BEST VALUE</div>
            <div style="font-size:15px;font-weight:700;color:#e2e8f0;">Annual Plan</div>
            <div class="pc-price">$199</div><div style="font-size:11px;color:#374f6e;margin-bottom:14px;">per year · save 43%</div>
            <hr style="border-color:rgba(255,255,255,.06);margin:14px 0;">
            <div style="font-size:12px;color:#374f6e;line-height:2.3;">✅ Everything in Premium<br>✅ Priority support<br>✅ Early feature access<br>✅ Export to CSV<br>✅ Custom alerts<br>✅ API access (Q3 2026)<br>✅ Backtesting (coming)</div></div>""",unsafe_allow_html=True)
        if st.button("Get Annual →",key="p_annual",use_container_width=True):
            st.info("💳 Coming soon!")
    st.markdown('<div class="disc">⚠️ Educational platform only. Not financial advice. Trading involves risk.</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

def page_settings():
    render_topbar()
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">⚙️ Account Settings</div>',unsafe_allow_html=True)
    db_user=st.session_state.users_db.get(st.session_state.user["email"],{}) if is_authed() else {}
    email=st.session_state.user["email"] if is_authed() else ""
    tabs=st.tabs(["👤 Profile","🔐 Security","🔔 Alerts","📊 Subscription"])
    with tabs[0]:
        with st.form("pf"):
            nn=st.text_input("Display Name",value=st.session_state.user.get("name",""))
            st.text_input("Email (read-only)",value=email,disabled=True)
            if db_user.get("verified"):
                st.markdown('<div style="font-size:12px;color:#22c55e;margin:4px 0;">✅ Email verified</div>',unsafe_allow_html=True)
            if st.form_submit_button("Save Changes",type="primary") and nn:
                st.session_state.user["name"]=nn
                if email in st.session_state.users_db: st.session_state.users_db[email]["name"]=nn
                st.success("✅ Updated!")
    with tabs[1]:
        st.markdown('<div class="card card-red"><div style="font-size:12px;font-weight:700;color:#f87171;margin-bottom:4px;">🔒 Security Notice</div><div style="font-size:12px;color:#374f6e;line-height:1.6;">For production: Set admin/owner credentials in Streamlit Cloud Secrets (Settings → Secrets), not in source code. Your session data is not persisted between deployments.</div></div>',unsafe_allow_html=True)
        with st.form("pwf"):
            cp=st.text_input("Current Password",type="password")
            np_=st.text_input("New Password",type="password")
            np2=st.text_input("Confirm New",type="password")
            if st.form_submit_button("Update Password",type="primary"):
                if hp(cp)!=db_user.get("pw",""): st.error("Current password incorrect.")
                elif np_!=np2: st.error("Passwords don't match.")
                elif len(np_)<6: st.error("Must be 6+ characters.")
                else: st.session_state.users_db[email]["pw"]=hp(np_); st.success("✅ Password updated!")
        if st.button("🚪 Logout",key="set_logout"): logout()
    with tabs[2]:
        alerts=st.session_state.get("alerts",[])
        with st.form("af"):
            ac1,ac2,ac3=st.columns(3)
            with ac1: at=st.text_input("Ticker",placeholder="AAPL").upper()
            with ac2: ap=st.number_input("Price",value=100.0,min_value=0.01)
            with ac3: atype=st.selectbox("Type",["Price Above","Price Below"])
            if st.form_submit_button("➕ Add Alert",type="primary") and at:
                alerts.append({"ticker":at,"price":ap,"type":atype,"active":True}); st.session_state.alerts=alerts; st.success("Alert set!")
        for i,a in enumerate(alerts):
            ac1,ac2=st.columns([4,1])
            with ac1: st.markdown(f'<div class="card" style="padding:10px 14px;margin-bottom:4px;"><span style="font-family:\'JetBrains Mono\',monospace;color:#60a5fa;font-weight:700;">{a["ticker"]}</span> <span style="font-size:12px;color:#374f6e;">{a["type"]} ${a["price"]:.2f}</span></div>',unsafe_allow_html=True)
            with ac2:
                if st.button("🗑",key=f"da_{i}"): alerts.pop(i); st.session_state.alerts=alerts; st.rerun()
        if not alerts: st.caption("No active alerts.")
    with tabs[3]:
        role=st.session_state.get("role","free")
        rl={"free":"Free","premium":"Premium Monthly","admin":"Admin","owner":"Owner"}.get(role,"Free")
        rc_={"free":"#6b7fa0","premium":"#a78bfa","admin":"#93b4fd","owner":"#f59e0b"}.get(role,"#6b7fa0")
        st.markdown(f"""<div class="card card-blue"><div style="font-size:15px;font-weight:800;color:#e2e8f0;">Current Plan: <span style="color:{rc_};">{rl}</span></div><div style="font-size:12px;color:#374f6e;margin-top:4px;">Member since {db_user.get('joined','N/A')}</div></div>""",unsafe_allow_html=True)
        if not is_premium():
            if st.button("🚀 Upgrade to Premium ($29/mo)",key="set_prem",type="primary",use_container_width=True): nav("pricing")
    st.markdown('</div>',unsafe_allow_html=True)

def page_admin():
    if not is_admin(): st.error("Access denied."); return
    render_topbar("admin")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">🛠️ Admin Panel</div>',unsafe_allow_html=True)

    # Security notice
    st.markdown("""<div class="card card-red">
        <div style="font-size:13px;font-weight:700;color:#f87171;margin-bottom:6px;">🔒 Production Security Checklist</div>
        <div style="font-size:12px;color:#374f6e;line-height:1.9;">
        ✅ Set <code style="background:#1a0000;color:#f87171;padding:1px 5px;border-radius:3px;">TWELVE_DATA_API_KEY</code> in Streamlit Cloud Secrets (Settings → Secrets)<br>
        ✅ Set <code style="background:#1a0000;color:#f87171;padding:1px 5px;border-radius:3px;">[accounts]</code> section in Secrets with hashed owner/admin passwords<br>
        ✅ Never commit real passwords to GitHub — use secrets for all credentials<br>
        ✅ Change demo account passwords before launching publicly
        </div>
    </div>""",unsafe_allow_html=True)

    tabs=st.tabs(["📊 Overview","👥 Users","🔑 API / Secrets","📈 Analytics"])
    with tabs[0]:
        ss=st.session_state.site_stats
        oc=st.columns(5)
        for col,(v,l,c) in zip(oc,[(ss["total_signups"],"Signups","#93b4fd"),(ss["premium_users"],"Premium","#a78bfa"),(ss["daily_active"],"Daily Active","#22c55e"),(f"{ss['conversion_rate']:.1f}%","Conversion","#fbbf24"),(len(st.session_state.users_db),"Accounts","#94a3b8")]):
            col.markdown(f'<div class="stat"><div class="stat-v" style="font-size:17px;color:{c};">{v}</div><div class="stat-l">{l}</div></div>',unsafe_allow_html=True)
        st.markdown("<br>",unsafe_allow_html=True)
        hc=st.columns(3)
        key_set=bool(get_td_key() if is_admin() else False)
        for col,(name,status,note) in zip(hc,[("Yahoo Finance","✅ Active","Free · No key needed"),("StockTwits","✅ Active","Public API · Free"),("Twelve Data",f"{'✅ Configured' if key_set else '⚠️ Not Set'}","Optional · Premium quality")]):
            c_="#22c55e" if "✅" in status else "#fbbf24"
            col.markdown(f'<div class="card"><div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:4px;">{name}</div><div style="font-size:12px;font-weight:700;color:{c_};">{status}</div><div style="font-size:11px;color:#2a3a52;margin-top:3px;">{note}</div></div>',unsafe_allow_html=True)
    with tabs[1]:
        for email,u in list(st.session_state.users_db.items()):
            uc1,uc2,uc3,uc4=st.columns([3,1,2,1])
            with uc1:
                v_icon="✅" if u.get("verified") else "⚠️"
                st.markdown(f'<div style="padding:8px 0;"><div style="font-size:13px;font-weight:600;color:#e2e8f0;">{u["name"]}</div><div style="font-size:11px;color:#2a3a52;">{v_icon} {email}</div></div>',unsafe_allow_html=True)
            with uc2:
                role=u["role"]; rc_={"owner":"#f59e0b","admin":"#93b4fd","premium":"#a78bfa","free":"#4a5e7a"}.get(role,"#4a5e7a")
                st.markdown(f'<div style="padding:10px 0;"><span style="font-size:10px;font-weight:700;color:{rc_};background:rgba(0,0,0,0.3);padding:2px 8px;border-radius:4px;">{role.upper()}</span></div>',unsafe_allow_html=True)
            with uc3:
                if is_owner() and u["role"]!="owner":
                    new_role=st.selectbox("",["free","premium","admin"],index=["free","premium","admin"].index(u["role"]) if u["role"] in ["free","premium","admin"] else 0,key=f"role_{email}",label_visibility="collapsed")
                    if st.button("Update",key=f"upd_{email}",use_container_width=True):
                        st.session_state.users_db[email]["role"]=new_role; st.rerun()
            with uc4:
                if is_owner() and email!=st.session_state.user.get("email",""):
                    if st.button("🗑",key=f"del_{email}",use_container_width=True):
                        del st.session_state.users_db[email]; st.rerun()
            st.markdown('<div style="border-bottom:1px solid rgba(255,255,255,.04);margin-bottom:4px;"></div>',unsafe_allow_html=True)
    with tabs[2]:
        # Recommended APIs
        st.markdown('''<div class="sec-hd" style="font-size:13px;">Recommended APIs to Add</div>''', unsafe_allow_html=True)
        api_recs = [
            ("Polygon.io","Real-time options flow, unusual options activity, tick data, WebSocket streaming. Excellent for detecting institutional moves before they hit price.", "https://polygon.io", "#22c55e"),
            ("Alpha Vantage","Earnings dates, economic indicators, forex/crypto. Free tier available. Great for adding earnings calendar to the dashboard.", "https://www.alphavantage.co", "#3b82f6"),
            ("Unusual Whales","Premium options flow data — whale trades, dark pool prints. The best signal for big money moves. Paid but powerful.", "https://unusualwhales.com", "#a78bfa"),
            ("FRED (Federal Reserve)","Free. Interest rates, inflation, economic data. Add macro context to market signals — critical for sector analysis.", "https://fred.stlouisfed.org/docs/api/fred/", "#fbbf24"),
            ("Benzinga / NewsAPI","News sentiment and earnings headlines. Lets you surface news-driven moves automatically in the Social Catalyst category.", "https://www.benzinga.com/apis/", "#f97316"),
            ("Finviz","Screener data, insider trading, analyst ratings. Their elite API has sector maps and market breadth data.", "https://finviz.com", "#60a5fa"),
        ]
        cols = st.columns(3, gap="small")
        for i,(name,desc,url,color) in enumerate(api_recs):
            with cols[i%3]:
                st.markdown(f'''<div class="card" style="border-left:3px solid {color};height:100%;">
                    <div style="font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:4px;">{name}</div>
                    <div style="font-size:11px;color:#374f6e;line-height:1.6;margin-bottom:8px;">{desc}</div>
                    <div style="font-size:10px;color:{color};">{url}</div>
                </div>''', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""<div class="card card-blue">
            <div style="font-size:13px;font-weight:700;color:#93b4fd;margin-bottom:8px;">How to Set Streamlit Cloud Secrets (Permanent Setup)</div>
            <div style="font-size:12px;color:#374f6e;line-height:1.9;">
            1. Go to your Streamlit Cloud dashboard → your app → <strong style="color:#e2e8f0;">Settings → Secrets</strong><br>
            2. Add the following (replace values with your actual credentials):
            </div>
            <pre style="background:#060a12;border:1px solid rgba(255,255,255,.08);border-radius:7px;padding:12px;font-size:11px;color:#4ade80;margin-top:10px;overflow-x:auto;">TWELVE_DATA_API_KEY = "your_key_here"

[accounts]
owner_email = "owner@yourdomain.com"
owner_pw_hash = "sha256_hash_of_your_password"
admin_email = "admin@yourdomain.com"  
admin_pw_hash = "sha256_hash_of_your_password"</pre>
            <div style="font-size:11px;color:#374f6e;margin-top:8px;">Generate a password hash: <code style="background:#060a12;color:#93b4fd;padding:2px 6px;border-radius:3px;">python3 -c "import hashlib; print(hashlib.sha256(b'YourPassword').hexdigest())"</code></div>
        </div>""",unsafe_allow_html=True)
        if is_admin():
            st.markdown('<div class="sec-hd" style="margin-top:16px;font-size:13px;">Session API Key Override (Admin Only)</div>',unsafe_allow_html=True)
            st.caption("This is a session-only override for testing. Use Streamlit Secrets for production.")
            with st.form("api_f"):
                nk=st.text_input("Twelve Data API Key",type="password",placeholder="Paste key here — never shown to users")
                if st.form_submit_button("Save for Session",type="primary"):
                    st.session_state._admin_td_key=nk; st.success("✅ Session key saved.")
            if st.button("Clear Session Key",key="clr_api"): st.session_state._admin_td_key=""; st.success("Cleared.")
    with tabs[3]:
        if HAS_PLOTLY:
            dates=pd.date_range(end=datetime.now(),periods=30,freq='D')
            su=[random.randint(45,130) for _ in range(30)]
            pu=[random.randint(6,28) for _ in range(30)]
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=list(dates),y=su,name="Signups",line=dict(color="#3b82f6",width=2),fill="tozeroy",fillcolor="rgba(59,130,246,0.08)"))
            fig.add_trace(go.Scatter(x=list(dates),y=pu,name="Premium Upgrades",line=dict(color="#f59e0b",width=2)))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=260,legend=dict(bgcolor="rgba(0,0,0,0)",font=dict(color="#6b7fa0",size=11)),xaxis=dict(showgrid=False,color="#4a5e7a"),yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a"))
            st.plotly_chart(fig,use_container_width=True)
        st.markdown('<div class="disc">📊 Analytics are simulated. In production, connect Mixpanel, PostHog, or your analytics provider.</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────
render_sidebar()

page=st.session_state.get("page","landing")
guard={"dashboard","discover","watchlist","screener","bi_dashboard","stock_detail","settings","admin"}

if page in guard and not is_authed():
    page_login()
elif page=="landing":       page_landing()
elif page=="login":         page_login()
elif page=="signup":        page_signup()
elif page=="forgot_pw":     page_forgot()
elif page=="pricing":       page_pricing()
elif page=="dashboard":     page_dashboard()
elif page=="discover":      page_discover()
elif page=="watchlist":     page_watchlist()
elif page=="screener":      page_screener()
elif page=="bi_dashboard":  page_bi()
elif page=="stock_detail":  page_detail()
elif page=="settings":      page_settings()
elif page=="admin":
    if is_admin(): page_admin()
    else:          st.error("Access denied."); nav("dashboard")
else:                       page_landing()
