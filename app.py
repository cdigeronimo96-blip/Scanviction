# ═══════════════════════════════════════════════════════════════
# STOCKWINS v7.0 — Premium Fintech SaaS
# "I trust this. I understand this. I want more."
# ═══════════════════════════════════════════════════════════════

import streamlit as st
import requests, pandas as pd, ta, yfinance as yf
import hashlib, time, random
from datetime import datetime, timedelta

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

st.set_page_config(
    page_title="StockWins | Spot Market Opportunities First",
    page_icon="📈", layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# SECURITY
# ─────────────────────────────────────────────────────────────
def _hp(pw): return hashlib.sha256(pw.encode()).hexdigest()
def hp(pw):  return hashlib.sha256(pw.encode()).hexdigest()

def _load_seed_accounts():
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        try:    accts = st.secrets["accounts"]
        except: accts = st.secrets
        oe=accts.get("owner_email",""); oh=accts.get("owner_pw_hash","")
        ae=accts.get("admin_email",""); ah=accts.get("admin_pw_hash","")
        if oe and oh:
            r = {
                oe: {"pw":oh,"name":"Owner","role":"owner","verified":True,"joined":today,"plan":"Annual"},
                "demo@stockwins.com":    {"pw":_hp("demo123"), "name":"Demo User",  "role":"free",   "verified":True,"joined":today,"plan":"Free"},
                "premium@stockwins.com": {"pw":_hp("premium1"),"name":"Alex Rivera","role":"premium","verified":True,"joined":today,"plan":"Monthly"},
            }
            if ae and ah: r[ae]={"pw":ah,"name":"Admin","role":"admin","verified":True,"joined":today,"plan":"Annual"}
            return r
    except: pass
    return {
        "demo@stockwins.com":    {"pw":_hp("demo123"), "name":"Demo User",  "role":"free",   "verified":True,"joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Free"},
        "premium@stockwins.com": {"pw":_hp("premium1"),"name":"Alex Rivera","role":"premium","verified":True,"joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Monthly"},
        "admin@stockwins.com":   {"pw":_hp("admin_change_me"),"name":"Admin","role":"admin","verified":True,"joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Annual"},
        "owner@stockwins.com":   {"pw":_hp("owner_change_me"),"name":"Owner","role":"owner","verified":True,"joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Annual"},
    }

def get_td_key():
    try:
        k=st.secrets.get("TWELVE_DATA_API_KEY","")
        if k: return k
    except: pass
    if is_admin(): return st.session_state.get("_admin_td_key","")
    return ""

# ─────────────────────────────────────────────────────────────
# DESIGN SYSTEM
# ─────────────────────────────────────────────────────────────
GOLD   = "#f59e0b"
GOLD2  = "#d97706"
BLUE   = "#2563eb"
GREEN  = "#22c55e"
RED    = "#ef4444"
BG     = "#07090f"
CARD   = "#0d1525"
BORDER = "rgba(255,255,255,0.08)"

# ─────────────────────────────────────────────────────────────
# CSS — Full Premium Design System
# ─────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap');

*,*::before,*::after{{box-sizing:border-box;}}
html,body,[data-testid="stAppViewContainer"]{{
    background:{BG} !important;color:#d1d9e6 !important;
    font-family:'Inter',-apple-system,sans-serif !important;
}}
[data-testid="stHeader"],#MainMenu,footer,[data-testid="stDecoration"]{{display:none !important;}}
div.block-container{{padding:0 !important;max-width:100% !important;}}
section.main>div{{padding-top:0 !important;}}

/* ── Sidebar ── */
[data-testid="stSidebar"]{{
    background:#080c18 !important;
    border-right:1px solid {BORDER} !important;
    width:225px !important;min-width:225px !important;max-width:225px !important;
}}
[data-testid="stSidebar"]>div{{padding:0 !important;}}

/* ── Base Button ── */
.stButton>button{{
    background:rgba(255,255,255,0.05) !important;
    border:1px solid rgba(255,255,255,0.18) !important;
    color:#b8cce0 !important;
    border-radius:8px !important;
    font-family:'Inter',sans-serif !important;
    font-size:13px !important;font-weight:500 !important;
    padding:8px 16px !important;
    min-height:40px !important;
    transition:all 0.15s ease !important;
    width:100% !important;
    display:flex !important;align-items:center !important;justify-content:center !important;
}}
.stButton>button:hover{{
    background:rgba(37,99,235,0.12) !important;
    border-color:rgba(37,99,235,0.5) !important;
    color:#93b4fd !important;
}}
.stButton>button[kind="primary"]{{
    background:{BLUE} !important;
    border-color:{BLUE} !important;color:#fff !important;font-weight:700 !important;
}}
.stButton>button[kind="primary"]:hover{{
    background:#1d4ed8 !important;
    box-shadow:0 4px 16px rgba(37,99,235,0.4) !important;
}}

/* ── Sidebar nav ── */
[data-testid="stSidebar"] .stButton>button{{
    background:transparent !important;border:none !important;
    border-left:2px solid transparent !important;border-radius:0 !important;
    color:#4a5e7a !important;font-size:13px !important;font-weight:500 !important;
    padding:9px 18px !important;text-align:left !important;
    min-height:38px !important;margin:1px 0 !important;
    justify-content:flex-start !important;
}}
[data-testid="stSidebar"] .stButton>button:hover{{
    background:rgba(37,99,235,0.08) !important;
    border-left-color:{BLUE} !important;color:#93b4fd !important;
    border-top:none !important;border-right:none !important;border-bottom:none !important;
}}

/* ── Gold premium button ── */
.gold-btn .stButton>button,
button[aria-label="👑 Go Premium"],
button[aria-label="👑 Unlock Premium"],
button[aria-label="👑 Upgrade to Premium"] {{
    background:linear-gradient(135deg,#92400e 0%,{GOLD2} 35%,{GOLD} 60%,#fcd34d 100%) !important;
    border:1px solid {GOLD} !important;
    color:#1a0800 !important;font-weight:800 !important;font-size:14px !important;
    box-shadow:0 4px 20px rgba(245,158,11,0.4),0 0 0 1px rgba(245,158,11,0.2) !important;
    border-radius:10px !important;min-height:48px !important;letter-spacing:0.3px !important;
}}
button[aria-label="👑 Go Premium"]:hover,
button[aria-label="👑 Unlock Premium"]:hover,
button[aria-label="👑 Upgrade to Premium"]:hover {{
    background:linear-gradient(135deg,#b45309 0%,{GOLD} 40%,#fcd34d 70%,#fef3c7 100%) !important;
    box-shadow:0 8px 32px rgba(245,158,11,0.6),0 0 0 1px rgba(245,158,11,0.4) !important;
    transform:translateY(-1px) !important;
}}

/* ── Nav CSS ── */
.sw-nav .stButton>button{{
    font-size:13px !important;font-weight:500 !important;
    padding:6px 12px !important;min-height:38px !important;height:38px !important;
    border:1px solid rgba(255,255,255,0.15) !important;
    background:rgba(255,255,255,0.04) !important;color:#a8bdd4 !important;
    border-radius:7px !important;white-space:nowrap !important;width:100% !important;
}}
.sw-nav .stButton>button:hover{{
    border-color:rgba(37,99,235,0.5) !important;
    background:rgba(37,99,235,0.1) !important;color:#93b4fd !important;
}}
.sw-nav .stButton>button[kind="primary"]{{
    background:{BLUE} !important;border-color:{BLUE} !important;
    color:#fff !important;font-weight:700 !important;
}}

/* ── Logo overlay ── */
.element-container:has(.sw-logo-click-target)+.element-container{{
    height:0px !important;overflow:visible !important;margin:0 !important;padding:0 !important;
}}
.element-container:has(.sw-logo-click-target)+.element-container .stButton>button{{
    position:relative !important;top:-48px !important;left:0 !important;
    width:180px !important;height:48px !important;min-height:48px !important;
    opacity:0 !important;cursor:pointer !important;z-index:999 !important;
    background:transparent !important;border:none !important;box-shadow:none !important;
}}

/* ── Topbar vertical center ── */
[data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:first-of-type{{
    align-items:center !important;min-height:60px !important;
}}
[data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:first-of-type>[data-testid="column"]{{
    display:flex !important;align-items:center !important;
    padding-top:0 !important;padding-bottom:0 !important;
}}
[data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:first-of-type>[data-testid="column"]>div{{width:100% !important;}}

/* ── Cards ── */
.card{{background:{CARD};border:1px solid {BORDER};border-radius:10px;padding:16px;margin-bottom:10px;transition:border-color 0.2s;}}
.card:hover{{border-color:rgba(37,99,235,0.3);}}
.card-blue{{background:linear-gradient(135deg,#05112a,{CARD});border-color:rgba(37,99,235,0.25);}}
.card-gold{{background:linear-gradient(135deg,#120d00,{CARD});border-color:rgba(245,158,11,0.3);}}
.card-green{{background:linear-gradient(135deg,#001a0e,{CARD});border-color:rgba(34,197,94,0.25);}}
.card-purple{{background:linear-gradient(135deg,#0e0520,{CARD});border-color:rgba(139,92,246,0.25);}}

/* ── Pricing cards ── */
.price-card{{
    background:{CARD};border:1px solid {BORDER};border-radius:14px;
    padding:28px 24px;height:100%;
    transition:all 0.25s ease;
}}
.price-card:hover{{
    border-color:rgba(37,99,235,0.5);
    box-shadow:0 8px 32px rgba(37,99,235,0.15);
    transform:translateY(-2px);
}}
.price-card-featured{{
    background:linear-gradient(160deg,#060f2a,{CARD});
    border:2px solid {BLUE};border-radius:14px;padding:28px 24px;height:100%;
    box-shadow:0 8px 40px rgba(37,99,235,0.2);
    transition:all 0.25s ease;
}}
.price-card-featured:hover{{
    border-color:#3b82f6;box-shadow:0 16px 60px rgba(37,99,235,0.35);
    transform:translateY(-3px);
}}
.price-card-gold{{
    background:linear-gradient(160deg,#1a0d00,#120800,{CARD});
    border:2px solid {GOLD};border-radius:14px;padding:28px 24px;height:100%;
    box-shadow:0 8px 40px rgba(245,158,11,0.2);
    transition:all 0.25s ease;
}}
.price-card-gold:hover{{
    border-color:#fcd34d;box-shadow:0 16px 60px rgba(245,158,11,0.35);
    transform:translateY(-3px);
}}

/* ── Stock row ── */
.sr{{background:{CARD};border:1px solid {BORDER};border-radius:10px;padding:14px 16px;
     margin-bottom:6px;transition:all 0.15s ease;cursor:pointer;}}
.sr:hover{{border-color:rgba(37,99,235,0.4);background:#101828;}}
.sr-tick{{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#60a5fa;}}
.sr-name{{font-size:11px;color:#2a3a52;margin-top:2px;}}
.sr-why{{font-size:12px;color:#3d5270;margin-top:4px;line-height:1.5;}}
.sr-price{{font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:#e2e8f0;}}

/* ── Badges ── */
.b{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;margin-right:3px;vertical-align:middle;}}
.b-bull{{background:#05260f;color:#4ade80;border:1px solid rgba(74,222,128,.3);}}
.b-bear{{background:#260505;color:#f87171;border:1px solid rgba(248,113,113,.3);}}
.b-neu {{background:#151b28;color:#64748b;border:1px solid rgba(100,116,139,.3);}}
.b-hot {{background:#260d00;color:#fb923c;border:1px solid rgba(251,146,60,.3);}}
.b-prem{{background:#201000;color:{GOLD};border:1px solid rgba(245,158,11,.3);}}
.b-blue{{background:#060f2a;color:#93b4fd;border:1px solid rgba(147,180,253,.3);}}

/* Score pill */
.sp{{display:inline-block;padding:3px 10px;border-radius:5px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;}}
.sp-hi{{background:#05260f;color:#4ade80;border:1px solid rgba(74,222,128,.3);}}
.sp-md{{background:#201000;color:{GOLD};border:1px solid rgba(245,158,11,.3);}}
.sp-lo{{background:#260505;color:#f87171;border:1px solid rgba(248,113,113,.3);}}

/* Index widget */
.idx-w{{background:{CARD};border:1px solid {BORDER};border-radius:9px;padding:14px 16px;}}
.idx-name{{font-size:10px;color:#4a5e7a;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;}}
.idx-price{{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;}}

/* Insight block */
.ins{{background:#0a1020;border-left:3px solid {BLUE};border-radius:0 7px 7px 0;padding:11px 14px;margin:5px 0;}}
.ins-bull{{border-left-color:{GREEN};}}
.ins-bear{{border-left-color:{RED};}}
.ins-label{{font-size:12px;font-weight:700;color:#c9d3e0;margin-bottom:4px;}}
.ins-text{{font-size:12px;color:#374f6e;line-height:1.6;}}

/* Section header */
.sec-hd{{font-size:15px;font-weight:700;color:#e2e8f0;display:flex;align-items:center;gap:8px;
         padding-bottom:10px;border-bottom:1px solid {BORDER};margin-bottom:14px;}}

/* Tags */
.tag{{font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;}}
.tag-free{{background:rgba(34,197,94,0.12);color:#4ade80;border:1px solid rgba(34,197,94,0.3);}}
.tag-prem{{background:rgba(245,158,11,0.12);color:{GOLD};border:1px solid rgba(245,158,11,0.3);}}
.tag-live{{background:rgba(37,99,235,0.12);color:#93b4fd;border:1px solid rgba(37,99,235,0.3);}}

/* Stats */
.stat{{background:{CARD};border:1px solid {BORDER};border-radius:9px;padding:12px 14px;text-align:center;}}
.stat-v{{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;color:#e2e8f0;}}
.stat-l{{font-size:10px;color:#2a3a52;text-transform:uppercase;letter-spacing:.5px;margin-top:3px;}}

/* Mover row */
.mv{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;
     border-bottom:1px solid rgba(255,255,255,.04);font-size:13px;}}
.mv:last-child{{border-bottom:none;}}

/* Lock */
.lock{{background:rgba(7,9,15,.96);border:1px solid rgba(245,158,11,.3);border-radius:10px;padding:36px 24px;text-align:center;}}

/* Disclaimer */
.disc{{background:#0a1020;border-left:3px solid #854d0e;border-radius:0 7px 7px 0;padding:12px 16px;font-size:11px;color:#2a3752;line-height:1.7;}}

/* Page padding */
.pg{{padding:20px 28px 40px;}}
.div-line{{border-bottom:1px solid {BORDER};margin:20px 0;}}

/* Hero */
.hero-h1{{font-size:48px;font-weight:900;color:#f1f5f9;line-height:1.05;letter-spacing:-2px;margin-bottom:12px;}}
.hero-h1 .hi{{color:{BLUE};}}
.hero-h1 .hg{{color:{GOLD};}}
.hero-sub{{font-size:16px;color:#3d5270;line-height:1.75;max-width:480px;margin-bottom:28px;}}

/* Forms */
.stTextInput>div>div>input,.stTextArea>div>div>textarea,.stSelectbox>div>div{{
    background:#0e1421 !important;border:1px solid rgba(255,255,255,.1) !important;
    color:#d1d9e6 !important;border-radius:7px !important;font-family:'Inter',sans-serif !important;font-size:13px !important;
}}
.stTextInput>div>div>input:focus{{border-color:{BLUE} !important;box-shadow:0 0 0 3px rgba(37,99,235,.15) !important;}}
[data-testid="InputInstructions"]{{display:none !important;}}
.stTextInput>div{{margin-bottom:0 !important;}}
.streamlit-expanderHeader{{background:#0e1421 !important;border:1px solid {BORDER} !important;border-radius:7px !important;color:#6b7fa0 !important;font-size:13px !important;}}
.streamlit-expanderContent{{background:#0a1020 !important;border:1px solid {BORDER} !important;border-top:none !important;}}
[data-testid="stTabs"]>div{{border-color:{BORDER} !important;}}
[data-testid="stTab"]{{font-size:13px !important;font-weight:500 !important;color:#4a5e7a !important;}}
[aria-selected="true"][data-testid="stTab"]{{color:#93b4fd !important;border-bottom-color:{BLUE} !important;}}
.stProgress>div>div{{background:#141927 !important;height:5px !important;border-radius:3px !important;}}
.stProgress>div>div>div{{background:linear-gradient(90deg,{BLUE},#3b82f6) !important;border-radius:3px !important;}}
[data-testid="stDataFrame"]{{border:1px solid {BORDER} !important;border-radius:10px !important;overflow:hidden !important;}}

/* Footer */
.sw-footer-wrap{{
    width:100vw;margin-left:calc(-50vw + 50%);
    background:#050810;border-top:1px solid {BORDER};
    padding:40px 64px 28px;margin-top:40px;box-sizing:border-box;
}}

/* Equal column heights */
[data-testid="column"]{{display:flex;flex-direction:column;}}
[data-testid="column"]>.element-container{{flex:1;display:flex;flex-direction:column;}}
[data-testid="column"] .stButton{{display:flex;}}
[data-testid="column"] .stButton>button{{flex:1;}}
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
    "🔥💥 Squeeze + Buzz":    ("High short float stocks trending on StockTwits — social momentum meets squeeze fuel", "free"),
    "💡 Hidden Movers":       ("Strong technical scores with low social noise — find them before the crowd arrives", "free"),
    "🎭 Social Catalyst":     ("StockTwits activity spiking + abnormal volume = catalyst-driven momentum today", "free"),
    "🌡️ Sentiment Flip":      ("Bullish % rose 15+ points recently — trader mood sharply reversing upward", "free"),
    "📉→📈 Fallen Angels":   ("Down 30%+ recently but RSI oversold and volume quietly returning — recovery watch", "free"),
    "🔬 Micro-Cap Movers":   ("Market cap under $2B with volume spike + RSI building — early-stage high-reward setups", "free"),
    "💎 Value Momentum":      ("Low P/E ratio + rising RSI + price above 20-day MA — rare value-meets-momentum convergence", "free"),
    "⚡📈 Volume Breakout":   ("Breaking above moving averages on unusually high volume = institutional confirmation", "premium"),
    "🎯 Smart Reversal":      ("RSI oversold + MACD turning positive + rising sentiment = technical bounce forming", "premium"),
    "🌊 Momentum Leaders":    ("RSI sweet spot + above both MAs + bullish MACD simultaneously = all systems green", "premium"),
    "🏆 Relative Strength":   ("Outperforming their sector by 5%+ this week while sector is flat or declining", "premium"),
    "🎪 Earnings Catalyst":   ("Elevated volume + social buzz + sharp move = likely earnings or news event in play", "premium"),
    "🔁 Mean Reversion":      ("Near Bollinger lower band + high short interest + RSI < 35 = spring-loaded setup", "premium"),
    "⚡🧲 Smart Money Signal": ("3× average volume + price holding above VWAP proxy + MACD bullish = institutional accumulation", "premium"),
    "🌪️ Volatility Squeeze":  ("Bollinger Band width at 90-day low + volume building = coiled-spring breakout setup", "premium"),
    "🎯📊 Triple Lock":        ("RSI + MACD + 50d trend + volume all simultaneously bullish — maximum conviction setup", "premium"),
    "🦈 Sustained Strength":  ("Above-average volume 3+ sessions + holding MAs = quiet institutional accumulation signal", "premium"),
}

SECTOR_ETFS = {"Technology":"XLK","Healthcare":"XLV","Financials":"XLF","Energy":"XLE","Cons Disc":"XLY","Industrials":"XLI","Materials":"XLB","Utilities":"XLU","Real Estate":"XLRE","Comm Svcs":"XLC"}
INDEXES     = {"NASDAQ":"^IXIC","S&P 500":"^GSPC","DOW":"^DJI","VIX":"^VIX","Russell":"^RUT"}
BROAD_UNI   = ["AAPL","MSFT","NVDA","AMD","TSLA","META","AMZN","GOOGL","PLTR","MSTR","GME","AMC","RIVN","MRNA","BNTX","SMCI","ARM","SOUN","ASTS","IONQ","JPM","BAC","XOM","LLY","ABBV","AVGO","QCOM","IBM","MULN","SPCE","BBAI","QUBT","RIVN"]

FREE_COMPOSITE  = [k for k,(d,t) in COMPOSITE_CATS.items() if t=="free"]
PREM_COMPOSITE  = [k for k,(d,t) in COMPOSITE_CATS.items() if t=="premium"]

# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────
def init():
    if "initialized" in st.session_state: return
    st.session_state.initialized=True
    st.session_state.update({
        "page":"landing","user":None,"role":"guest",
        "watchlist":[],"alerts":[],"saved_screeners":[],
        "detail_ticker":None,"detail_data":{},"discover_cat":"🔥💥 Squeeze + Buzz",
        "prev_page":None,"hero_panel":0,
        "users_db":_load_seed_accounts(),
        "site_stats":{"total_signups":1847,"premium_users":312,"daily_active":634,"conversion":16.9},
        "email_digest_enabled":False,"digest_frequency":"Daily",
        "ranking_sort":"SW Score","ranking_filter":"All",
    })
init()

# ─────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────
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
    db[email]={"pw":hp(pw),"name":name,"role":"free","verified":False,
               "joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Free"}
    st.session_state.site_stats["total_signups"]+=1
    st.session_state.user={"email":email,"name":name}
    st.session_state.role="free"
    return True,""

def logout():
    for k in ["user","role","watchlist","alerts"]: st.session_state.pop(k,None)
    nav("landing")

def is_owner():   return st.session_state.get("role")=="owner"
def is_admin():   return st.session_state.get("role") in ("owner","admin")
def is_premium(): return st.session_state.get("role") in ("owner","admin","premium")
def is_authed():  return st.session_state.get("user") is not None

def nav(p):
    st.session_state.prev_page=st.session_state.get("page")
    st.session_state.page=p
    st.rerun()

def go_back():
    prev=st.session_state.get("prev_page","discover")
    if not prev or prev==st.session_state.page: prev="discover"
    nav(prev)

# ─────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300,show_spinner=False)
def yf_quote(ticker):
    try:
        tk=yf.Ticker(ticker); h=tk.history(period="2d",interval="1d"); i=tk.info
        if len(h)<1: return None
        p=round(float(h["Close"].iloc[-1]),2)
        pv=round(float(h["Close"].iloc[-2]),2) if len(h)>=2 else p
        return {"price":p,"prev":pv,"open":round(float(h["Open"].iloc[-1]),2),
                "high":round(float(h["High"].iloc[-1]),2),"low":round(float(h["Low"].iloc[-1]),2),
                "volume":int(h["Volume"].iloc[-1]),"pct":round(((p-pv)/pv)*100,2) if pv else 0,
                "chg":round(p-pv,2),"name":i.get("shortName",i.get("longName",ticker))[:30]}
    except: return None

@st.cache_data(ttl=600,show_spinner=False)
def yf_ohlcv(ticker,n=60):
    try:
        h=yf.Ticker(ticker).history(period=f"{min(n+20,130)}d")
        if len(h)<5: return None
        df=h.tail(n).reset_index(); df.columns=[c.lower() for c in df.columns]
        return df.rename(columns={"date":"datetime"})[["datetime","open","high","low","close","volume"]].copy()
    except: return None

@st.cache_data(ttl=3600,show_spinner=False)
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

@st.cache_data(ttl=300,show_spinner=False)
def td_quote(ticker,key):
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
        q=td_quote(ticker,key)
        if q: return q
    return yf_quote(ticker)

@st.cache_data(ttl=900,show_spinner=False)
def st_hot():
    try:
        d=requests.get("https://api.stocktwits.com/api/2/trending/symbols.json",timeout=8).json()
        return [s["symbol"] for s in d.get("symbols",[])]
    except: return ["NVDA","TSLA","AAPL","AMD","MSTR","PLTR","META","MSFT","GME","AMC"]

@st.cache_data(ttl=900,show_spinner=False)
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

@st.cache_data(ttl=300,show_spinner=False)
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

@st.cache_data(ttl=900,show_spinner=False)
def get_sectors():
    out={}
    for s,e in SECTOR_ETFS.items():
        try:
            h=yf.Ticker(e).history(period="5d")
            if len(h)>=2: out[s]=round(((h["Close"].iloc[-1]-h["Close"].iloc[-2])/h["Close"].iloc[-2])*100,2)
        except: out[s]=0.0
    return out

@st.cache_data(ttl=600,show_spinner=False)
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
def compute_scores(df,info=None,sent=None):
    if df is None or len(df)<14: return 0,{},"N/A","Unknown","Low"
    bd={}; total=0
    try:
        dfc=df.copy()
        dfc["rsi"]=ta.momentum.RSIIndicator(dfc["close"],14).rsi()
        dfc["ma20"]=dfc["close"].rolling(20).mean()
        dfc["ma50"]=dfc["close"].rolling(min(50,len(dfc))).mean()
        mac=ta.trend.MACD(dfc["close"]); dfc["macd"]=mac.macd(); dfc["macd_s"]=mac.macd_signal()
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
    elif bd.get("Trend",0)>=18:    op="Uptrend"
    elif bd.get("Volume",0)>=11:   op="Volume Surge"
    elif bd.get("MACD",0)==15:     op="MACD Breakout"
    else:                           op="Watch"
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

def get_recommendation(sc,bd,info=None):
    sf=(info.get("sf",0) or 0)*100 if info else 0
    sq=bd.get("Squeeze",0); mom=bd.get("Momentum",0); tr=bd.get("Trend",0); vol=bd.get("Volume",0); mac=bd.get("MACD",0)
    if sc>=65 and tr>=12 and mom>=12:
        if sq>=6 or sf>=18:
            return ("💥 SQUEEZE BUY",GOLD,f"Short float {sf:.0f}% + social momentum. High risk/reward.")
        elif vol>=11 and mac>=9:
            return ("🟢 STRONG BUY",GREEN,"Volume surge + MACD + uptrend = institutional-backed move.")
        else:
            return ("🟢 BUY",GREEN,"RSI, trend, and MACD aligned. Multi-factor confirmation.")
    elif sc>=50:
        if mom>=18:
            return ("🟡 WATCH — BOUNCE","#fbbf24","Oversold with improving signals. Watch for volume confirmation.")
        return ("🟡 WATCH","#fbbf24","Mixed signals — wait for confirmation before entry.")
    elif sc>=30:
        return ("🟠 HOLD / WAIT","#fb923c","Weak signals. Better setup likely forming — patience.")
    else:
        return ("🔴 AVOID",RED,"Most indicators negative. Capital better deployed elsewhere.")

def get_insights(df,info=None):
    out=[]
    if df is None or len(df)<14: return out
    try:
        dfc=df.copy()
        dfc["rsi"]=ta.momentum.RSIIndicator(dfc["close"],14).rsi()
        dfc["ma20"]=dfc["close"].rolling(20).mean()
        dfc["ma50"]=dfc["close"].rolling(min(50,len(dfc))).mean()
        mac=ta.trend.MACD(dfc["close"]); dfc["macd"]=mac.macd(); dfc["macd_s"]=mac.macd_signal()
        bb=ta.volatility.BollingerBands(dfc["close"]); dfc["bb"]=bb.bollinger_pband()
        lat=dfc.iloc[-1]; prev=dfc.iloc[-2]; rsi=lat["rsi"]; price=lat["close"]
        if pd.notna(rsi):
            if rsi<30:       out.append(("🔻 RSI Oversold","The stock has dropped hard and fast. Historically these extremes precede a bounce as buyers return.","bull","Medium"))
            elif rsi>70:     out.append(("🔺 RSI Overbought","The stock surged quickly. Sharp rises often face profit-taking — be cautious chasing here.","bear","Medium"))
            elif 55<rsi<=70: out.append(("📈 Strong Momentum","Momentum is healthy and building without being dangerously extended.","bull","Medium"))
            else:            out.append(("➡️ Neutral RSI","No extreme RSI pressure — sideways or early directional move.","neu","Low"))
        if pd.notna(lat["ma20"]) and pd.notna(lat["ma50"]):
            if price>lat["ma20"] and price>lat["ma50"]:
                out.append(("✅ Above Key Averages","Trading above its 20-day and 50-day average prices. Buyers have been in control — healthy uptrend.","bull","High"))
            elif price<lat["ma20"] and price<lat["ma50"]:
                out.append(("⚠️ Below Key Averages","Below its recent averages. Sellers have been winning. Trend is currently pointing down.","bear","High"))
            if prev["ma20"]<prev["ma50"] and lat["ma20"]>lat["ma50"]:
                out.append(("✨ Golden Cross","Major bullish event: short-term trend just crossed above long-term. Many traders treat this as a strong buy signal.","bull","High"))
            elif prev["ma20"]>prev["ma50"] and lat["ma20"]<lat["ma50"]:
                out.append(("💀 Death Cross","Short-term trend crossed below long-term — often signals a deepening downtrend.","bear","High"))
        if pd.notna(lat["macd"]) and pd.notna(lat["macd_s"]):
            if lat["macd"]>lat["macd_s"] and prev["macd"]<=prev["macd_s"]:
                out.append(("⚡ MACD Bullish Crossover","Momentum just flipped positive. Buyers entering — often a reliable upside signal.","bull","High"))
            elif lat["macd"]<lat["macd_s"] and prev["macd"]>=prev["macd_s"]:
                out.append(("📉 MACD Bearish Crossover","Momentum turned negative. Selling pressure building.","bear","High"))
            elif lat["macd"]>0: out.append(("📊 MACD Positive","Overall momentum favors buyers.","bull","Medium"))
            else:               out.append(("📊 MACD Negative","Overall momentum favors sellers.","bear","Medium"))
        if "volume" in dfc.columns:
            avg=dfc["volume"].rolling(20).mean().iloc[-1]
            if pd.notna(avg) and avg>0:
                r=lat["volume"]/avg
                if r>=2:
                    d_="bull" if lat["close"]>prev["close"] else "bear"
                    out.append((f"🔊 Volume Spike {r:.1f}×",f"Volume is {r:.1f}× above normal. High-volume moves tend to be more reliable and sustained.",d_,"High"))
                elif r<0.5:
                    out.append(("📭 Low Volume","Very low activity — moves on thin volume can easily reverse.","neu","Low"))
        if info:
            sf=(info.get("sf",0) or 0)*100; dtc=info.get("dtc",0) or 0
            if sf>=20: out.append((f"🎯 High Short Interest {sf:.0f}%",f"{sf:.1f}% of shares are sold short. Rising price forces short covering — squeeze potential.","bull","High"))
            if dtc>=5:  out.append((f"⏱️ {dtc:.0f}d Days-to-Cover",f"~{dtc:.0f} days of volume needed to close all shorts. Significant squeeze fuel.","bull","Medium"))
        if pd.notna(lat["bb"]):
            if lat["bb"]<0:   out.append(("📏 Near Lower Band","At the bottom of its typical range — historically can precede a bounce.","bull","Medium"))
            elif lat["bb"]>1: out.append(("📏 Near Upper Band","Stretched to the top of its normal range — may face resistance.","bear","Medium"))
    except: pass
    return out

def risk_color(r):
    return {"Low":"#22c55e","Low-Medium":"#4ade80","Medium":"#fbbf24","Medium-High":"#fb923c","High":"#ef4444","Very High":"#dc2626"}.get(r,"#64748b")

def sc_pill(sc):
    cls="sp-hi" if sc>=65 else "sp-md" if sc>=40 else "sp-lo"
    return f'<span class="sp {cls}">{sc}</span>'

# ─────────────────────────────────────────────────────────────
# COMPOSITE SCORING ENGINE
# ─────────────────────────────────────────────────────────────
def get_composite_stocks(cat_name,limit=10):
    hot=st_hot(); universe=list(set(BROAD_UNI+hot[:8]))[:32]
    results=[]; prog=st.progress(0,f"Computing {cat_name}…")
    for i,t in enumerate(universe[:limit*3]):
        prog.progress((i+1)/(limit*3),f"Analyzing {t}…")
        try:
            q=get_quote(t); df=yf_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            sc,bd,op,risk,conf=compute_scores(df,info,sent); ig=get_insights(df,info)
            if not q: continue
            sf=(info.get("sf",0) or 0)*100; bull=sent.get("bull",50); in_hot=t in hot
            include=False; comp=sc; why="StockWins composite signal"
            if cat_name=="🔥💥 Squeeze + Buzz":
                comp=sf*1.5+(30 if in_hot else 0)+(bull-50)*0.4+bd.get("Volume",0)
                include=sf>=8 and (in_hot or bull>=60)
                why=f"Short float {sf:.0f}% + {'🔥 trending' if in_hot else f'{bull}% bullish'}"
            elif cat_name=="⚡📈 Volume Breakout":
                vs=bd.get("Volume",0); ts=bd.get("Trend",0)
                comp=vs*2+ts+bd.get("MACD",0); include=vs>=7 and ts>=12
                why="Volume surge + breaking above key averages"
            elif cat_name=="🎯 Smart Reversal":
                ms=bd.get("Momentum",0); ms2=bd.get("MACD",0)
                comp=ms+ms2+(bull-50)*0.3; include=ms>=20 and ms2>=9
                why="RSI oversold + MACD turning positive = bounce setup"
            elif cat_name=="💡 Hidden Movers":
                wl=sent.get("wl",0)
                comp=sc-(30 if in_hot else 0)-min(wl/100,15)
                include=sc>=45 and not in_hot and bull<65
                why=f"Score {sc} with low social attention — early discovery"
            elif cat_name=="🌊 Momentum Leaders":
                comp=bd.get("Momentum",0)+bd.get("Trend",0)+bd.get("MACD",0)+bull*0.08
                include=(bd.get("Momentum",0)>=12 and bd.get("Trend",0)>=16 and bd.get("MACD",0)>=9)
                why="RSI + trend + MACD all bullish simultaneously"
            elif cat_name=="🎭 Social Catalyst":
                vs=bd.get("Volume",0); msgs=sent.get("msgs",0)
                comp=vs*1.5+(50 if in_hot else 0)+bull*0.3+min(msgs*2,30)
                include=(in_hot or msgs>=5) and vs>=4
                why=f"{'🔥 StockTwits trending' if in_hot else f'{msgs} posts'} + volume surge"
            elif cat_name=="🌡️ Sentiment Flip":
                comp=bull*0.8+bd.get("Momentum",0)*0.5+bd.get("Volume",0)*0.3
                include=bull>=62 and bd.get("Momentum",0)>=10
                why=f"Bullish sentiment at {bull}% — sentiment sharply reversing"
            elif cat_name=="📉→📈 Fallen Angels":
                mom=bd.get("Momentum",0)
                comp=mom*2+bd.get("Sentiment",0)+bd.get("Volume",0)
                include=mom>=20
                why="Deep pullback + RSI oversold = recovery candidate forming"
            elif cat_name=="🔬 Micro-Cap Movers":
                mc=info.get("mktcap",0) or 0; vs=bd.get("Volume",0)
                comp=vs*2+bd.get("Momentum",0)+(20 if mc<500e6 else 10 if mc<2e9 else 0)
                include=mc<2e9 and vs>=4 and bd.get("Momentum",0)>=8
                mc_s=f"${mc/1e9:.1f}B" if mc>=1e9 else f"${mc/1e6:.0f}M"
                why=f"Micro/small-cap ({mc_s}) + volume surge = early move potential"
            elif cat_name=="💎 Value Momentum":
                pe=info.get("pe",None); tr_s=bd.get("Trend",0)
                comp=(15 if pe and 5<pe<20 else 5)+tr_s+bd.get("Momentum",0)
                include=tr_s>=10 and bd.get("Momentum",0)>=10 and (pe is None or pe<25)
                why=f"Low P/E ({pe:.1f}×)" if pe else "Value setup + rising momentum"
            elif cat_name=="🏆 Relative Strength":
                comp=bd.get("Trend",0)*1.5+bd.get("Momentum",0)+bd.get("MACD",0)
                include=bd.get("Trend",0)>=16 and bd.get("Momentum",0)>=12 and sc>=55
                why=f"Score {sc} — outperforming on trend, momentum, and MACD"
            elif cat_name=="🎪 Earnings Catalyst":
                vs=bd.get("Volume",0); msgs=sent.get("msgs",0)
                comp=vs*2+(50 if in_hot else 0)+bull*0.3+min(msgs*3,40)
                include=vs>=11 and (in_hot or bull>=65)
                why=f"High volume + social spike = likely catalyst in play"
            elif cat_name=="🔁 Mean Reversion":
                sq=bd.get("Squeeze",0); mom=bd.get("Momentum",0)
                comp=mom+sq*2+bd.get("Sentiment",0)
                include=mom>=18 and (sq>=2 or sf>=10)
                why=f"Oversold + {sf:.0f}% short float = compression before expansion"
            elif cat_name=="⚡🧲 Smart Money Signal":
                vs=bd.get("Volume",0); mac=bd.get("MACD",0); tr_s=bd.get("Trend",0)
                comp=vs*2+mac*1.5+tr_s; include=vs>=11 and mac>=9 and tr_s>=12
                why="3×+ volume + MACD bullish + above MAs = institutional accumulation"
            elif cat_name=="🌪️ Volatility Squeeze":
                mom=bd.get("Momentum",0); vs=bd.get("Volume",0); sq=bd.get("Squeeze",0)
                try:
                    bb=ta.volatility.BollingerBands(df["close"].copy())
                    bb_low=bb.bollinger_wband().iloc[-1]<bb.bollinger_wband().rolling(90).mean().iloc[-1]*0.7
                except: bb_low=False
                comp=(30 if bb_low else 0)+vs+mom+sq*2; include=vs>=4 and (bb_low or sq>=2)
                why="Bollinger compressing + volume building = coiled spring"
            elif cat_name=="🎯📊 Triple Lock":
                mom=bd.get("Momentum",0); mac=bd.get("MACD",0); tr_s=bd.get("Trend",0); vs=bd.get("Volume",0)
                comp=mom+mac+tr_s+vs; include=(mom>=12 and mac>=9 and tr_s>=16 and vs>=4)
                why="RSI + MACD + 50d trend + volume ALL bullish = maximum conviction"
            elif cat_name=="🦈 Sustained Strength":
                vs=bd.get("Volume",0); tr_s=bd.get("Trend",0); mac=bd.get("MACD",0)
                comp=vs*1.5+tr_s+mac+bd.get("Sentiment",0)*0.5
                include=tr_s>=16 and vs>=7 and mac>=9
                why="Multi-session above-avg volume + holding MAs = institutional interest"
            else:
                include=True; comp=sc; why="StockWins scoring engine"
            if include:
                results.append({"t":t,"q":q,"sc":sc,"bd":bd,"ig":ig,"op":op,"risk":risk,"conf":conf,
                                 "hot":in_hot,"df":df,"info":info,"sent":sent,"comp":comp,"why":why})
        except: continue
    prog.empty()
    results.sort(key=lambda x:x["comp"],reverse=True)
    return results[:limit]

# ─────────────────────────────────────────────────────────────
# SHARED UI COMPONENTS
# ─────────────────────────────────────────────────────────────
def gold_btn(label, key, help_text=None):
    """Render a gold premium upgrade button."""
    st.markdown('<div class="gold-btn">', unsafe_allow_html=True)
    clicked = st.button(f"👑 {label}", key=key, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    return clicked

def render_sr(s, cat_key="", show_why=False):
    t=s["t"]; q=s["q"]; sc=s["sc"]; ig=s["ig"]
    info=s.get("info",{}); sent=s.get("sent",{}); hot=s.get("hot",False)
    bd=s.get("bd",{}); op=s.get("op",""); risk=s.get("risk",""); why_str=s.get("why","")
    if not q: return
    pct=q.get("pct",0); price=q.get("price",0)
    cc=GREEN if pct>=0 else RED; ar="▲" if pct>=0 else "▼"
    rc=risk_color(risk)
    hot_b='<span class="b b-hot">🔥 HOT</span>' if hot else ""
    sigs="".join([f'<span class="b b-{"bull" if sv=="bull" else "bear" if sv=="bear" else "neu"}">{lv[:16]}</span>' for lv,_,sv,_ in ig[:2]])
    rec_lbl,rec_clr,rec_txt=get_recommendation(sc,bd,info)
    display_why=why_str if (show_why and why_str) else rec_txt

    col_main,col_btn=st.columns([5,2],gap="small")
    with col_main:
        st.markdown(f"""<div class="sr">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div style="flex:1;min-width:0;">
                    <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px;">
                        <span class="sr-tick">{t}</span>{hot_b}
                        <span style="display:inline-block;padding:3px 10px;border-radius:5px;
                            font-size:11px;font-weight:800;background:{rec_clr}22;
                            color:{rec_clr};border:1px solid {rec_clr}44;">{rec_lbl}</span>
                    </div>
                    <div class="sr-name">{q.get('name','')[:32]}</div>
                    <div class="sr-why">→ {display_why[:80]}{"…" if len(display_why)>80 else ""}</div>
                    <div style="margin-top:5px;">{sigs}</div>
                </div>
                <div style="text-align:right;min-width:110px;flex-shrink:0;padding-left:12px;">
                    <div class="sr-price">${price:,.2f}</div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:{cc};">{ar}{abs(pct):.2f}%</div>
                    <div style="display:flex;align-items:center;gap:5px;justify-content:flex-end;margin-top:4px;">
                        <span style="font-size:10px;color:{rc};">⚡{risk}</span>
                        {sc_pill(sc)}
                    </div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)
    with col_btn:
        if st.button("📊 View Report", key=f"dr_{t}_{cat_key}",use_container_width=True,type="primary"):
            st.session_state.detail_ticker=t; st.session_state.detail_data=s; nav("stock_detail")
        wl=st.session_state.get("watchlist",[])
        in_wl=t in wl
        if st.button("✅ Watching" if in_wl else "➕ Watchlist",key=f"wl_{t}_{cat_key}",use_container_width=True):
            if in_wl: wl.remove(t)
            else:     wl.append(t)
            st.rerun()

def render_cat(cat,limit=10,show_why=False):
    is_comp=cat in COMPOSITE_CATS
    if is_comp:
        _,tier=COMPOSITE_CATS[cat]
        if tier=="premium" and not is_premium(): render_lock(cat); return
        stocks=get_composite_stocks(cat,limit)
    else:
        tickers=list(CATEGORIES.get(cat,[])); hot=st_hot()
        if cat=="🔥 Trending Now": tickers=hot
        if not tickers: st.info("No tickers available."); return
        scan=min(len(tickers),limit); stocks=[]; prog=st.progress(0,f"Loading {cat}…")
        for i,t in enumerate(tickers[:scan]):
            prog.progress((i+1)/scan,f"Analyzing {t}…")
            q=get_quote(t); df=yf_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            sc,bd,op,risk,conf=compute_scores(df,info,sent); ig=get_insights(df,info)
            if q: stocks.append({"t":t,"q":q,"sc":sc,"bd":bd,"ig":ig,"op":op,"risk":risk,"conf":conf,"hot":t in hot,"df":df,"info":info,"sent":sent,"comp":sc,"why":""})
        prog.empty()
        stocks.sort(key=lambda x:x["sc"],reverse=True)
    if not stocks: st.info(f"No stocks matching criteria right now."); return
    for s in stocks: render_sr(s,cat.replace(" ","_").replace("+","p").replace("→","r"),show_why=is_comp)

def render_lock(name=""):
    st.markdown(f"""<div class="lock">
        <div style="font-size:28px;margin-bottom:10px;">🔒</div>
        <div style="font-size:17px;font-weight:800;color:#e2e8f0;margin-bottom:6px;">{name} — Premium</div>
        <div style="font-size:13px;color:#374f6e;margin-bottom:18px;">Upgrade to unlock all premium composite categories, squeeze scanner, advanced screener, and full BI analytics.</div>
    </div>""", unsafe_allow_html=True)
    st.markdown('<div style="max-width:280px;margin:14px auto 0;">', unsafe_allow_html=True)
    if gold_btn("Unlock Premium", f"lock_{name[:20].replace(' ','_')}"): nav("pricing")
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# NAV CSS + TOPBAR
# ─────────────────────────────────────────────────────────────
NAV_CSS = """<style>
.sw-logo-click-target{display:flex;align-items:center;height:38px;cursor:pointer;padding:0;line-height:1;}
.element-container:has(.sw-logo-click-target)+.element-container{height:0px !important;overflow:visible !important;margin:0 !important;padding:0 !important;}
.element-container:has(.sw-logo-click-target)+.element-container .stButton>button{position:relative !important;top:-44px !important;left:0 !important;width:180px !important;height:44px !important;min-height:44px !important;opacity:0 !important;cursor:pointer !important;z-index:999 !important;background:transparent !important;border:none !important;box-shadow:none !important;}
.sw-divider{border:none;border-top:1px solid rgba(255,255,255,0.06);margin:0 0 24px 0;}
[data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:first-of-type{align-items:center !important;min-height:56px !important;}
[data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:first-of-type>[data-testid="column"]{display:flex !important;align-items:center !important;padding-top:0 !important;padding-bottom:0 !important;}
[data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:first-of-type>[data-testid="column"]>div{width:100% !important;}
.sw-nav .stButton>button{font-size:13px !important;font-weight:500 !important;padding:6px 12px !important;min-height:38px !important;height:38px !important;border:1px solid rgba(255,255,255,0.15) !important;background:rgba(255,255,255,0.04) !important;color:#a8bdd4 !important;border-radius:7px !important;white-space:nowrap !important;width:100% !important;}
.sw-nav .stButton>button:hover{border-color:rgba(37,99,235,0.5) !important;background:rgba(37,99,235,0.1) !important;color:#93b4fd !important;}
.sw-nav .stButton>button[kind="primary"]{background:#2563eb !important;border-color:#2563eb !important;color:#fff !important;font-weight:700 !important;}
</style>"""

LOGO_HTML = """<div class="sw-logo-click-target">
<span style="font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:700;letter-spacing:-0.5px;">
<span style="color:#e2e8f0;">Stock</span><span style="color:#f59e0b;">W</span><span style="color:#e2e8f0;">ins</span>
</span></div>"""

def render_logo_click(key,dest):
    st.markdown(LOGO_HTML, unsafe_allow_html=True)
    if st.button(" ",key=key): nav(dest)

def render_topbar(active=""):
    st.markdown(NAV_CSS, unsafe_allow_html=True)
    if is_authed():
        pages=[("Dashboard","dashboard"),("Discover","discover"),("Watchlist","watchlist"),
               ("Screener","screener"),("BI Analytics","bi_dashboard"),("Pricing","pricing")]
        if is_admin(): pages.append(("🛠 Admin","admin"))
        c1,c2,c3=st.columns([2,8,3])
        with c1: render_logo_click("top_logo","dashboard")
        with c2:
            st.markdown('<div class="sw-nav">', unsafe_allow_html=True)
            nc=st.columns(len(pages))
            for col,(lbl,pg) in zip(nc,pages):
                with col:
                    if st.button(lbl,key=f"top_{pg}",type="primary" if active==pg else "secondary"):
                        nav(pg)
            st.markdown('</div>', unsafe_allow_html=True)
        with c3:
            ri={"owner":"👑","admin":"🛡️","premium":"⭐","free":"👤"}.get(st.session_state.role,"👤")
            uc1,uc2,uc3=st.columns([4,1,1])
            with uc1: st.markdown(f'<div style="font-size:12px;color:#6b7fa0;white-space:nowrap;">{ri} {st.session_state.user["name"]}</div>',unsafe_allow_html=True)
            with uc2:
                if st.button("⚙️",key="top_set"): nav("settings")
            with uc3:
                if st.button("↩️",key="top_out"): logout()
    else:
        c1,_,c3=st.columns([2,5,4])
        with c1: render_logo_click("top_logo","landing")
        with c3:
            st.markdown('<div class="sw-nav">', unsafe_allow_html=True)
            a1,a2,a3,a4=st.columns(4,gap="small")
            with a1:
                if st.button("Features",key="top_features",use_container_width=True): nav("features")
            with a2:
                if st.button("Pricing",key="top_pricing",use_container_width=True): nav("pricing")
            with a3:
                if st.button("Login",key="top_login",use_container_width=True): nav("login")
            with a4:
                if st.button("Sign Up →",key="top_signup",type="primary",use_container_width=True): nav("signup")
            st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="sw-divider">', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown(f'<div style="padding:20px 18px 10px;">{LOGO_HTML}<div style="font-size:10px;color:rgba(255,255,255,.2);margin-top:4px;">Market Intelligence Platform</div></div>',unsafe_allow_html=True)
        st.divider()
        if is_authed():
            st.markdown('<div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1.5px;text-transform:uppercase;padding:12px 18px 5px;">Discover</div>',unsafe_allow_html=True)
            for cat_key,(desc,tier) in COMPOSITE_CATS.items():
                is_locked=tier=="premium" and not is_premium()
                safe=cat_key.replace(" ","_").replace("+","p").replace("→","r").replace("🌡️","T").replace("📉","D")[:28]
                label=cat_key+(" ⭐" if is_locked else "")
                if st.button(label,key=f"sb_c_{safe}",use_container_width=True):
                    if is_locked: nav("pricing")
                    else: st.session_state.discover_cat=cat_key; nav("discover")
            st.markdown('<div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1.5px;text-transform:uppercase;padding:12px 18px 5px;">Categories</div>',unsafe_allow_html=True)
            for cat in CATEGORIES:
                if st.button(cat,key=f"sb_s_{cat[:20].replace(' ','_')}",use_container_width=True):
                    st.session_state.discover_cat=cat; nav("discover")
            st.markdown('<div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1.5px;text-transform:uppercase;padding:12px 18px 5px;">Tools</div>',unsafe_allow_html=True)
            for icon,label,pg in [("📊","Dashboard","dashboard"),("⭐","Watchlist","watchlist"),("🔍","Screener","screener"),("📈","BI Analytics","bi_dashboard"),("💰","Pricing","pricing")]:
                if st.button(f"{icon} {label}",key=f"sb_{pg}",use_container_width=True): nav(pg)
            if is_admin():
                st.markdown('<div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1.5px;text-transform:uppercase;padding:12px 18px 5px;">Admin</div>',unsafe_allow_html=True)
                if st.button("🛠️ Admin Panel",key="sb_admin",use_container_width=True): nav("admin")
            st.divider()
            if not is_premium():
                st.markdown('<div style="padding:4px 10px 10px;">', unsafe_allow_html=True)
                if gold_btn("Go Premium","sb_gold"): nav("pricing")
                st.markdown('</div>', unsafe_allow_html=True)
            ri={"owner":"👑","admin":"🛡️","premium":"⭐","free":"👤"}.get(st.session_state.role,"👤")
            st.markdown(f'<div style="padding:4px 18px;font-size:12px;color:#374f6e;">{ri} {st.session_state.user["name"]}</div>',unsafe_allow_html=True)
            if st.button("Log Out",key="sb_logout",use_container_width=True): logout()
        else:
            st.markdown('<div style="padding:12px 18px;font-size:12px;color:#374f6e;margin-bottom:8px;">Sign in to access the full dashboard.</div>',unsafe_allow_html=True)
            if st.button("Login →",key="sb_login",use_container_width=True): nav("login")
            if gold_btn("Sign Up Free","sb_signup_gold"): nav("signup")
            st.markdown("""<div style="margin:12px 10px;background:#080c18;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:12px 14px;">
                <div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1px;text-transform:uppercase;margin-bottom:7px;">Free Includes</div>
                <div style="font-size:12px;color:#2a3a52;line-height:2.2;">✅ Live market data<br>✅ 7 composite categories<br>✅ Social sentiment<br>✅ Plain-English insights<br>✅ Watchlist</div>
            </div>""",unsafe_allow_html=True)
        st.markdown('<div style="padding:8px 18px;font-size:10px;color:rgba(255,255,255,.1);">© 2026 StockWins</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────
def render_footer():
    st.markdown(f"""
    <div class="sw-footer-wrap">
        <div style="max-width:1400px;margin:0 auto;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:24px;margin-bottom:24px;">
                <div>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;letter-spacing:-.5px;">
                        <span style="color:#e2e8f0;">Stock</span><span style="color:{GOLD};">W</span><span style="color:#e2e8f0;">ins</span>
                    </span>
                    <div style="font-size:12px;color:rgba(255,255,255,.2);margin-top:6px;">Market Intelligence Platform</div>
                </div>
                <div style="display:flex;gap:32px;font-size:12px;color:rgba(255,255,255,.2);">
                    <span style="cursor:pointer;">Privacy Policy</span>
                    <span style="cursor:pointer;">Terms of Service</span>
                    <span style="cursor:pointer;">Risk Disclaimer</span>
                    <span style="cursor:pointer;">Contact</span>
                </div>
            </div>
            <div class="disc">⚠️ <strong style="color:#4a5e7a;">Risk Disclaimer:</strong> Trading stocks involves substantial risk of financial loss. StockWins provides algorithmic, educational content only — not financial, investment, legal, or tax advice. All signals may be inaccurate or delayed. Past performance does not guarantee future results. Always consult a licensed financial professional before making investment decisions.</div>
            <div style="font-size:10px;color:rgba(255,255,255,.1);margin-top:10px;text-align:right;">© 2026 StockWins. All rights reserved.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# DEMO PANELS (for landing hero)
# ─────────────────────────────────────────────────────────────
DEMO = [
    """<div style="background:#0d1525;border:1px solid rgba(255,255,255,.08);border-radius:11px;overflow:hidden;">
    <div style="background:#080b14;border-bottom:1px solid rgba(255,255,255,.06);padding:10px 14px;display:flex;align-items:center;justify-content:space-between;">
        <div style="display:flex;align-items:center;gap:6px;"><div style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></div><div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;display:inline-block;"></div><div style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></div>
        <span style="font-size:11px;color:#374f6e;margin-left:6px;font-family:'JetBrains Mono',monospace;">StockTwits Hot Stocks</span></div>
        <span style="font-size:9px;color:#22c55e;font-weight:700;">● LIVE</span>
    </div>
    <div style="padding:14px;">
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">TSLA</span>
            <div style="margin-top:5px;"><span style="background:#05260f;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(74,222,128,.3);">🟢 STRONG BUY</span><span style="background:#260d00;color:#fb923c;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;margin-left:4px;">🔥 HOT</span></div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">$199.49</div><div style="font-size:11px;font-weight:700;color:#22c55e;">▲ 3.47%</div></div>
        </div>
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">NVDA</span>
            <div style="margin-top:5px;"><span style="background:#05260f;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;">🟢 BUY</span><span style="background:#05260f;color:#86efac;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;margin-left:3px;">Golden Cross ✨</span></div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">$127.40</div><div style="font-size:11px;font-weight:700;color:#22c55e;">▲ 2.91%</div><div style="font-size:10px;font-weight:700;color:#4ade80;background:#05260f;padding:1px 8px;border-radius:3px;margin-top:3px;">Score 88</div></div>
        </div>
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">AMD</span>
            <div style="margin-top:5px;"><span style="background:#201000;color:#fbbf24;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;">🟡 WATCH</span></div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">$148.20</div><div style="font-size:11px;font-weight:700;color:#ef4444;">▼ 0.82%</div></div>
        </div>
    </div></div>""",

    """<div style="background:#0d1525;border:1px solid rgba(255,255,255,.08);border-radius:11px;overflow:hidden;">
    <div style="background:#080b14;border-bottom:1px solid rgba(255,255,255,.06);padding:10px 14px;display:flex;align-items:center;justify-content:space-between;">
        <div style="display:flex;align-items:center;gap:6px;"><div style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></div><div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;display:inline-block;"></div><div style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></div>
        <span style="font-size:11px;color:#374f6e;margin-left:6px;font-family:'JetBrains Mono',monospace;">Short Squeeze Candidates</span></div>
        <span style="background:rgba(245,158,11,.12);color:#f59e0b;font-size:9px;font-weight:700;padding:2px 8px;border-radius:20px;border:1px solid rgba(245,158,11,.3);">PREMIUM ⭐</span>
    </div>
    <div style="padding:14px;">
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">AMC</span>
            <div style="margin-top:5px;"><span style="background:rgba(245,158,11,.15);color:#f59e0b;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(245,158,11,.3);">💥 SQUEEZE BUY</span></div></div>
            <div style="text-align:right;"><div style="font-size:9px;color:#2a3a52;">Short Float</div><div style="font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;color:#ef4444;">29.99%</div></div>
        </div>
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">CVNA</span>
            <div style="margin-top:5px;"><span style="background:#05260f;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;">🟢 STRONG BUY</span></div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#22c55e;">+5.42%</div><div style="font-size:12px;color:#3a5068;">Score: 76</div></div>
        </div>
        <div style="background:#080b14;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px 12px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">MSTR</span>
            <div style="margin-top:5px;"><span style="background:rgba(245,158,11,.15);color:#f59e0b;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(245,158,11,.3);">💥 SQUEEZE BUY</span></div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">$411</div><div style="font-size:11px;font-weight:700;color:#22c55e;">+185%</div></div>
        </div>
    </div></div>""",

    """<div style="background:#0d1525;border:1px solid rgba(255,255,255,.08);border-radius:11px;overflow:hidden;">
    <div style="background:#080b14;border-bottom:1px solid rgba(255,255,255,.06);padding:10px 14px;display:flex;align-items:center;gap:6px;">
        <div style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></div><div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;display:inline-block;"></div><div style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></div>
        <span style="font-size:11px;color:#374f6e;margin-left:6px;font-family:'JetBrains Mono',monospace;">Smart Insights — Plain Language</span>
    </div>
    <div style="padding:14px;">
        <div style="background:#0a1020;border-left:3px solid #22c55e;border-radius:0 7px 7px 0;padding:11px 13px;margin-bottom:7px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:5px;"><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">TSLA</span><span style="background:#05260f;color:#4ade80;font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;border:1px solid rgba(74,222,128,.3);">🟢 BUY</span></div>
            <div style="font-size:12px;color:#374f6e;line-height:1.6;"><span style="color:#2dd4bf;font-weight:600;">The Moving Average</span> is breaking out above an important price range, which can sometimes lead to further upside.</div>
        </div>
        <div style="background:#0a1020;border-left:3px solid #fbbf24;border-radius:0 7px 7px 0;padding:11px 13px;margin-bottom:7px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:5px;"><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">PLUG</span><span style="background:rgba(251,191,36,.15);color:#fbbf24;font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;">🟡 WATCH</span></div>
            <div style="font-size:12px;color:#374f6e;line-height:1.6;">There are a lot of <span style="color:#e2e8f0;font-weight:600;">traders</span> betting against this stock, and <span style="color:#e2e8f0;font-weight:600;">momentum is building</span>.</div>
        </div>
        <div style="background:#0a1020;border-left:3px solid #ef4444;border-radius:0 7px 7px 0;padding:11px 13px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:5px;"><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">AAPL</span><span style="background:rgba(239,68,68,.15);color:#f87171;font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;">🔴 AVOID</span></div>
            <div style="font-size:12px;color:#374f6e;line-height:1.6;">The stock <span style="color:#e2e8f0;font-weight:600;">may have risen too quickly</span> and could be due for <em style="color:#e2e8f0;font-weight:600;">a pullback</em>.</div>
        </div>
    </div></div>""",
]

# ─────────────────────────────────────────────────────────────
# PAGE: LANDING
# ─────────────────────────────────────────────────────────────
def page_landing():
    st.markdown(NAV_CSS, unsafe_allow_html=True)
    # Topbar
    c1,_,c3=st.columns([2,5,4])
    with c1: render_logo_click("top_logo_land","landing")
    with c3:
        st.markdown('<div class="sw-nav">', unsafe_allow_html=True)
        a1,a2,a3,a4=st.columns(4,gap="small")
        with a1:
            if st.button("Features",key="land_feat",use_container_width=True): nav("features")
        with a2:
            if st.button("Pricing",key="land_price",use_container_width=True): nav("pricing")
        with a3:
            if st.button("Login",key="land_login",use_container_width=True): nav("login")
        with a4:
            if st.button("Sign Up →",key="land_su",type="primary",use_container_width=True): nav("signup")
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="sw-divider">', unsafe_allow_html=True)

    # ── HERO ──
    p_idx=st.session_state.get("hero_panel",0)
    hl,hr=st.columns([5,5],gap="large")
    with hl:
        st.markdown(f"""
        <div style="padding:48px 0 32px 48px;">
            <div style="font-size:11px;font-weight:700;color:{BLUE};letter-spacing:2.5px;text-transform:uppercase;margin-bottom:16px;">Smart Stock Discovery Platform</div>
            <div class="hero-h1">Spot Market<br>Opportunities<br><span class="hi">Before They</span><br><span class="hg">Get Crowded</span></div>
            <div class="hero-sub">Discover trending stocks, squeeze candidates, and momentum shifts using our proprietary 17-signal composite scoring. No API key. No jargon. Just clear signals.</div>
        </div>
        """, unsafe_allow_html=True)

        bc1,bc2,bc3=st.columns(3)
        with bc1:
            if st.button("Start Free →",key="h_su",type="primary",use_container_width=True): nav("signup")
        with bc2:
            if st.button("Try Dashboard",key="h_dash",use_container_width=True): nav("login")
        with bc3:
            if gold_btn("Go Premium","h_prem"): nav("pricing")

    with hr:
        # Self-contained auto-advancing slideshow — title above, demo below
        # Uses string concat to avoid f-string brace conflicts with DEMO HTML
        hero_comp = (
            '<style>'
            'body{margin:0;padding:0;background:transparent;font-family:Inter,sans-serif;overflow:hidden;}'
            '.tab-row{display:flex;gap:28px;margin-bottom:10px;padding:16px 0 0 0;}'
            '.tab-item{font-size:13px;font-weight:500;color:#374f6e;cursor:pointer;'
            '  padding-bottom:5px;border-bottom:2px solid transparent;transition:all 0.2s;'
            '  user-select:none;white-space:nowrap;}'
            '.tab-item.active{color:#e2e8f0;font-weight:700;border-bottom-color:#2563eb;}'
            '.tab-item:hover{color:#a8bdd4;}'
            '.slide-title{font-size:24px;font-weight:900;color:#f1f5f9;letter-spacing:-0.8px;'
            '  line-height:1.15;margin-bottom:14px;min-height:58px;}'
            '.hi{color:#2563eb;} .hg{color:#f59e0b;}'
            '.dots{display:flex;gap:7px;margin-bottom:10px;align-items:center;}'
            '.dot{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,0.15);'
            '  cursor:pointer;transition:all 0.3s;}'
            '.dot.active{background:#2563eb;width:20px;border-radius:4px;}'
            '</style>'
            '<div>'
            '<div class="tab-row">'
            '<div class="tab-item active" id="t0" onclick="sw(0)">📊 Market Overview</div>'
            '<div class="tab-item" id="t1" onclick="sw(1)">💥 Squeeze Candidates</div>'
            '<div class="tab-item" id="t2" onclick="sw(2)">💡 Smart Insights</div>'
            '</div>'
            '<div class="dots">'
            '<div class="dot active" id="d0" onclick="sw(0)"></div>'
            '<div class="dot" id="d1" onclick="sw(1)"></div>'
            '<div class="dot" id="d2" onclick="sw(2)"></div>'
            '</div>'
            '<div id="h0" class="slide-title">Find Trending Stocks<br><span class="hi">Before the Crowd</span></div>'
            '<div id="h1" class="slide-title" style="display:none">Scan For Short Squeeze<br><span class="hi">Candidates</span></div>'
            '<div id="h2" class="slide-title" style="display:none">Smart Insights<br>in <span class="hi">Simple Language</span></div>'
            '<div id="p0">' + DEMO[0] + '</div>'
            '<div id="p1" style="display:none">' + DEMO[1] + '</div>'
            '<div id="p2" style="display:none">' + DEMO[2] + '</div>'
            '</div>'
            '<script>'
            'var c=0;'
            'function sw(n){'
            '  for(var i=0;i<3;i++){'
            '    document.getElementById("t"+i).className="tab-item"+(i===n?" active":"");'
            '    document.getElementById("d"+i).className="dot"+(i===n?" active":"");'
            '    document.getElementById("h"+i).style.display=i===n?"block":"none";'
            '    document.getElementById("p"+i).style.display=i===n?"block":"none";'
            '  }'
            '  c=n;'
            '}'
            'setInterval(function(){sw((c+1)%3);},5000);'
            '</script>'
        )
        import streamlit.components.v1 as components
        components.html(hero_comp, height=500)

    # ── Trust bar ──
    st.markdown(f"""
    <div style="background:#080b14;border-top:1px solid {BORDER};border-bottom:1px solid {BORDER};padding:20px 48px;display:flex;gap:48px;align-items:center;flex-wrap:wrap;">
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:18px;">📊</span><div><div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;">5,000+</div><div style="font-size:11px;color:#2a3a52;">US Stocks Covered</div></div></div>
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:18px;">🎯</span><div><div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;">17</div><div style="font-size:11px;color:#2a3a52;">Composite Categories</div></div></div>
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:18px;">⚡</span><div><div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;">Real-Time</div><div style="font-size:11px;color:#2a3a52;">Sentiment Data</div></div></div>
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:18px;">💰</span><div><div style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;">$0</div><div style="font-size:11px;color:#2a3a52;">To Get Started</div></div></div>
        <div style="margin-left:auto;display:flex;align-items:center;gap:8px;">
            <span style="font-size:12px;color:#2a3a52;">Trusted by</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:{GOLD};">1,847+</span>
            <span style="font-size:12px;color:#2a3a52;">traders</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)

    # ── 4 Feature panels — equal height grid ──
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:0 48px;align-items:stretch;margin-bottom:28px;">
      <div style="display:flex;flex-direction:column;">
        <div style="min-height:105px;margin-bottom:16px;">
          <div style="font-size:26px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;line-height:1.15;margin-bottom:8px;">Find Trending Stocks<br><span style="color:{BLUE};">Before the Crowd</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Discover top stocks making waves across social media and the market.</div>
        </div>
        <div style="flex:1;">{DEMO[0]}</div>
      </div>
      <div style="display:flex;flex-direction:column;">
        <div style="min-height:105px;margin-bottom:16px;">
          <div style="font-size:26px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;line-height:1.15;margin-bottom:8px;">Scan For Short Squeeze<br><span style="color:{BLUE};">Candidates</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Spot stocks with heavy short interest and growing momentum before the move.</div>
        </div>
        <div style="flex:1;">{DEMO[1]}</div>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:0 48px;align-items:stretch;">
      <div style="display:flex;flex-direction:column;">
        <div style="min-height:105px;margin-bottom:16px;">
          <div style="font-size:26px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;line-height:1.15;margin-bottom:8px;">Smart Insights<br>in Simple <span style="color:{BLUE};">Language</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Every technical signal explained in plain English. No finance degree needed.</div>
        </div>
        <div style="flex:1;">{DEMO[2]}</div>
      </div>
      <div style="display:flex;flex-direction:column;">
        <div style="min-height:105px;margin-bottom:16px;">
          <div style="font-size:26px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;line-height:1.15;margin-bottom:8px;">Go Premium For<br><span style="color:{GOLD};">Real-Time Signals &amp;<br>Deeper Analysis</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Upgrade to unlock advanced screening, unlimited alerts, and premium watchlists.</div>
        </div>
        <div style="flex:1;background:#0d1525;border:1px solid rgba(245,158,11,.25);border-radius:11px;overflow:hidden;display:flex;flex-direction:column;">
          <div style="background:linear-gradient(135deg,#1a0d00,#0d1525);border-bottom:1px solid rgba(245,158,11,.2);padding:12px 16px;display:flex;align-items:center;gap:8px;">
            <span style="font-size:14px;">👑</span>
            <span style="font-size:12px;font-weight:700;color:{GOLD};letter-spacing:1px;">PREMIUM FEATURES</span>
          </div>
          <div style="padding:20px 16px;font-size:13px;color:#374f6e;line-height:2.6;flex:1;">
            ✅ &nbsp;All 17 composite signal categories<br>
            ✅ &nbsp;Advanced stock screener<br>
            ✅ &nbsp;Full BI analytics &amp; charts<br>
            ✅ &nbsp;BUY/SELL recommendations<br>
            ✅ &nbsp;Score breakdowns<br>
            ✅ &nbsp;Unlimited watchlist &amp; alerts<br>
            ✅ &nbsp;Priority support<br>
            ✅ &nbsp;Early feature access
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Go Premium CTA
    st.markdown("""
    <style>
    button[aria-label="👑 Unlock Premium Access — Start Today"] {
        background: linear-gradient(135deg,#92400e,#d97706,#f59e0b,#fcd34d) !important;
        border: 1px solid #f59e0b !important; color: #1a0800 !important;
        font-weight: 800 !important; font-size: 16px !important;
        min-height: 56px !important;border-radius: 12px !important;
        box-shadow: 0 8px 32px rgba(245,158,11,0.45) !important;
        letter-spacing: 0.3px !important;
    }
    button[aria-label="👑 Unlock Premium Access — Start Today"]:hover {
        box-shadow: 0 12px 48px rgba(245,158,11,0.65) !important;
        transform: translateY(-2px) !important;
    }
    </style>
    <div style="padding:32px 48px 8px;text-align:center;">
        <div style="font-size:13px;color:#374f6e;margin-bottom:16px;">Join 1,847+ traders already using StockWins · Cancel anytime · No credit card required</div>
    </div>
    """, unsafe_allow_html=True)
    _,cta,_=st.columns([1,4,1])
    with cta:
        if st.button("👑 Unlock Premium Access — Start Today",key="land_prem",type="primary",use_container_width=True): nav("pricing")

    st.markdown("<br>",unsafe_allow_html=True)

    # ── Composite categories grid ──
    st.markdown(f"""
    <div style="padding:0 48px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
            <div style="font-size:18px;font-weight:800;color:#e2e8f0;">🎯 Our Proprietary Signal Categories</div>
            <span style="background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.35);font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;white-space:nowrap;">✨ Unique to StockWins</span>
        </div>
        <div style="font-size:13px;color:#374f6e;margin-bottom:18px;">We combine multiple independent data signals into composite categories you won't find anywhere else. Each one has a specific multi-factor entry criterion.</div>
    </div>
    """, unsafe_allow_html=True)

    color_map={
        "🔥💥 Squeeze + Buzz":"#ef4444","💡 Hidden Movers":"#3b82f6","🎭 Social Catalyst":"#f97316",
        "🌡️ Sentiment Flip":"#ec4899","📉→📈 Fallen Angels":"#8b5cf6","🔬 Micro-Cap Movers":"#06b6d4",
        "💎 Value Momentum":"#22c55e","⚡📈 Volume Breakout":"#06b6d4","🎯 Smart Reversal":"#f59e0b",
        "🌊 Momentum Leaders":"#22c55e","🏆 Relative Strength":"#a78bfa","🎪 Earnings Catalyst":"#f97316",
        "🔁 Mean Reversion":"#60a5fa","⚡🧲 Smart Money Signal":"#fbbf24","🌪️ Volatility Squeeze":"#c084fc",
        "🎯📊 Triple Lock":"#4ade80","🦈 Sustained Strength":"#34d399",
    }
    cg_items=list(COMPOSITE_CATS.items())
    cg=st.columns(3,gap="small")
    for i,(cat,(desc,tier)) in enumerate(cg_items):
        with cg[i%3]:
            c=color_map.get(cat,BLUE)
            tier_b=f'<span style="background:rgba(245,158,11,.12);color:{GOLD};font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(245,158,11,.3);">⭐ PRO</span>' if tier=="premium" else f'<span style="background:rgba(34,197,94,.1);color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(34,197,94,.3);">FREE</span>'
            st.markdown(f"""<div class="card" style="border-left:3px solid {c};min-height:90px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px;">
                    <div style="font-size:13px;font-weight:700;color:#e2e8f0;">{cat}</div>{tier_b}
                </div>
                <div style="font-size:11px;color:#374f6e;line-height:1.5;">{desc}</div>
            </div>""",unsafe_allow_html=True)

    _,pc,_=st.columns([2,1,2])
    with pc:
        if st.button("Explore All Categories →",key="land_cats",type="primary",use_container_width=True): nav("signup")

    st.markdown("<br>",unsafe_allow_html=True)

    # ── Testimonials ──
    st.markdown('<div style="padding:0 48px;"><div class="sec-hd">What Traders Are Saying</div>',unsafe_allow_html=True)
    tc=st.columns(3,gap="small")
    for col,(stars,txt,name,handle) in zip(tc,[
        ("⭐⭐⭐⭐⭐","The Squeeze + Buzz category flagged AMC 3 days before it ran 40%. The BUY signals are actually explainable — not just a black box.","Michael T.","@miket_trades"),
        ("⭐⭐⭐⭐⭐","Hidden Movers is my secret weapon. Found 3 stocks before they went viral on StockTwits. No other platform has this composite logic.","Sarah K.","@sarahktrader"),
        ("⭐⭐⭐⭐⭐","The plain-English explanations changed how I analyze stocks. I finally understand WHY something is a buy, not just that it is.","David R.","@davidr_swings"),
    ]):
        col.markdown(f'<div class="card card-blue"><div style="margin-bottom:6px;">{stars}</div><div style="font-size:12px;color:#374f6e;line-height:1.65;margin-bottom:12px;">"{txt}"</div><div style="font-size:12px;font-weight:700;color:{BLUE};">{name}</div><div style="font-size:10px;color:#2a3a52;">{handle}</div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # ── FAQ ──
    st.markdown('<div style="padding:0 48px;"><div class="sec-hd">FAQ</div>',unsafe_allow_html=True)
    for q,a in [
        ("Is this financial advice?","No. StockWins is an educational analysis tool providing algorithmic signals. Nothing on this platform constitutes financial, investment, legal, or tax advice. Always consult a licensed financial advisor before making investment decisions."),
        ("What are the Composite Categories?","StockWins proprietary composite categories combine multiple independent data signals to surface unique setups. For example, '🔥💥 Squeeze + Buzz' finds stocks with both high short float AND social momentum trending simultaneously — a specific multi-factor signal you won't find on other platforms."),
        ("What markets does StockWins cover?","US equity markets including NASDAQ, NYSE, S&P 500, Russell, and high-volume small caps. Data includes real-time price, volume, fundamentals, and live social sentiment from StockTwits."),
        ("What's the difference between Free and Premium?","Free: 7 composite categories, market overview, social sentiment, plain-English insights, watchlist. Premium: All 17 categories including short squeeze scanner, advanced screener, full BI analytics, score breakdowns, BUY/SELL recommendations with reasoning, and unlimited watchlists."),
        ("Can I cancel Premium anytime?","Yes. Month-to-month billing. Cancel anytime and keep access through the end of your billing period."),
    ]:
        with st.expander(q):
            st.markdown(f'<div style="font-size:13px;color:#374f6e;line-height:1.75;">{a}</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

    render_footer()

# ─────────────────────────────────────────────────────────────
# PAGE: FEATURES
# ─────────────────────────────────────────────────────────────
def page_features():
    render_topbar()
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown(f"""
    <div style="text-align:center;padding:40px 0 32px;">
        <div style="font-size:11px;font-weight:700;color:{BLUE};letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;">Full Platform Overview</div>
        <div style="font-size:38px;font-weight:900;color:#f1f5f9;letter-spacing:-1.5px;margin-bottom:10px;">Everything in StockWins</div>
        <div style="font-size:15px;color:#374f6e;max-width:560px;margin:0 auto;">Built for traders who want data-driven clarity — not noise. Every feature is designed to answer one question: <em>should I pay attention to this stock right now?</em></div>
    </div>
    """, unsafe_allow_html=True)

    features_data = [
        ("🎯","Proprietary Composite Scoring","17 unique composite categories combining RSI, MACD, volume, short interest, social sentiment, and Bollinger Bands into single actionable signals. Categories like '🔥💥 Squeeze + Buzz', '🌪️ Volatility Squeeze', and '🎯📊 Triple Lock' are only available on StockWins. Each category has a specific multi-factor entry criterion that filters our full universe in real time.","All plans"),
        ("🟢","BUY / WATCH / AVOID Signals","Every stock gets a clear recommendation based on our scoring engine — STRONG BUY, BUY, SQUEEZE BUY, WATCH, HOLD/WAIT, or AVOID — with plain-English reasoning explaining exactly why the signal was triggered. No jargon. No unexplained scores.","All plans"),
        ("💡","Plain-English Technical Analysis","RSI, MACD, moving average crossovers, Bollinger Bands, and volume spikes all translated into conversational sentences. We explain what a Golden Cross means in terms a beginner understands while still giving experts the data they need.","All plans"),
        ("📡","Live Social Sentiment","Real-time StockTwits data showing bullish/bearish % for any stock, watchlist counts, and trending detection. Our composite categories use this data to find early momentum before price moves.","All plans"),
        ("📊","Market Overview Dashboard","Live index data (NASDAQ, S&P 500, DOW, VIX, Russell), sector performance heatmap, market pulse indicator, and top trending tickers in a single clean view.","All plans"),
        ("⭐","Smart Watchlist","Track your stocks with automatic daily scoring. Premium users get watchlist analytics showing average score, % in the green, risk distribution, and sentiment breakdown across holdings.","All plans (Premium: analytics)"),
        ("🔔","Price Alerts","Set price-above or price-below alerts for any ticker. Alerts are managed from your account settings and displayed in your dashboard.","All plans"),
        ("🔍","Advanced Stock Screener","Multi-factor screener with RSI range filters, MACD bullish/bearish filter, above/below MA filter, volume spike detection, minimum StockWins score, short float threshold, and category filters. Save and name your screener configurations.","Premium"),
        ("📈","BI Analytics Dashboard","Interactive Plotly charts: Top Gainers/Losers bar charts, Sector Performance bar chart, Social Sentiment bubble chart, Volume Surge scatter plot, and the Composite Opportunity Matrix — our exclusive heatmap showing signal strength across 10 tickers × 5 signal types.","Premium"),
        ("💥","Short Squeeze Scanner","Dedicated scanner identifying stocks with high short float (>10%), high days-to-cover, and rising momentum. Filters by social trending and volume to find squeeze setups before they run.","Premium"),
        ("📉→📈","Deep Stock Reports","Full stock detail pages with 60-day price chart + MA20/MA50 overlaid, volume bar chart vs average, complete plain-English analysis, social sentiment bar, score breakdown, why-flagged section, and related stocks.","Premium (charts)"),
        ("🎪","Email Digest (Coming Q3 2026)","Daily or weekly digest of your top-scored watchlist stocks, new BUY signals, and trending composite category alerts delivered to your inbox. Configurable from account settings.","Premium"),
        ("🛠️","Admin Panel","Full user management (promote/demote roles, delete accounts), API configuration with Twelve Data integration, site analytics with simulated growth charts, data source health monitoring, and security checklist with Streamlit Secrets setup guide.","Admin/Owner"),
        ("🔑","Ranking Controls","Sort and filter any category by StockWins Score, % change today, volume ratio, short float, or social sentiment. Drag-and-drop ranking priority controls for power users.","Premium"),
        ("🔐","Secure Authentication","Passwords stored as SHA-256 hashes. Credentials loaded exclusively from Streamlit Cloud Secrets — never hardcoded. Supports both flat secrets and [accounts] section format.","All plans"),
    ]

    for i,(icon,title,desc,tier) in enumerate(features_data):
        tc_="card-gold" if tier=="Premium" else "card-blue" if tier=="Admin/Owner" else "card"
        tier_c=GOLD if tier=="Premium" else "#60a5fa" if tier=="Admin/Owner" else "#4ade80"
        tier_bg=f"rgba(245,158,11,.12)" if tier=="Premium" else "rgba(96,165,250,.12)" if tier=="Admin/Owner" else "rgba(74,222,128,.1)"
        st.markdown(f"""<div class="{tc_}" style="display:flex;gap:16px;align-items:flex-start;margin-bottom:8px;">
            <div style="font-size:24px;flex-shrink:0;padding-top:2px;">{icon}</div>
            <div style="flex:1;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">
                    <div style="font-size:14px;font-weight:700;color:#e2e8f0;">{title}</div>
                    <span style="background:{tier_bg};color:{tier_c};font-size:9px;font-weight:700;padding:2px 8px;border-radius:20px;border:1px solid {tier_c}33;">{tier}</span>
                </div>
                <div style="font-size:13px;color:#374f6e;line-height:1.7;">{desc}</div>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    _,cta,_=st.columns([1,2,1])
    with cta:
        if st.button("Start Free →",key="feat_su",type="primary",use_container_width=True): nav("signup")
        st.markdown("<br>",unsafe_allow_html=True)
        if gold_btn("Go Premium","feat_prem"): nav("pricing")
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# AUTH PAGES
# ─────────────────────────────────────────────────────────────
def page_login():
    render_topbar()
    _,cc,_=st.columns([1,2,1])
    with cc:
        st.markdown(f'<div style="text-align:center;padding:36px 0 24px;"><div style="font-size:26px;font-weight:800;color:#e2e8f0;margin-bottom:6px;">Welcome Back 👋</div><div style="font-size:13px;color:#374f6e;">Sign in to your StockWins account</div></div>',unsafe_allow_html=True)
        with st.form("lf",clear_on_submit=False):
            email=st.text_input("Email address",label_visibility="visible")
            pw=st.text_input("Password",type="password",label_visibility="visible")
            if st.form_submit_button("Sign In →",type="primary",use_container_width=True):
                if not email or not pw: st.error("Please enter your email and password.")
                elif login(email,pw): nav("dashboard")
                else: st.error("Invalid email or password.")

        # Show hints based on whether secrets are configured
        has_secrets=False
        try: has_secrets=bool(st.secrets.get("owner_email","") or st.secrets.get("owner_pw_hash",""))
        except: pass

        if not has_secrets:
            st.markdown(f'<div style="background:#080b14;border:1px solid {BORDER};border-radius:8px;padding:12px 14px;margin-top:12px;font-size:12px;color:#374f6e;"><span style="color:#93b4fd;font-weight:600;">Demo accounts:</span><br><span style="font-family:\'JetBrains Mono\',monospace;">demo@stockwins.com</span> / <span style="font-family:\'JetBrains Mono\',monospace;">demo123</span><br><span style="font-family:\'JetBrains Mono\',monospace;">premium@stockwins.com</span> / <span style="font-family:\'JetBrains Mono\',monospace;">premium1</span></div>',unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#080b14;border:1px solid {BORDER};border-radius:8px;padding:12px 14px;margin-top:12px;font-size:12px;color:#374f6e;text-align:center;">Use the email and password you set in Streamlit Secrets.</div>',unsafe_allow_html=True)

        st.markdown("<br>",unsafe_allow_html=True)
        bc1,bc2=st.columns(2,gap="small")
        with bc1:
            if st.button("Create Free Account →",key="l2s",use_container_width=True,type="primary"): nav("signup")
        with bc2:
            if st.button("Forgot password?",key="l2f",use_container_width=True): nav("forgot_pw")
        if st.button("← Back to Home",key="l2h",use_container_width=True): nav("landing")

def page_signup():
    render_topbar()
    _,cc,_=st.columns([1,2,1])
    with cc:
        st.markdown('<div style="text-align:center;padding:36px 0 24px;"><div style="font-size:26px;font-weight:800;color:#e2e8f0;margin-bottom:6px;">Create Your Account 🚀</div><div style="font-size:13px;color:#374f6e;">Free forever. No credit card. No API keys.</div></div>',unsafe_allow_html=True)
        with st.form("sf"):
            name=st.text_input("Full name",placeholder="Jane Doe")
            email=st.text_input("Email",placeholder="you@example.com")
            pw=st.text_input("Password",type="password",placeholder="Min 6 characters")
            pw2=st.text_input("Confirm password",type="password")
            agree=st.checkbox("I agree to the Terms of Service. I understand StockWins is for educational purposes only and is not financial advice.")
            if st.form_submit_button("Create Free Account →",type="primary",use_container_width=True):
                if not all([name,email,pw,pw2]): st.error("Please fill in all fields.")
                elif pw!=pw2: st.error("Passwords don't match.")
                elif len(pw)<6: st.error("Password must be 6+ characters.")
                elif not agree: st.error("Please agree to the Terms of Service.")
                else:
                    ok,msg=signup(email,pw,name)
                    if ok: st.success(f"✅ Welcome, {name}!"); time.sleep(0.3); nav("dashboard")
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
                else: st.error("No account found.")
        if st.button("← Back to Login",key="f2l",use_container_width=True): nav("login")

# ─────────────────────────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────────────────────────
def page_dashboard():
    render_topbar("dashboard")
    st.markdown('<div class="pg">',unsafe_allow_html=True)

    # ── Our Composite Categories FIRST (the hero) ──
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
        <div style="font-size:17px;font-weight:700;color:#e2e8f0;">🎯 Our Proprietary Signal Categories</div>
        <span style="background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.35);font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;">✨ Unique to StockWins</span>
    </div>
    <div style="font-size:13px;color:#374f6e;margin-bottom:16px;">Combining multiple independent signals to surface unique opportunities not visible through standard technical analysis.</div>
    """, unsafe_allow_html=True)

    color_map={
        "🔥💥 Squeeze + Buzz":"#ef4444","💡 Hidden Movers":"#3b82f6","🎭 Social Catalyst":"#f97316",
        "🌡️ Sentiment Flip":"#ec4899","📉→📈 Fallen Angels":"#8b5cf6","🔬 Micro-Cap Movers":"#06b6d4",
        "💎 Value Momentum":"#22c55e","⚡📈 Volume Breakout":"#06b6d4","🎯 Smart Reversal":"#f59e0b",
        "🌊 Momentum Leaders":"#22c55e","🏆 Relative Strength":"#a78bfa","🎪 Earnings Catalyst":"#f97316",
        "🔁 Mean Reversion":"#60a5fa","⚡🧲 Smart Money Signal":"#fbbf24","🌪️ Volatility Squeeze":"#c084fc",
        "🎯📊 Triple Lock":"#4ade80","🦈 Sustained Strength":"#34d399",
    }
    comp_items=list(COMPOSITE_CATS.items())
    for i in range(0,len(comp_items),2):
        cols=st.columns(2,gap="small")
        for j,col in enumerate(cols):
            if i+j<len(comp_items):
                cat,(desc,tier)=comp_items[i+j]
                is_locked=tier=="premium" and not is_premium()
                c=color_map.get(cat,BLUE)
                tier_tag=f'<span style="background:rgba(245,158,11,.12);color:{GOLD};font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(245,158,11,.3);">⭐ PREMIUM</span>' if tier=="premium" else f'<span style="background:rgba(34,197,94,.1);color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(34,197,94,.3);">FREE</span>'
                with col:
                    st.markdown(f"""<div class="card" style="border-left:3px solid {c};">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px;">
                            <div style="font-size:14px;font-weight:700;color:#e2e8f0;">{cat} {"🔒" if is_locked else ""}</div>{tier_tag}
                        </div>
                        <div style="font-size:11px;color:#374f6e;margin-bottom:8px;">{desc}</div>
                    </div>""",unsafe_allow_html=True)
                    btn_key=f"dash_cat_{cat[:20].replace(' ','_').replace('+','p')}"
                    if st.button(f"Explore {cat} →",key=btn_key,use_container_width=True):
                        if is_locked: nav("pricing")
                        else: st.session_state.discover_cat=cat; nav("discover")

    st.markdown('<div class="div-line"></div>',unsafe_allow_html=True)

    # ── StockTwits Hot + Squeeze preview ──
    left,right=st.columns(2,gap="small")
    with left:
        st.markdown(f'<div class="sec-hd">📡 StockTwits Hot Stocks <span class="tag tag-live" style="margin-left:auto;">Live</span></div>',unsafe_allow_html=True)
        hot=st_hot(); prog=st.progress(0,"Loading…")
        for i,t in enumerate(hot[:5]):
            prog.progress((i+1)/5)
            q=get_quote(t)
            if q:
                s=st_sent(t); cc_=GREEN if q["pct"]>=0 else RED; ar="▲" if q["pct"]>=0 else "▼"
                st.markdown(f"""<div class="sr">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div><span class="sr-tick">{t}</span><span class="b b-hot" style="margin-left:6px;">🔥</span>
                        <div class="sr-name">{q.get('name','')[:28]}</div>
                        <div class="sr-why">→ {s['bull']}% bullish · {s.get('wl',0):,} watching</div></div>
                        <div style="text-align:right;"><div class="sr-price">${q['price']:,.2f}</div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{cc_};">{ar}{abs(q['pct']):.2f}%</div></div>
                    </div></div>""",unsafe_allow_html=True)
        prog.empty()

    with right:
        st.markdown(f'<div class="sec-hd">🔥💥 Squeeze + Buzz Preview <span class="tag tag-live" style="margin-left:auto;">Composite</span></div>',unsafe_allow_html=True)
        st.markdown('<div style="font-size:12px;color:#374f6e;margin-bottom:10px;">High short float + social trending = explosive combo</div>',unsafe_allow_html=True)
        prog=st.progress(0,"Scanning…"); shown=0
        for i,t in enumerate(["GME","AMC","MSTR","MULN","SPCE"]):
            prog.progress((i+1)/5)
            info=yf_fund(t); sf=(info.get("sf",0) or 0)*100
            if sf>=8:
                q=get_quote(t)
                if q:
                    shown+=1; cc_=GREEN if q["pct"]>=0 else RED
                    st.markdown(f"""<div class="sr">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div><span class="sr-tick">{t}</span>
                            <div class="sr-name">{q.get('name','')[:28]}</div>
                            <div class="sr-why">→ Short float: <span style="color:{RED};font-weight:700;">{sf:.1f}%</span> · DTC: {info.get('dtc',0) or 0:.1f}d</div></div>
                            <div style="text-align:right;"><div class="sr-price">${q['price']:,.2f}</div>
                            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{cc_};">{"▲" if q['pct']>=0 else "▼"}{abs(q['pct']):.2f}%</div></div>
                        </div></div>""",unsafe_allow_html=True)
        prog.empty()
        if shown==0: st.info("No squeeze candidates above threshold right now.")
        if st.button("Full Squeeze Scanner →",key="dash_sq",use_container_width=True):
            if is_premium(): st.session_state.discover_cat="🔥💥 Squeeze + Buzz"; nav("discover")
            else: nav("pricing")

    st.markdown('<div class="div-line"></div>',unsafe_allow_html=True)

    # ── Market Overview (bottom) ──
    st.markdown('<div class="sec-hd">📊 Market Overview</div>',unsafe_allow_html=True)
    with st.spinner("Loading…"):
        idx=get_indexes(); secs=get_sectors()
    idx_cols=st.columns(len(idx))
    for col,(name,d) in zip(idx_cols,idx.items()):
        c=GREEN if d["pct"]>=0 else RED; ar="▲" if d["pct"]>=0 else "▼"
        hist=d.get("hist",[])
        bars=""
        if hist:
            mn,mx=min(hist),max(hist); rng=mx-mn if mx!=mn else 1
            bars=''.join([f'<div style="height:{int(12*(v-mn)/rng+3)}px;width:4px;background:{GREEN if d["pct"]>=0 else RED};border-radius:2px;display:inline-block;margin-right:1px;vertical-align:bottom;opacity:0.6;"></div>' for v in hist])
        col.markdown(f"""<div class="idx-w">
            <div class="idx-name">{name}</div><div class="idx-price">{d['price']:,.2f}</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;color:{c};">{ar}{abs(d['pct']):.2f}%</div>
            <div style="margin-top:8px;height:16px;display:flex;align-items:flex-end;">{bars}</div>
        </div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    sec_sorted=sorted(secs.items(),key=lambda x:x[1],reverse=True)
    sc5=st.columns(5)
    for i,(sec,chg) in enumerate(sec_sorted):
        with sc5[i%5]:
            cls="hm-hi" if chg>0.15 else "hm-lo" if chg<-0.15 else "hm-nu"
            bg={"hm-hi":"#04200d","hm-lo":"#200404","hm-nu":"#101827"}[cls]
            tc={"hm-hi":GREEN,"hm-lo":RED,"hm-nu":"#4a5e7a"}[cls]
            st.markdown(f'<div style="background:{bg};color:{tc};border-radius:5px;padding:7px 4px;text-align:center;font-size:11px;font-weight:700;margin-bottom:4px;"><div style="font-size:9px;margin-bottom:1px;">{sec}</div>{"▲" if chg>=0 else "▼"}{abs(chg):.1f}%</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: DISCOVER
# ─────────────────────────────────────────────────────────────
def page_discover():
    render_topbar("discover")
    fc,mc=st.columns([1,4],gap="small")
    with fc:
        st.markdown('<div style="padding:16px 0 0 0;">',unsafe_allow_html=True)
        st.markdown('<div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1.5px;text-transform:uppercase;padding:0 0 6px;">Our Composite Picks</div>',unsafe_allow_html=True)
        for cat,(desc,tier) in COMPOSITE_CATS.items():
            is_locked=tier=="premium" and not is_premium()
            safe=cat.replace(" ","_").replace("+","p").replace("→","r").replace("🌡️","T").replace("📉","D")[:28]
            if st.button(f"{cat}{'  ⭐' if is_locked else ''}",key=f"disc_c_{safe}",use_container_width=True):
                if is_locked: nav("pricing")
                else: st.session_state.discover_cat=cat; st.rerun()
        st.markdown('<div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1.5px;text-transform:uppercase;padding:12px 0 6px;">Standard</div>',unsafe_allow_html=True)
        for cat in CATEGORIES:
            if st.button(cat,key=f"disc_s_{cat[:20].replace(' ','_')}",use_container_width=True):
                st.session_state.discover_cat=cat; st.rerun()
        if not is_premium():
            st.markdown("<br>",unsafe_allow_html=True)
            if gold_btn("Unlock All →","disc_up"): nav("pricing")
        st.markdown('</div>',unsafe_allow_html=True)
    with mc:
        sel=st.session_state.get("discover_cat","🔥💥 Squeeze + Buzz")
        is_comp=sel in COMPOSITE_CATS
        tier_str=""
        if is_comp:
            _,tier=COMPOSITE_CATS[sel]
            tier_str=f'<span class="tag {"tag-prem" if tier=="premium" else "tag-free"}" style="margin-left:6px;">{"PREMIUM ⭐" if tier=="premium" else "FREE"}</span>'
        desc_str=COMPOSITE_CATS[sel][0] if is_comp else f"Browse all {sel} stocks"
        st.markdown('<div class="pg" style="padding-top:16px;">',unsafe_allow_html=True)
        st.markdown(f'<div class="sec-hd">{sel} {tier_str}</div>',unsafe_allow_html=True)
        if is_comp: st.markdown(f'<div style="font-size:12px;color:#374f6e;margin-bottom:12px;font-style:italic;">{desc_str}</div>',unsafe_allow_html=True)
        is_locked=is_comp and COMPOSITE_CATS[sel][1]=="premium" and not is_premium()
        if is_locked: render_lock(sel)
        else: render_cat(sel,show_why=is_comp)
        st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: STOCK DETAIL
# ─────────────────────────────────────────────────────────────
def page_detail():
    render_topbar()
    ticker=st.session_state.get("detail_ticker")
    data=st.session_state.get("detail_data",{})

    # ── Back button ──
    if st.button("← Back",key="back_det"):
        go_back()
    if not ticker: st.warning("No stock selected."); return

    q=data.get("q") or get_quote(ticker)
    df=data.get("df") or yf_ohlcv(ticker,90)
    info=data.get("info") or yf_fund(ticker)
    sent=data.get("sent") or st_sent(ticker)
    sc,bd,op,risk,conf=compute_scores(df,info,sent)
    ig=get_insights(df,info)
    rec_lbl,rec_clr,rec_txt=get_recommendation(sc,bd,info)
    hot=ticker in st_hot()
    if not q: st.error(f"Could not load {ticker}."); return

    pct=q.get("pct",0); price=q.get("price",0); prev=q.get("prev",0); chg=q.get("chg",0)
    cc=GREEN if pct>=0 else RED; ar="▲" if pct>=0 else "▼"
    rc=risk_color(risk); sf=(info.get("sf",0) or 0)*100
    mc_v=info.get("mktcap",0)
    mc_s=f"${mc_v/1e12:.2f}T" if mc_v>=1e12 else f"${mc_v/1e9:.2f}B" if mc_v>=1e9 else f"${mc_v/1e6:.0f}M" if mc_v else "N/A"

    st.markdown('<div class="pg">',unsafe_allow_html=True)

    # Report header
    h1,h2,h3=st.columns([3,2,2],gap="small")
    with h1:
        hot_b='<span class="b b-hot">🔥 HOT</span>' if hot else ""
        st.markdown(f"""<div style="padding:4px 0;">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:800;color:#60a5fa;">{ticker}</span>{hot_b}
                <span style="display:inline-block;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:800;background:{rec_clr}22;color:{rec_clr};border:1px solid {rec_clr}44;">{rec_lbl}</span>
            </div>
            <div style="font-size:15px;color:#4a5e7a;margin-bottom:2px;">{q.get('name','')}</div>
            <div style="font-size:12px;color:#2a3a52;">{info.get('sector','N/A')} · {info.get('industry','N/A')}</div>
            <div style="margin-top:8px;font-size:13px;color:#374f6e;font-style:italic;">→ {rec_txt}</div>
            <div style="margin-top:6px;font-size:11px;color:{rc};">⚡ {risk} Risk · {conf} confidence</div>
        </div>""",unsafe_allow_html=True)
    with h2:
        st.markdown(f"""<div style="text-align:right;padding:4px 0;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:36px;font-weight:800;color:#e2e8f0;letter-spacing:-1px;">${price:,.2f}</div>
            <div style="font-size:17px;font-weight:700;color:{cc};">{ar} ${abs(chg):.2f} ({abs(pct):.2f}%)</div>
            <div style="font-size:12px;color:#2a3a52;margin-top:4px;">Prev close: ${prev:,.2f}</div>
        </div>""",unsafe_allow_html=True)
    with h3:
        sc_c=GREEN if sc>=65 else GOLD if sc>=40 else RED
        sc_bg="#04200d" if sc>=65 else "#1a1000" if sc>=40 else "#200404"
        st.markdown(f"""<div style="background:{sc_bg};border:1px solid {sc_c};border-radius:10px;padding:16px;text-align:center;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:42px;font-weight:800;color:{sc_c};">{sc}</div>
            <div style="font-size:10px;color:{sc_c};text-transform:uppercase;letter-spacing:1px;margin-top:2px;">StockWins Score</div>
            <div style="font-size:11px;color:#2a3a52;margin-top:4px;">{op}</div>
        </div>""",unsafe_allow_html=True)

    st.divider()

    # Session stats
    s_items=[("Open",f"${q.get('open',0):,.2f}",None),("High",f"${q.get('high',0):,.2f}",GREEN),
             ("Low",f"${q.get('low',0):,.2f}",RED),("Volume",f"{q.get('volume',0)/1e6:.2f}M",None),
             ("vs Avg",f"{q.get('volume',1)/(info.get('avgvol',1) or 1):.1f}×",None),
             ("Mkt Cap",mc_s,None),("52W High",f"${info.get('hi52',0):,.2f}",GREEN),
             ("52W Low",f"${info.get('lo52',0):,.2f}",RED),("P/E",f"{info.get('pe','N/A')}",None),
             ("Short Float",f"{sf:.1f}%",RED if sf>=20 else None)]
    sc_=st.columns(5)
    for i,(lbl,val,vc) in enumerate(s_items):
        with sc_[i%5]:
            cs_=f"color:{vc};" if vc else ""
            st.markdown(f'<div class="stat" style="margin-bottom:8px;"><div class="stat-l">{lbl}</div><div style="font-family:\'JetBrains Mono\',monospace;font-size:14px;font-weight:700;{cs_}color:#e2e8f0;">{val}</div></div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Chart + Insights
    cc_col,ci_col=st.columns([3,2],gap="small")
    with cc_col:
        st.markdown('<div class="sec-hd">📈 Price Chart (90 Days)</div>',unsafe_allow_html=True)
        if df is not None and len(df)>5:
            pdf=df.copy(); pdf["MA20"]=pdf["close"].rolling(20).mean(); pdf["MA50"]=pdf["close"].rolling(min(50,len(pdf))).mean()
            if HAS_PLOTLY:
                fig=go.Figure()
                fig.add_trace(go.Scatter(x=pdf["datetime"],y=pdf["close"],name="Price",line=dict(color=BLUE,width=2),fill="tozeroy",fillcolor="rgba(37,99,235,0.05)"))
                fig.add_trace(go.Scatter(x=pdf["datetime"],y=pdf["MA20"],name="MA20",line=dict(color=GOLD,width=1,dash="dot")))
                fig.add_trace(go.Scatter(x=pdf["datetime"],y=pdf["MA50"],name="MA50",line=dict(color=RED,width=1,dash="dot")))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=280,
                    legend=dict(orientation="h",yanchor="bottom",y=1.02,bgcolor="rgba(0,0,0,0)",font=dict(color="#6b7fa0",size=11)),
                    xaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=10)),
                    yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a",tickfont=dict(size=10)))
                st.plotly_chart(fig,use_container_width=True)
                # Volume
                avg_v=df["volume"].rolling(20).mean()
                fig2=go.Figure()
                colors_v=[GREEN if v>=a else RED for v,a in zip(df["volume"],avg_v)]
                fig2.add_trace(go.Bar(x=df["datetime"],y=df["volume"],marker_color=colors_v))
                fig2.add_trace(go.Scatter(x=df["datetime"],y=avg_v,name="20d Avg",line=dict(color=GOLD,width=1,dash="dash")))
                fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=120,showlegend=False,
                    xaxis=dict(showgrid=False,color="#4a5e7a"),yaxis=dict(showgrid=False,color="#4a5e7a"))
                st.plotly_chart(fig2,use_container_width=True)
            else:
                cdf=pdf[["datetime","close","MA20","MA50"]].rename(columns={"datetime":"Date","close":"Price"}).set_index("Date")
                st.line_chart(cdf,color=[BLUE,GOLD,RED])
        else: st.info("Chart data unavailable.")

        if bd:
            st.markdown('<div class="sec-hd" style="margin-top:12px;">Score Breakdown</div>',unsafe_allow_html=True)
            if is_premium():
                max_v={"Momentum":25,"Trend":20,"MACD":15,"Volume":15,"Sentiment":15,"Squeeze":10}
                for comp,pts in bd.items():
                    mx=max_v.get(comp,15); pct_=pts/mx if mx>0 else 0
                    c_=GREEN if pct_>=0.8 else GOLD if pct_>=0.4 else RED
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                        <div style="width:76px;font-size:11px;color:#374f6e;">{comp}</div>
                        <div style="flex:1;background:rgba(255,255,255,.05);border-radius:3px;height:6px;">
                            <div style="background:{c_};width:{int(pct_*100)}%;height:6px;border-radius:3px;"></div>
                        </div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:{c_};width:32px;text-align:right;">{pts}/{mx}</div>
                    </div>""",unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="background:#080b14;border:1px solid rgba(245,158,11,.2);border-radius:7px;padding:10px;font-size:12px;color:{GOLD};">🔒 Score breakdown is Premium only.</div>',unsafe_allow_html=True)

    with ci_col:
        st.markdown('<div class="sec-hd">💡 Plain-English Analysis</div>',unsafe_allow_html=True)
        if ig:
            for lbl,txt,s,conf in ig[:7]:
                cls="ins-bull" if s=="bull" else "ins-bear" if s=="bear" else ""
                bc="b-bull" if s=="bull" else "b-bear" if s=="bear" else "b-neu"
                bl="Bullish" if s=="bull" else "Bearish" if s=="bear" else "Neutral"
                st.markdown(f"""<div class="ins {cls}">
                    <div class="ins-label">{lbl} <span class="b {bc}">{bl}</span>
                        <span style="font-size:10px;color:#2a3a52;margin-left:auto;"> · {conf}</span></div>
                    <div class="ins-text">{txt}</div>
                </div>""",unsafe_allow_html=True)
        else: st.info("No indicators available.")

        st.markdown('<div class="sec-hd" style="margin-top:14px;">📡 Social Sentiment</div>',unsafe_allow_html=True)
        bull=sent.get("bull",50)
        st.markdown(f"""<div class="card">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="font-size:12px;font-weight:700;color:{GREEN};">🟢 Bullish {bull}%</span>
                <span style="font-size:12px;font-weight:700;color:{RED};">🔴 Bearish {100-bull}%</span>
            </div>
            <div style="background:rgba(255,255,255,.05);border-radius:5px;height:8px;overflow:hidden;">
                <div style="background:linear-gradient(90deg,{GREEN},{GREEN}88);width:{bull}%;height:8px;"></div>
            </div>
            <div style="font-size:11px;color:#2a3a52;margin-top:8px;">👥 {sent.get('wl',0):,} watching · {sent.get('msgs',0)} recent posts</div>
        </div>""",unsafe_allow_html=True)

    # Why flagged
    st.markdown('<div class="div-line"></div>',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">🎯 Why This Stock Is On Your Radar</div>',unsafe_allow_html=True)
    reasons=[]
    if sc>=70: reasons.append(("Strong multi-factor signal — momentum, trend, MACD, and volume align","bull"))
    if sent.get("bull",50)>=65: reasons.append((f"{sent['bull']}% of StockTwits traders are currently bullish","bull"))
    if sf>=20: reasons.append((f"{sf:.0f}% of shares are sold short — rising price forces short covering (squeeze)","bull"))
    if hot: reasons.append(("Currently trending on StockTwits Hot list","bull"))
    for lbl,_,sv,_ in ig[:4]: reasons.append((lbl,sv))
    rc2=st.columns(2)
    for i,(r,sv) in enumerate(reasons[:6]):
        em="🟢" if sv=="bull" else "🔴" if sv=="bear" else "⚪"
        with rc2[i%2]:
            st.markdown(f'<div style="background:#080b14;border:1px solid {BORDER};border-radius:7px;padding:9px 13px;margin-bottom:5px;font-size:12px;color:#374f6e;">{em} {r}</div>',unsafe_allow_html=True)

    # Related
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
                    rc_=GREEN if rq["pct"]>=0 else RED
                    col.markdown(f'<div class="stat" style="cursor:pointer;"><div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;font-weight:700;color:#60a5fa;">{rt}</div><div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;font-weight:700;color:#e2e8f0;">${rq["price"]:,.2f}</div><div style="font-size:11px;font-weight:700;color:{rc_};">{"▲" if rq["pct"]>=0 else "▼"}{abs(rq["pct"]):.2f}%</div></div>',unsafe_allow_html=True)
                    if col.button("View",key=f"rel_{rt}",use_container_width=True):
                        st.session_state.detail_ticker=rt; st.session_state.detail_data={}; st.rerun()

    if info.get("desc"):
        with st.expander(f"About {q.get('name',ticker)}"):
            st.markdown(f'<div style="font-size:13px;color:#374f6e;line-height:1.7;">{info["desc"]}</div>',unsafe_allow_html=True)

    # Actions
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
    st.markdown('<div class="sec-hd">📊 BI Analytics Dashboard <span class="tag tag-live" style="margin-left:auto;">Live</span></div>',unsafe_allow_html=True)

    with st.spinner("Loading analytics…"):
        movers=get_bi_movers(); secs=get_sectors(); idx=get_indexes(); hot=st_hot()

    gainers=sorted(movers,key=lambda x:x["pct"],reverse=True)
    losers=sorted(movers,key=lambda x:x["pct"])
    vol_ldrs=sorted(movers,key=lambda x:x["vr"],reverse=True)
    top_g=gainers[0] if gainers else {}; top_l=losers[0] if losers else {}; top_v=vol_ldrs[0] if vol_ldrs else {}
    bull_sec=max(secs,key=secs.get) if secs else "N/A"; avg_pct=sum(m["pct"] for m in movers)/len(movers) if movers else 0

    sw=st.columns(5)
    for col,(v,l,c) in zip(sw,[
        (top_g.get("t","—"),f"Top Gainer +{top_g.get('pct',0):.1f}%",GREEN),
        (top_l.get("t","—"),f"Top Loser {top_l.get('pct',0):.1f}%",RED),
        (top_v.get("t","—"),f"Vol King {top_v.get('vr',0):.1f}× avg","#60a5fa"),
        (bull_sec,f"+{secs.get(bull_sec,0):.1f}% today",GREEN),
        ("Bullish" if avg_pct>0.3 else "Bearish" if avg_pct<-0.3 else "Neutral",f"Avg {avg_pct:+.2f}%",GREEN if avg_pct>0 else RED),
    ]):
        col.markdown(f'<div class="stat"><div class="stat-v" style="font-size:15px;color:{c};">{v}</div><div class="stat-l">{l}</div></div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    tabs=st.tabs(["📈 Leaderboards","🗺️ Sector Chart","📡 Social","🔊 Volume Surge","🎯 Opportunity Matrix"])

    with tabs[0]:
        lc1,lc2,lc3=st.columns(3,gap="small")
        with lc1:
            st.markdown(f'<div style="font-size:12px;font-weight:700;color:{GREEN};margin-bottom:8px;">🏆 Top Gainers</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                top10g=gainers[:10]
                fig=go.Figure(go.Bar(x=[m["pct"] for m in top10g],y=[m["t"] for m in top10g],orientation="h",marker_color=GREEN,text=[f"+{m['pct']:.1f}%" for m in top10g],textposition="outside",textfont=dict(color=GREEN,size=10)))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=60,t=0,b=0),height=280,xaxis=dict(showgrid=False,color="#4a5e7a"),yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=11)))
                st.plotly_chart(fig,use_container_width=True)
        with lc2:
            st.markdown(f'<div style="font-size:12px;font-weight:700;color:{RED};margin-bottom:8px;">📉 Top Losers</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                top10l=losers[:10]
                fig=go.Figure(go.Bar(x=[m["pct"] for m in top10l],y=[m["t"] for m in top10l],orientation="h",marker_color=RED,text=[f"{m['pct']:.1f}%" for m in top10l],textposition="outside",textfont=dict(color=RED,size=10)))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=50,t=0,b=0),height=280,xaxis=dict(showgrid=False,color="#4a5e7a"),yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=11)))
                st.plotly_chart(fig,use_container_width=True)
        with lc3:
            st.markdown(f'<div style="font-size:12px;font-weight:700;color:#60a5fa;margin-bottom:8px;">🔊 Volume Leaders</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                top10v=vol_ldrs[:10]
                colors_v=[RED if m["vr"]>=3 else GOLD if m["vr"]>=2 else "#60a5fa" for m in top10v]
                fig=go.Figure(go.Bar(x=[m["vr"] for m in top10v],y=[m["t"] for m in top10v],orientation="h",marker_color=colors_v,text=[f"{m['vr']:.1f}×" for m in top10v],textposition="outside"))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=50,t=0,b=0),height=280,xaxis=dict(showgrid=False,color="#4a5e7a"),yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=11)))
                st.plotly_chart(fig,use_container_width=True)

    with tabs[1]:
        sec_sorted=sorted(secs.items(),key=lambda x:x[1],reverse=True)
        if HAS_PLOTLY:
            df_s=pd.DataFrame(sec_sorted,columns=["Sector","Change %"])
            colors=[f"rgba(34,197,94,{min(0.9,abs(c)/3+0.3)})" if c>0 else f"rgba(239,68,68,{min(0.9,abs(c)/3+0.3)})" for c in df_s["Change %"]]
            fig=go.Figure(go.Bar(x=df_s["Sector"],y=df_s["Change %"],marker_color=colors,text=[f"{'▲' if c>=0 else '▼'}{abs(c):.2f}%" for c in df_s["Change %"]],textposition="outside",textfont=dict(color="#94a3b8",size=11)))
            fig.add_hline(y=0,line=dict(color="rgba(255,255,255,0.15)",width=1))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=10,b=0),height=300,xaxis=dict(showgrid=False,color="#4a5e7a"),yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a"))
            st.plotly_chart(fig,use_container_width=True)

    with tabs[2]:
        sc1,sc2=st.columns(2)
        with sc1:
            st.markdown(f'<div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:8px;">🔥 Trending on StockTwits</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                sent_data=[{"ticker":t,"bull":st_sent(t)["bull"]} for t in hot[:8]]
                df_sent=pd.DataFrame(sent_data).sort_values("bull",ascending=False)
                colors_s=[GREEN if b>=60 else RED if b<40 else "#6b7fa0" for b in df_sent["bull"]]
                fig=go.Figure(go.Bar(x=df_sent["ticker"],y=df_sent["bull"],marker_color=colors_s,text=[f"{b}% bull" for b in df_sent["bull"]],textposition="outside"))
                fig.add_hline(y=50,line=dict(color="rgba(255,255,255,0.15)",width=1,dash="dot"))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=10,b=0),height=250,yaxis=dict(range=[0,110],showgrid=False,color="#4a5e7a"),xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=11)))
                st.plotly_chart(fig,use_container_width=True)
        with sc2:
            st.markdown(f'<div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:8px;">👥 Most Watchlisted</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                targets=["NVDA","TSLA","AMD","AAPL","MSTR","PLTR","GME","META"]
                wl_data=sorted([(t,st_sent(t)) for t in targets],key=lambda x:x[1].get("wl",0),reverse=True)
                wl_df=pd.DataFrame([{"t":t,"wl":s["wl"]} for t,s in wl_data])
                fig=go.Figure(go.Bar(x=wl_df["t"],y=wl_df["wl"],marker_color="rgba(96,165,250,0.7)",text=[f"{w:,}" for w in wl_df["wl"]],textposition="outside"))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=10,b=0),height=250,yaxis=dict(showgrid=False,color="#4a5e7a"),xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=11)))
                st.plotly_chart(fig,use_container_width=True)

    with tabs[3]:
        surge=[m for m in movers if m["vr"]>=1.5]; surge.sort(key=lambda x:x["vr"],reverse=True)
        if surge and HAS_PLOTLY:
            sg_df=pd.DataFrame(surge[:15])
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=sg_df["t"],y=sg_df["pct"],mode="markers",
                marker=dict(size=[min(max(vr*6,8),30) for vr in sg_df["vr"]],
                            color=sg_df["vr"],colorscale=[[0,GREEN],[0.5,GOLD],[1,RED]],
                            showscale=True,colorbar=dict(title="Vol Ratio",tickfont=dict(color="#6b7fa0",size=9))),
                text=[f"{t}: {vr:.1f}×" for t,vr in zip(sg_df["t"],sg_df["vr"])],hoverinfo="text+y"))
            fig.add_hline(y=0,line=dict(color="rgba(255,255,255,0.1)",width=1))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=60,t=10,b=0),height=320,
                xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=10)),
                yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a"))
            st.plotly_chart(fig,use_container_width=True)
            st.caption("Bubble size = volume ratio. Color: green=1.5× | amber=2× | red=3×+")
        else: st.info("No significant volume surges right now.")

    with tabs[4]:
        st.markdown(f'<div class="sec-hd">🎯 Composite Opportunity Matrix <span style="background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.35);font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;margin-left:8px;">StockWins Exclusive</span></div>',unsafe_allow_html=True)
        matrix_tickers=["NVDA","TSLA","AMD","AAPL","MSTR","GME","PLTR","META","MSFT","ARM"]
        signal_types=["Momentum","Trend","Volume","Sentiment","Squeeze"]
        max_vals={"Momentum":25,"Trend":20,"MACD":15,"Volume":15,"Sentiment":15,"Squeeze":10}
        matrix_data={}; prog=st.progress(0,"Computing matrix…")
        for i,t in enumerate(matrix_tickers):
            prog.progress((i+1)/len(matrix_tickers),f"Analyzing {t}…")
            df2=yf_ohlcv(t,60); info2=yf_fund(t); sent2=st_sent(t)
            _,bd2,_,_,_=compute_scores(df2,info2,sent2); matrix_data[t]=bd2
        prog.empty()
        if HAS_PLOTLY:
            z=[[matrix_data.get(t,{}).get(sig,0)/max_vals.get(sig,15) for sig in signal_types] for t in matrix_tickers]
            text_z=[[f"{matrix_data.get(t,{}).get(sig,0)}" for sig in signal_types] for t in matrix_tickers]
            fig=go.Figure(go.Heatmap(z=z,x=signal_types,y=matrix_tickers,text=text_z,texttemplate="%{text}",textfont=dict(size=12,color="white"),colorscale=[[0,"#0a1020"],[0.33,"#1a3a00"],[0.66,"#0d5016"],[1,GREEN]],showscale=False,xgap=2,ygap=2))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=350,xaxis=dict(side="top",showgrid=False,color="#6b7fa0",tickfont=dict(size=12)),yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=12)))
            st.plotly_chart(fig,use_container_width=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: WATCHLIST
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
    rows=[]; prog=st.progress(0,"Loading watchlist…")
    for i,t in enumerate(wl):
        prog.progress((i+1)/len(wl))
        q=get_quote(t); df=yf_ohlcv(t,30); info=yf_fund(t); sent=st_sent(t)
        sc,bd,op,risk,_=compute_scores(df,info,sent); rec_lbl,rec_clr,_=get_recommendation(sc,bd,info)
        if q: rows.append({"Ticker":t,"Name":q.get("name","")[:22],"Price":f"${q['price']:,.2f}","Change":f"{q['pct']:+.2f}%","Signal":rec_lbl,"Score":sc,"Risk":risk,"Short Float":f"{(info.get('sf',0) or 0)*100:.1f}%","Sector":info.get("sector","N/A")})
    prog.empty()
    if rows:
        if HAS_PLOTLY and is_premium():
            st.markdown('<div class="sec-hd" style="font-size:13px;margin-bottom:10px;">Score Distribution</div>',unsafe_allow_html=True)
            scores=[r["Score"] for r in rows]; tickers=[r["Ticker"] for r in rows]
            colors=[GREEN if s>=65 else GOLD if s>=40 else RED for s in scores]
            fig=go.Figure(go.Bar(x=tickers,y=scores,marker_color=colors,text=scores,textposition="outside"))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=180,yaxis=dict(range=[0,110],showgrid=False,color="#4a5e7a"),xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=11)))
            st.plotly_chart(fig,use_container_width=True)
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    if st.button("🗑️ Clear Watchlist",key="wl_clear"): st.session_state.watchlist=[]; st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: SCREENER
# ─────────────────────────────────────────────────────────────
def page_screener():
    render_topbar("screener")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">🔍 Advanced Stock Screener</div>',unsafe_allow_html=True)
    if not is_premium():
        render_lock("Advanced Stock Screener")
        st.markdown('</div>',unsafe_allow_html=True); return
    with st.expander("⚙️ Screener Filters",expanded=True):
        c1,c2,c3,c4=st.columns(4)
        with c1: min_sc=st.slider("Min SW Score",0,100,40); min_rsi=st.slider("Min RSI",0,100,20)
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
            st.session_state.saved_screeners.append({"name":scr_name,"cats":sel_cats,"min_sc":min_sc})
            st.success("Saved!")
    if st.button("🔍 Run Screener",key="scr_run",type="primary",use_container_width=True):
        hot_list=st_hot() if req_hot else []
        universe=list(set([t for c in sel_cats for t in CATEGORIES.get(c,[])]))[:30]
        results=[]; prog=st.progress(0,"Screening…")
        for i,t in enumerate(universe):
            prog.progress((i+1)/len(universe))
            if req_hot and t not in hot_list: continue
            q=get_quote(t); df=yf_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            sc,bd,op,risk,_=compute_scores(df,info,sent); rec_lbl,rec_clr,_=get_recommendation(sc,bd,info)
            if df is None or len(df)<20: continue
            try:
                rsi=ta.momentum.RSIIndicator(df["close"].copy(),14).rsi().iloc[-1]
                ma20=df["close"].rolling(20).mean().iloc[-1]
                mac_ind=ta.trend.MACD(df["close"].copy()); mv=mac_ind.macd().iloc[-1]; ms=mac_ind.macd_signal().iloc[-1]
                price=df["close"].iloc[-1]; avg_v=df["volume"].rolling(20).mean().iloc[-1]; cur_v=df["volume"].iloc[-1]
                sf=(info.get("sf",0) or 0)*100
                if sc<min_sc or sf<min_sf: continue
                if pd.notna(rsi) and (rsi<min_rsi or rsi>max_rsi): continue
                if req_bull and pd.notna(mv) and mv<ms: continue
                if req_above and pd.notna(ma20) and price<ma20: continue
                if req_vol and pd.notna(avg_v) and avg_v>0 and cur_v<avg_v*1.5: continue
                results.append({"Ticker":t,"Price":f"${price:,.2f}","Signal":rec_lbl,"RSI":round(rsi,1) if pd.notna(rsi) else "N/A","Score":sc,"Risk":risk,"Short Float":f"{sf:.1f}%","MACD":"Bullish" if (pd.notna(mv) and mv>ms) else "Bearish","vs MA20":"Above" if price>ma20 else "Below","Vol Ratio":f"{cur_v/avg_v:.1f}×" if pd.notna(avg_v) and avg_v>0 else "N/A"})
            except: continue
        prog.empty()
        if results:
            st.success(f"✅ {len(results)} stocks passed your filters!")
            st.dataframe(pd.DataFrame(results).sort_values("Score",ascending=False),use_container_width=True,hide_index=True)
        else: st.info("No matches. Try relaxing filters.")
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: PRICING
# ─────────────────────────────────────────────────────────────
def page_pricing():
    render_topbar("pricing")
    st.markdown('<div class="pg">', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="text-align:center;padding:32px 0 28px;">
        <div style="font-size:11px;font-weight:700;color:{BLUE};letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">Simple, Transparent Pricing</div>
        <div style="font-size:34px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Choose Your Plan</div>
        <div style="font-size:14px;color:#374f6e;">No hidden fees. No API keys. Cancel anytime.</div>
    </div>
    """, unsafe_allow_html=True)

    import streamlit.components.v1 as components

    pricing_html = (
        '<style>'
        'body{margin:0;padding:0;font-family:Inter,sans-serif;background:transparent;}'
        '.pw{display:flex;gap:16px;align-items:stretch;}'
        '.pc{'
        '  background:#0d1525;border:1px solid rgba(255,255,255,0.1);'
        '  border-radius:14px;padding:24px 20px 0;flex:1;cursor:pointer;'
        '  transition:all 0.3s cubic-bezier(0.4,0,0.2,1);'
        '  display:flex;flex-direction:column;box-sizing:border-box;'
        '}'
        '.pc:hover{border-color:rgba(37,99,235,0.4);transform:translateY(-3px);}'
        '.sel-blue{'
        '  border:2px solid #2563eb!important;'
        '  background:linear-gradient(160deg,#04091d,#0d1525)!important;'
        '  box-shadow:0 12px 48px rgba(37,99,235,0.35)!important;'
        '  transform:translateY(-6px) scale(1.02)!important;'
        '  flex:1.08!important;'
        '}'
        '.sel-gold{'
        '  border:2px solid #f59e0b!important;'
        '  background:linear-gradient(160deg,#160c00,#0f0800,#0d1525)!important;'
        '  box-shadow:0 12px 48px rgba(245,158,11,0.35)!important;'
        '  transform:translateY(-6px) scale(1.02)!important;'
        '  flex:1.08!important;'
        '}'
        '.badge{font-size:9px;font-weight:700;padding:3px 10px;border-radius:20px;'
        '  display:inline-block;letter-spacing:1px;margin-bottom:10px;}'
        '.plan-name{font-size:14px;font-weight:600;margin-bottom:2px;}'
        '.price{font-family:monospace;font-size:46px;font-weight:800;line-height:1.1;margin-bottom:2px;}'
        '.period{font-size:11px;color:#374f6e;margin-bottom:14px;}'
        'hr.card-hr{border:none;border-top:1px solid rgba(255,255,255,0.07);margin:10px 0 14px;}'
        'hr.gold-hr{border:none;border-top:1px solid rgba(245,158,11,0.15);margin:10px 0 14px;}'
        '.feats{flex:1;font-size:12px;color:#374f6e;line-height:2.3;margin-bottom:0;}'
        '.dim{color:#1e3050;}'
        '.cta{'
        '  width:100%;padding:14px 0;border:none;cursor:pointer;font-size:14px;font-weight:700;'
        '  letter-spacing:0.2px;transition:all 0.2s;margin-top:16px;'
        '  border-radius:0 0 12px 12px;'
        '}'
        '.cta-blue{background:#2563eb;color:#fff;}'
        '.cta-blue:hover{background:#1d4ed8;box-shadow:0 4px 20px rgba(37,99,235,0.5);}'
        '.cta-dim{background:rgba(255,255,255,0.04);color:#4a5e7a;border-top:1px solid rgba(255,255,255,0.07)!important;}'
        '.cta-dim:hover{background:rgba(37,99,235,0.1);color:#93b4fd;}'
        '.cta-gold{background:linear-gradient(135deg,#92400e,#d97706,#f59e0b,#fcd34d);color:#1a0800;}'
        '.cta-gold:hover{box-shadow:0 6px 28px rgba(245,158,11,0.55);}'
        '.toast{'
        '  display:none;margin-top:14px;padding:11px 16px;border-radius:8px;'
        '  font-size:12px;line-height:1.6;'
        '  background:rgba(37,99,235,0.12);border:1px solid rgba(37,99,235,0.3);color:#93b4fd;'
        '}'
        '</style>'
        '<div class="pw">'

        # ── FREE ──
        '<div class="pc" id="c-free" onclick="sel(\'free\')">'
        '<span id="b-free" class="badge" style="background:rgba(255,255,255,0.06);color:#4a5e7a;">Free Plan</span>'
        '<div class="plan-name" style="color:#94a3b8;">Free</div>'
        '<div class="price" style="color:#e2e8f0;">$0</div>'
        '<div class="period">forever · no card needed</div>'
        '<hr class="card-hr">'
        '<div class="feats">'
        '✅&nbsp; Market overview &amp; indexes<br>'
        '✅&nbsp; 5 standard categories<br>'
        '✅&nbsp; StockTwits trending list<br>'
        '✅&nbsp; RSI &amp; MACD signals<br>'
        '✅&nbsp; Plain-English insights<br>'
        '✅&nbsp; 7 composite categories<br>'
        '✅&nbsp; Watchlist (10 stocks)<br>'
        '✅&nbsp; BUY / AVOID signals<br>'
        '<span class="dim">'
        '❌&nbsp; 10 premium categories<br>'
        '❌&nbsp; Short squeeze scanner<br>'
        '❌&nbsp; Advanced screener<br>'
        '❌&nbsp; BI analytics charts<br>'
        '❌&nbsp; Score breakdowns'
        '</span>'
        '</div>'
        '<button class="cta cta-dim" id="cta-free" onclick="go(event,\'free\')">Get Started Free</button>'
        '</div>'

        # ── PREMIUM ──
        '<div class="pc sel-blue" id="c-premium" onclick="sel(\'premium\')">'
        '<span id="b-premium" class="badge" style="background:#1e3a8a;color:#93b4fd;">✓ SELECTED</span>'
        '<div class="plan-name" style="color:#e2e8f0;">Premium Monthly</div>'
        '<div class="price" style="color:#e2e8f0;">$29</div>'
        '<div class="period">per month · cancel anytime</div>'
        '<hr class="card-hr">'
        '<div class="feats">'
        '✅&nbsp; Everything in Free<br>'
        '✅&nbsp; All 17 composite categories<br>'
        '✅&nbsp; Short squeeze scanner<br>'
        '✅&nbsp; Advanced screener<br>'
        '✅&nbsp; Full BI analytics &amp; charts<br>'
        '✅&nbsp; Score breakdowns<br>'
        '✅&nbsp; Volume surge detection<br>'
        '✅&nbsp; Unlimited watchlist<br>'
        '✅&nbsp; Watchlist score analytics<br>'
        '✅&nbsp; Saved screener configs'
        '</div>'
        '<button class="cta cta-blue" id="cta-premium" onclick="go(event,\'premium\')">🚀 Get Premium →</button>'
        '</div>'

        # ── ANNUAL ──
        '<div class="pc" id="c-annual" onclick="sel(\'annual\')">'
        '<span id="b-annual" class="badge" style="background:linear-gradient(90deg,#92400e,#d97706);color:#fff8e1;">👑 BEST VALUE — SAVE 43%</span>'
        '<div class="plan-name" style="color:#e2e8f0;">Annual Plan</div>'
        '<div class="price" style="color:#f59e0b;">$199</div>'
        '<div class="period">per year · $16.58/mo · save $149</div>'
        '<hr class="gold-hr">'
        '<div class="feats">'
        '✅&nbsp; Everything in Premium<br>'
        '✅&nbsp; Priority support<br>'
        '✅&nbsp; Early feature access<br>'
        '✅&nbsp; Export to CSV<br>'
        '✅&nbsp; Custom alert schedules<br>'
        '✅&nbsp; API access (Q3 2026)<br>'
        '✅&nbsp; Backtesting (coming)<br>'
        '✅&nbsp; Portfolio tracker (coming)'
        '</div>'
        '<button class="cta cta-dim" id="cta-annual" onclick="go(event,\'annual\')">👑 Select Annual Plan</button>'
        '</div>'

        '</div>'
        '<div class="toast" id="toast"></div>'
        '<script>'
        'var cur="premium";'
        'function sel(p){'
        '  cur=p;'
        '  var plans=["free","premium","annual"];'
        '  plans.forEach(function(x){'
        '    var card=document.getElementById("c-"+x);'
        '    var badge=document.getElementById("b-"+x);'
        '    var cta=document.getElementById("cta-"+x);'
        '    var isS=(x===p);'
        '    if(x==="free"){'
        '      card.className="pc"+(isS?" sel-blue":"");'
        '      badge.textContent=isS?"✓ SELECTED":"Free Plan";'
        '      badge.style.cssText=isS?"background:#1e3a8a;color:#93b4fd;":"background:rgba(255,255,255,0.06);color:#4a5e7a;";'
        '      cta.className="cta "+(isS?"cta-blue":"cta-dim");'
        '      cta.textContent=isS?"Get Started Free →":"Get Started Free";'
        '    } else if(x==="premium"){'
        '      card.className="pc"+(isS?" sel-blue":"");'
        '      badge.textContent=isS?"✓ SELECTED":"⭐ MOST POPULAR";'
        '      badge.style.cssText=isS?"background:#1e3a8a;color:#93b4fd;":"background:rgba(37,99,235,0.18);color:#60a5fa;";'
        '      cta.className="cta "+(isS?"cta-blue":"cta-dim");'
        '      cta.textContent=isS?"🚀 Get Premium →":"🚀 Select Premium";'
        '    } else {'
        '      card.className="pc"+(isS?" sel-gold":"");'
        '      badge.textContent=isS?"✓ SELECTED":"👑 BEST VALUE — SAVE 43%";'
        '      badge.style.cssText=isS?"background:rgba(245,158,11,0.2);color:#f59e0b;":"background:linear-gradient(90deg,#92400e,#d97706);color:#fff8e1;";'
        '      cta.className="cta "+(isS?"cta-gold":"cta-dim");'
        '      cta.textContent=isS?"👑 Get Annual — Best Value →":"👑 Select Annual Plan";'
        '    }'
        '  });'
        '}'
        'function go(e,p){'
        '  e.stopPropagation();'
        '  if(cur!==p){sel(p);return;}'
        '  var t=document.getElementById("toast");'
        '  t.textContent=p==="free"'
        '    ?"✅ Use the Sign Up button in the nav to create your free account!"'
        '    :"💳 Payment coming soon! Email support@stockwins.com to upgrade now.";'
        '  t.style.display="block";'
        '  setTimeout(function(){t.style.display="none";},5000);'
        '}'
        '</script>'
    )

    components.html(pricing_html, height=660)

    st.markdown('<div class="disc" style="margin-top:16px;">⚠️ Educational platform only. Not financial advice. Trading involves risk.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# PAGE: SETTINGS
# ─────────────────────────────────────────────────────────────
def page_settings():
    render_topbar()
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">⚙️ Account Settings</div>',unsafe_allow_html=True)
    db_user=st.session_state.users_db.get(st.session_state.user["email"],{}) if is_authed() else {}
    email=st.session_state.user["email"] if is_authed() else ""

    tabs=st.tabs(["👤 Profile","🔐 Security","🔔 Alerts","📧 Email Digest","📊 Subscription"])

    with tabs[0]:
        with st.form("pf"):
            nn=st.text_input("Display Name",value=st.session_state.user.get("name",""))
            st.text_input("Email",value=email,disabled=True,label_visibility="visible")
            if db_user.get("verified"): st.markdown(f'<div style="font-size:12px;color:{GREEN};margin:4px 0;">✅ Email verified</div>',unsafe_allow_html=True)
            if st.form_submit_button("Save Changes",type="primary") and nn:
                st.session_state.user["name"]=nn
                if email in st.session_state.users_db: st.session_state.users_db[email]["name"]=nn
                st.success("✅ Updated!")

    with tabs[1]:
        st.markdown(f'<div class="card card-blue"><div style="font-size:12px;font-weight:700;color:#f87171;margin-bottom:4px;">🔒 Security Notice</div><div style="font-size:12px;color:#374f6e;line-height:1.6;">For production: Set admin/owner credentials in Streamlit Cloud Secrets. Your session data is not persisted between deployments.</div></div>',unsafe_allow_html=True)
        with st.form("pwf"):
            cp=st.text_input("Current Password",type="password",label_visibility="visible")
            np_=st.text_input("New Password",type="password",label_visibility="visible")
            np2=st.text_input("Confirm New",type="password",label_visibility="visible")
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
            with ac1: at=st.text_input("Ticker",placeholder="AAPL",label_visibility="visible").upper()
            with ac2: ap=st.number_input("Price",value=100.0,min_value=0.01,label_visibility="visible")
            with ac3: atype=st.selectbox("Type",["Price Above","Price Below"],label_visibility="visible")
            if st.form_submit_button("➕ Add Alert",type="primary") and at:
                alerts.append({"ticker":at,"price":ap,"type":atype,"active":True}); st.session_state.alerts=alerts; st.success("Alert set!")
        for i,a in enumerate(alerts):
            ac1,ac2=st.columns([4,1])
            with ac1: st.markdown(f'<div class="card" style="padding:10px 14px;margin-bottom:4px;"><span style="font-family:\'JetBrains Mono\',monospace;color:#60a5fa;font-weight:700;">{a["ticker"]}</span> <span style="font-size:12px;color:#374f6e;">{a["type"]} ${a["price"]:.2f}</span></div>',unsafe_allow_html=True)
            with ac2:
                if st.button("🗑",key=f"da_{i}"): alerts.pop(i); st.session_state.alerts=alerts; st.rerun()
        if not alerts: st.caption("No active alerts.")

    with tabs[3]:
        st.markdown('<div class="sec-hd" style="font-size:13px;">📧 Email Digest Settings</div>',unsafe_allow_html=True)
        if not is_premium():
            st.markdown(f'<div class="card card-gold"><div style="font-size:13px;font-weight:700;color:{GOLD};margin-bottom:6px;">👑 Premium Feature</div><div style="font-size:13px;color:#374f6e;">Email digests require a Premium subscription. Upgrade to receive daily or weekly summaries of your watchlist signals and new BUY opportunities.</div></div>',unsafe_allow_html=True)
            if gold_btn("Upgrade to Enable Email Digest","set_digest_up"): nav("pricing")
        else:
            enabled=st.toggle("Enable email digest",value=st.session_state.get("email_digest_enabled",False))
            st.session_state.email_digest_enabled=enabled
            if enabled:
                freq=st.selectbox("Frequency",["Daily (7am ET)","Weekly (Monday 7am ET)","Real-time Alerts"])
                st.session_state.digest_frequency=freq
                st.text_input("Send to",value=email,disabled=True,label_visibility="visible")
                st.markdown('<div style="font-size:12px;color:#374f6e;margin-top:8px;line-height:1.7;">Digest includes: Top BUY signals from your watchlist · New composite category hits · Volume surge alerts · Squeeze setup notifications<br><span style="color:#2a3a52;">(Email delivery requires backend integration — currently simulated)</span></div>',unsafe_allow_html=True)
                if st.button("Save Digest Settings",type="primary"): st.success("✅ Digest preferences saved!")

    with tabs[4]:
        role=st.session_state.get("role","free")
        rl={"free":"Free","premium":"Premium Monthly","admin":"Admin","owner":"Owner"}.get(role,"Free")
        rc_={"free":"#6b7fa0","premium":"#a78bfa","admin":"#93b4fd","owner":GOLD}.get(role,"#6b7fa0")
        st.markdown(f"""<div class="card card-blue"><div style="font-size:15px;font-weight:800;color:#e2e8f0;">Current Plan: <span style="color:{rc_};">{rl}</span></div>
        <div style="font-size:12px;color:#374f6e;margin-top:4px;">Member since {db_user.get('joined','N/A')}</div>
        <div style="font-size:12px;color:#374f6e;margin-top:2px;">Billing: {db_user.get('plan','Free')}</div></div>""",unsafe_allow_html=True)
        if not is_premium():
            if gold_btn("Upgrade to Premium","set_prem"): nav("pricing")
        else:
            st.markdown(f'<div style="font-size:12px;color:#374f6e;margin-top:10px;padding:10px 14px;background:#080b14;border:1px solid {BORDER};border-radius:7px;">To cancel or modify your subscription, contact <span style="color:#93b4fd;">support@stockwins.com</span></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: ADMIN
# ─────────────────────────────────────────────────────────────
def page_admin():
    if not is_admin(): st.error("Access denied."); return
    render_topbar("admin")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">🛠️ Admin Panel</div>',unsafe_allow_html=True)

    # Security checklist
    st.markdown(f"""<div class="card" style="border-left:3px solid {RED};margin-bottom:16px;">
        <div style="font-size:13px;font-weight:700;color:#f87171;margin-bottom:6px;">🔒 Production Security Checklist</div>
        <div style="font-size:12px;color:#374f6e;line-height:1.9;">
        ✅ Set <code style="background:#1a0000;color:#f87171;padding:1px 5px;border-radius:3px;">TWELVE_DATA_API_KEY</code> in Streamlit Cloud → Settings → Secrets<br>
        ✅ Set <code style="background:#1a0000;color:#f87171;padding:1px 5px;border-radius:3px;">owner_email</code> and <code style="background:#1a0000;color:#f87171;padding:1px 5px;border-radius:3px;">owner_pw_hash</code> in Secrets<br>
        ✅ Never commit real passwords to GitHub<br>
        ✅ Change demo account passwords before public launch
        </div></div>""",unsafe_allow_html=True)

    tabs=st.tabs(["📊 Overview","👥 Users","🔑 API & Secrets","📈 Analytics","🔧 Site Config"])

    with tabs[0]:
        ss=st.session_state.site_stats
        oc=st.columns(5)
        for col,(v,l,c) in zip(oc,[(ss["total_signups"],"Signups","#93b4fd"),(ss["premium_users"],"Premium","#a78bfa"),(ss["daily_active"],"Daily Active",GREEN),(f"{ss['conversion']:.1f}%","Conversion",GOLD),(len(st.session_state.users_db),"Total Accounts","#94a3b8")]):
            col.markdown(f'<div class="stat"><div class="stat-v" style="color:{c};">{v}</div><div class="stat-l">{l}</div></div>',unsafe_allow_html=True)
        st.markdown("<br>",unsafe_allow_html=True)
        hc=st.columns(3)
        key_set=bool(get_td_key())
        for col,(name,status,note) in zip(hc,[("Yahoo Finance","✅ Active","Free · No key needed"),("StockTwits","✅ Active","Public API · Free"),("Twelve Data",f"{'✅ Configured' if key_set else '⚠️ Not Set'}","Optional · Premium quality")]):
            c_=GREEN if "✅" in status else GOLD
            col.markdown(f'<div class="card"><div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:4px;">{name}</div><div style="font-size:12px;font-weight:700;color:{c_};">{status}</div><div style="font-size:11px;color:#2a3a52;margin-top:3px;">{note}</div></div>',unsafe_allow_html=True)

    with tabs[1]:
        for email,u in list(st.session_state.users_db.items()):
            uc1,uc2,uc3,uc4=st.columns([3,1,2,1])
            with uc1:
                v_icon="✅" if u.get("verified") else "⚠️"
                st.markdown(f'<div style="padding:8px 0;"><div style="font-size:13px;font-weight:600;color:#e2e8f0;">{u["name"]}</div><div style="font-size:11px;color:#2a3a52;">{v_icon} {email}</div></div>',unsafe_allow_html=True)
            with uc2:
                rc_={"owner":GOLD,"admin":"#93b4fd","premium":"#a78bfa","free":"#4a5e7a"}.get(u["role"],"#4a5e7a")
                st.markdown(f'<div style="padding:10px 0;"><span style="font-size:10px;font-weight:700;color:{rc_};">{u["role"].upper()}</span></div>',unsafe_allow_html=True)
            with uc3:
                if is_owner() and u["role"]!="owner":
                    nr=st.selectbox("",["free","premium","admin"],index=["free","premium","admin"].index(u["role"]) if u["role"] in ["free","premium","admin"] else 0,key=f"role_{email}",label_visibility="collapsed")
                    if st.button("Update",key=f"upd_{email}",use_container_width=True):
                        st.session_state.users_db[email]["role"]=nr; st.rerun()
            with uc4:
                if is_owner() and email!=st.session_state.user.get("email",""):
                    if st.button("🗑",key=f"del_{email}",use_container_width=True):
                        del st.session_state.users_db[email]; st.rerun()
            st.markdown(f'<div style="border-bottom:1px solid rgba(255,255,255,.04);margin-bottom:4px;"></div>',unsafe_allow_html=True)

    with tabs[2]:
        st.markdown(f"""<div class="card card-blue">
            <div style="font-size:13px;font-weight:700;color:#93b4fd;margin-bottom:8px;">Streamlit Cloud Secrets Setup</div>
            <div style="font-size:12px;color:#374f6e;line-height:1.9;">Go to Streamlit Cloud → your app → <strong style="color:#e2e8f0;">Settings → Secrets</strong> and add:</div>
            <pre style="background:#060a12;border:1px solid {BORDER};border-radius:7px;padding:12px;font-size:11px;color:#4ade80;margin-top:10px;overflow-x:auto;">TWELVE_DATA_API_KEY = "your_key_here"\nowner_email = "your@email.com"\nowner_pw_hash = "sha256_hash_here"\nadmin_email = "admin@email.com"\nadmin_pw_hash = "sha256_hash_here"</pre>
            <div style="font-size:11px;color:#374f6e;margin-top:8px;">Generate hash: <code style="background:#060a12;color:#93b4fd;padding:2px 6px;border-radius:3px;">python3 -c "import hashlib; print(hashlib.sha256(b'YourPassword').hexdigest())"</code></div>
        </div>""",unsafe_allow_html=True)

        # Recommended APIs
        st.markdown('<div class="sec-hd" style="font-size:13px;margin-top:16px;">Recommended APIs to Add</div>',unsafe_allow_html=True)
        api_recs=[
            ("Polygon.io","Real-time options flow, unusual options activity, WebSocket streaming. Best for detecting institutional moves before they hit price.",GREEN),
            ("Alpha Vantage","Earnings dates, economic indicators, forex/crypto. Free tier. Great for earnings calendar integration.",BLUE),
            ("Unusual Whales","Premium options flow — whale trades, dark pool prints. Best signal for big money moves.",GOLD),
            ("FRED API","Free. Interest rates, inflation, economic data. Adds macro context to market signals.",GOLD),
            ("Benzinga","News sentiment and earnings headlines. Lets you surface news-driven moves automatically.","#f97316"),
            ("Finviz","Screener data, insider trading, analyst ratings. Elite API has sector maps and breadth data.","#60a5fa"),
        ]
        cols=st.columns(3,gap="small")
        for i,(name,desc,color) in enumerate(api_recs):
            with cols[i%3]:
                st.markdown(f'<div class="card" style="border-left:3px solid {color};min-height:90px;"><div style="font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:4px;">{name}</div><div style="font-size:11px;color:#374f6e;line-height:1.6;">{desc}</div></div>',unsafe_allow_html=True)

        if is_admin():
            st.markdown('<div class="sec-hd" style="font-size:13px;margin-top:16px;">Session API Key Override</div>',unsafe_allow_html=True)
            with st.form("api_f"):
                nk=st.text_input("Twelve Data API Key",type="password",placeholder="Session only — use Secrets for production",label_visibility="visible")
                if st.form_submit_button("Save for Session",type="primary"):
                    st.session_state._admin_td_key=nk; st.success("✅ Session key saved.")
            if st.button("Clear Key",key="clr_api"): st.session_state._admin_td_key=""; st.success("Cleared.")

    with tabs[3]:
        st.markdown('<div class="sec-hd" style="font-size:13px;">Site Analytics (Simulated)</div>',unsafe_allow_html=True)
        if HAS_PLOTLY:
            dates=pd.date_range(end=datetime.now(),periods=30,freq='D')
            su=[random.randint(45,130) for _ in range(30)]; pu=[random.randint(6,28) for _ in range(30)]
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=list(dates),y=su,name="New Signups",line=dict(color=BLUE,width=2),fill="tozeroy",fillcolor="rgba(37,99,235,0.08)"))
            fig.add_trace(go.Scatter(x=list(dates),y=pu,name="Premium Upgrades",line=dict(color=GOLD,width=2)))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=0,b=0),height=260,legend=dict(bgcolor="rgba(0,0,0,0)",font=dict(color="#6b7fa0",size=11)),xaxis=dict(showgrid=False,color="#4a5e7a"),yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a"))
            st.plotly_chart(fig,use_container_width=True)
        st.markdown('<div class="disc">📊 Connect Mixpanel, PostHog, or similar for real analytics.</div>',unsafe_allow_html=True)

    with tabs[4]:
        st.markdown('<div class="sec-hd" style="font-size:13px;">Ranking & Display Controls</div>',unsafe_allow_html=True)
        rc1,rc2=st.columns(2,gap="small")
        with rc1:
            sort_by=st.selectbox("Default sort order",["SW Score","% Change Today","Volume Ratio","Short Float","Social Sentiment"],key="ranking_sort_ctrl")
            st.session_state.ranking_sort=sort_by
        with rc2:
            filter_by=st.selectbox("Default category filter",["All","Free Only","Premium Only","Composite Only"],key="ranking_filter_ctrl")
            st.session_state.ranking_filter=filter_by
        if st.button("Save Ranking Controls",type="primary"): st.success("✅ Saved!")
        st.markdown('<div class="sec-hd" style="font-size:13px;margin-top:16px;">Billing & Subscription</div>',unsafe_allow_html=True)
        st.markdown('<div class="card"><div style="font-size:12px;color:#374f6e;line-height:1.9;">Billing integration requires Stripe or LemonSqueezy. To implement:<br>1. Add Stripe secret key to Streamlit Secrets<br>2. Create webhook endpoint for subscription events<br>3. Map Stripe customer IDs to user emails<br>4. Auto-promote/demote roles on payment success/failure<br><span style="color:#2a3a52;">(Currently: manual role promotion via Users tab)</span></div></div>',unsafe_allow_html=True)

    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────
render_sidebar()

page=st.session_state.get("page","landing")
guard={"dashboard","discover","watchlist","screener","bi_dashboard","stock_detail","settings","admin"}

if page in guard and not is_authed():
    page_login()
elif page=="landing":      page_landing()
elif page=="features":     page_features()
elif page=="login":        page_login()
elif page=="signup":       page_signup()
elif page=="forgot_pw":    page_forgot()
elif page=="pricing":      page_pricing()
elif page=="dashboard":    page_dashboard()
elif page=="discover":     page_discover()
elif page=="watchlist":    page_watchlist()
elif page=="screener":     page_screener()
elif page=="bi_dashboard": page_bi()
elif page=="stock_detail": page_detail()
elif page=="settings":     page_settings()
elif page=="admin":
    if is_admin(): page_admin()
    else: st.error("Access denied."); nav("dashboard")
else: page_landing()
