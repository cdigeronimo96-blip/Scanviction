# ═══════════════════════════════════════════════════════════════════════
# STOCKWINS v4.0 — Premium Stock Intelligence Platform
# Fixed: All button crashes, navigation, composite categories, BI tools
# ═══════════════════════════════════════════════════════════════════════

import streamlit as st
import requests
import pandas as pd
import ta
import yfinance as yf
import hashlib
import time
import random
from datetime import datetime, timedelta

st.set_page_config(
    page_title="StockWins | Spot Market Opportunities",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap');

html,body,[data-testid="stAppViewContainer"]{
    background:#060a12 !important;color:#c9d3e0 !important;
    font-family:'Inter',sans-serif !important;
}
[data-testid="stHeader"]{display:none !important;}
#MainMenu,footer,[data-testid="stDecoration"]{display:none !important;}
div.block-container{padding:0 !important;max-width:100% !important;}
[data-testid="stVerticalBlock"]{gap:0 !important;}

[data-testid="stSidebar"]{
    background:#080d18 !important;border-right:1px solid #111c2e !important;
    min-width:210px !important;max-width:210px !important;
}
[data-testid="stSidebar"]>div{padding:0 !important;}

/* All buttons */
.stButton>button{
    background:#0e1525 !important;border:1px solid #1a2840 !important;
    color:#7a8fa8 !important;border-radius:6px !important;
    font-family:'Inter',sans-serif !important;font-size:13px !important;
    font-weight:500 !important;padding:7px 14px !important;
    transition:all 0.15s !important;width:100%;min-height:36px;
}
.stButton>button:hover{
    border-color:#2563eb !important;color:#60a5fa !important;
    background:#0f1d35 !important;
}
.stButton>button[kind="primary"]{
    background:linear-gradient(135deg,#2563eb,#1d4ed8) !important;
    border-color:#2563eb !important;color:#fff !important;font-weight:700 !important;
}
.stButton>button[kind="primary"]:hover{
    background:linear-gradient(135deg,#3b82f6,#2563eb) !important;
}
/* Sidebar nav buttons — styled to look like nav items */
[data-testid="stSidebar"] .stButton>button{
    background:transparent !important;border:none !important;
    border-radius:0 !important;border-left:2px solid transparent !important;
    color:#506070 !important;font-size:13px !important;font-weight:500 !important;
    padding:9px 16px !important;text-align:left !important;
    width:100% !important;margin:0 !important;
}
[data-testid="stSidebar"] .stButton>button:hover{
    background:#0e1525 !important;color:#c9d3e0 !important;
    border-left-color:#2563eb !important;border-top:none !important;
    border-right:none !important;border-bottom:none !important;
}

/* Inputs */
.stTextInput>div>div>input,.stTextArea>div>div>textarea,
.stSelectbox>div>div,.stNumberInput>div>div>input{
    background:#0e1525 !important;border:1px solid #1a2840 !important;
    color:#c9d3e0 !important;border-radius:6px !important;
    font-family:'Inter',sans-serif !important;font-size:13px !important;
}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus{
    border-color:#2563eb !important;box-shadow:0 0 0 2px rgba(37,99,235,.15) !important;
}
.stMultiSelect>div{background:#0e1525 !important;border-color:#1a2840 !important;}
[data-testid="stCheckbox"]>label{color:#7a8fa8 !important;font-size:13px !important;}
[data-testid="stRadio"]>div>label{color:#7a8fa8 !important;font-size:13px !important;}
.stSlider>div{color:#4a6080 !important;}
.stProgress>div>div{background:#111c2e !important;height:4px !important;}
.stProgress>div>div>div{background:#2563eb !important;}
.streamlit-expanderHeader{
    background:#0e1525 !important;border:1px solid #1a2840 !important;
    border-radius:6px !important;color:#7a8fa8 !important;font-size:13px !important;
}
.streamlit-expanderContent{
    background:#0a1020 !important;border:1px solid #1a2840 !important;border-top:none !important;
}
[data-testid="stDataFrame"]{border:1px solid #1a2840 !important;border-radius:8px !important;overflow:hidden;}
[data-testid="stDataFrame"] th{background:#0e1525 !important;color:#4a6080 !important;font-size:11px !important;text-transform:uppercase;}
[data-testid="stDataFrame"] td{background:#080d18 !important;color:#c9d3e0 !important;font-size:13px !important;}
hr{border-color:#111c2e !important;margin:0 !important;}
[data-testid="stTabs"]>div{border-color:#111c2e !important;}
[data-testid="stTab"]{font-size:13px !important;color:#506070 !important;}

/* Custom components */
.sw-logo{font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700;color:#e2e8f0;letter-spacing:-.5px;}
.sw-logo .w{color:#f59e0b;}
.nav-sec{font-size:10px;font-weight:700;color:#1e2d42;letter-spacing:1.5px;text-transform:uppercase;padding:18px 16px 5px;}

.sw-card{background:#0d1525;border:1px solid #111c2e;border-radius:8px;padding:16px;margin-bottom:8px;}
.sw-card:hover{border-color:#1a2840;}
.card-blue{background:linear-gradient(135deg,#060f2e,#0d1525);border-color:#1e3a8a;}
.card-gold{background:linear-gradient(135deg,#120d00,#0d1525);border-color:#854d0e;}
.card-green{background:linear-gradient(135deg,#002010,#0d1525);border-color:#14532d;}
.card-purple{background:linear-gradient(135deg,#0e0620,#0d1525);border-color:#4c1d95;}
.card-teal{background:linear-gradient(135deg,#001e20,#0d1525);border-color:#134e4a;}

.idx{background:#0d1525;border:1px solid #111c2e;border-radius:8px;padding:14px 16px;}
.idx-name{font-size:10px;color:#4a6080;text-transform:uppercase;letter-spacing:.5px;}
.idx-price{font-family:'JetBrains Mono',monospace;font-size:17px;font-weight:700;color:#e2e8f0;margin-top:2px;}

.sr{background:#0d1525;border:1px solid #111c2e;border-radius:8px;padding:12px 16px;margin-bottom:5px;transition:border-color .15s;}
.sr:hover{border-color:#1e3a8a;}
.sr-tick{font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#60a5fa;}
.sr-name{font-size:11px;color:#2a3a50;margin-top:2px;}
.sr-why{font-size:11px;color:#3a5a70;margin-top:3px;font-style:italic;}

.b{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;margin-right:3px;}
.b-bull{background:#052e16;color:#4ade80;border:1px solid #166534;}
.b-bear{background:#1c0000;color:#f87171;border:1px solid #7f1d1d;}
.b-neu{background:#0e1525;color:#64748b;border:1px solid #1e2a3a;}
.b-hot{background:#1c0800;color:#f97316;border:1px solid #92400e;}
.b-prem{background:#1c1000;color:#f59e0b;border:1px solid #854d0e;}
.b-new{background:#06163a;color:#60a5fa;border:1px solid #1e3a8a;}
.b-purple{background:#1a0a30;color:#c084fc;border:1px solid #4c1d95;}
.b-teal{background:#001e20;color:#2dd4bf;border:1px solid #134e4a;}

.sc-pill{display:inline-block;padding:3px 10px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;}
.sc-hi{background:#052e16;color:#4ade80;border:1px solid #166534;}
.sc-md{background:#1c1000;color:#fbbf24;border:1px solid #854d0e;}
.sc-lo{background:#1c0000;color:#f87171;border:1px solid #7f1d1d;}

.ins{background:#0a1020;border-left:2px solid #2563eb;border-radius:0 6px 6px 0;padding:10px 14px;margin:4px 0;}
.ins-bull{border-left-color:#22c55e;}
.ins-bear{border-left-color:#ef4444;}
.ins-label{font-size:12px;font-weight:700;color:#c9d3e0;margin-bottom:4px;}
.ins-text{font-size:12px;color:#3a5068;line-height:1.55;}

.sec{font-size:15px;font-weight:700;color:#c9d3e0;display:flex;align-items:center;gap:8px;padding-bottom:10px;border-bottom:1px solid #111c2e;margin-bottom:12px;}
.sec .cnt{font-size:10px;color:#2563eb;background:#06163a;border:1px solid #1e3a8a;padding:2px 8px;border-radius:20px;margin-left:auto;}

.stat{background:#0d1525;border:1px solid #111c2e;border-radius:8px;padding:12px 14px;text-align:center;}
.stat-v{font-family:'JetBrains Mono',monospace;font-size:19px;font-weight:700;color:#e2e8f0;}
.stat-l{font-size:10px;color:#2a3a50;text-transform:uppercase;letter-spacing:.5px;margin-top:3px;}

.hm{border-radius:5px;padding:7px 3px;text-align:center;font-size:11px;font-weight:700;}
.hm-hi{background:#052e16;color:#4ade80;}
.hm-lo{background:#1c0000;color:#f87171;}
.hm-neu{background:#0e1525;color:#506070;}

.mv{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #0e1525;font-size:13px;}
.mv:last-child{border-bottom:none;}
.lock{background:rgba(6,10,18,.95);border:1px solid #854d0e;border-radius:10px;padding:36px 24px;text-align:center;}
.pc{background:#0d1525;border:1px solid #111c2e;border-radius:10px;padding:28px 22px;}
.pc-feat{background:linear-gradient(160deg,#06163a,#0d1525);border:2px solid #2563eb;border-radius:10px;padding:28px 22px;}
.pc-price{font-family:'JetBrains Mono',monospace;font-size:38px;font-weight:700;color:#e2e8f0;}

.hero-wrap{background:radial-gradient(ellipse at 30% 50%,#061430 0%,#060a12 65%);border-bottom:1px solid #111c2e;padding:60px 48px 48px;display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:center;}
.hero-eyebrow{font-size:11px;font-weight:700;color:#2563eb;letter-spacing:2px;text-transform:uppercase;margin-bottom:14px;}
.hero-h1{font-size:44px;font-weight:900;color:#f1f5f9;line-height:1.1;letter-spacing:-1.5px;margin-bottom:8px;}
.hero-h1 .hi{color:#2563eb;}
.hero-sub{font-size:15px;color:#4a6080;line-height:1.7;margin-bottom:28px;max-width:440px;}
.stats-bar{background:#0a1020;border-bottom:1px solid #111c2e;padding:18px 48px;display:flex;gap:48px;align-items:center;}
.stats-val{font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;color:#e2e8f0;}
.stats-lbl{font-size:11px;color:#2a3a50;margin-top:1px;}
.disc{background:#0a1020;border-left:2px solid #854d0e;border-radius:0 6px 6px 0;padding:12px 16px;font-size:11px;color:#2a3a50;line-height:1.7;margin-top:16px;}
.pg{padding:20px 24px;}

/* Composite category badge colors */
.b-squeeze-buzz{background:#1a0020;color:#f0abfc;border:1px solid #7e22ce;}
.b-vol-break{background:#001a20;color:#67e8f9;border:1px solid #0e7490;}
.b-reversal{background:#1a1200;color:#fcd34d;border:1px solid #b45309;}
.b-hidden{background:#001020;color:#93c5fd;border:1px solid #1d4ed8;}
.b-momentum{background:#001a00;color:#86efac;border:1px solid #16a34a;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# CONSTANTS & CATEGORIES
# ─────────────────────────────────────────────────────────────────────
# Standard categories
CATEGORIES = {
    "🔥 Trending Now":     [],
    "📡 Social Buzz":      ["GME","AMC","BBIG","MULN","FFIE","ATER","SPCE","HOOD","CLOV","MSTR","PLTR","SNDL","BBAI","SOUN","ASTS"],
    "💻 Tech":             ["AAPL","MSFT","GOOGL","META","AMZN","NVDA","AMD","INTC","QCOM","AVGO","CRM","ORCL","ADBE","NOW","SNOW","UBER","SHOP","SQ","PYPL","NET","DDOG","MDB","OKTA","ZS","CRWD"],
    "🤖 AI":               ["NVDA","AMD","PLTR","MSFT","GOOGL","IBM","SOUN","BBAI","AI","ASTS","IONQ","QUBT","RGTI","SMCI","DELL","HPE","ARM","ALAB","MRVL"],
    "⚡ EV":               ["TSLA","RIVN","LCID","NIO","LI","XPEV","F","GM","CHPT","BLNK","ACHR","JOBY"],
    "🧬 Biotech":          ["MRNA","BNTX","NVAX","VRTX","REGN","BIIB","GILD","AMGN","SRPT","EDIT","CRSP","BEAM","NTLA"],
    "📊 S&P 500":          ["AAPL","MSFT","AMZN","GOOGL","META","TSLA","NVDA","JPM","JNJ","V","PG","MA","UNH","HD","XOM","CVX","LLY","ABBV","MRK","PFE","BAC","WMT","KO","DIS"],
    "💹 NASDAQ":           ["AAPL","MSFT","AMZN","NVDA","META","GOOGL","TSLA","AVGO","COST","AMD","CSCO","ADBE","QCOM","AMGN","INTU","ISRG","REGN","VRTX","PANW"],
    "🔬 Small Cap":        ["FFIE","MULN","NKLA","GOEV","WKHS","HCDI","ATER","SPCE","SOUN","BBAI","ASTS","IONQ","QUBT","RGTI","MNMD","ACHR"],
}

# Proprietary composite categories — unique to StockWins
COMPOSITE_CATS = {
    "🔥💥 Squeeze + Buzz":      "High short interest stocks currently trending on StockTwits — social momentum meets squeeze fuel",
    "⚡📈 Volume Breakout":      "Stocks breaking above moving averages on unusually high volume — institutional confirmation signal",
    "🎯 Smart Reversal":         "RSI oversold + bullish MACD crossover + rising sentiment — technical bounce setup forming",
    "💡 Hidden Movers":          "Strong technical scores with low social awareness — early discovery before the crowd arrives",
    "🌊 Momentum Leaders":       "RSI in the sweet spot + above both MAs + bullish MACD — all systems green",
    "🎭 Social Catalyst":        "Stocks spiking in StockTwits chatter + abnormal volume today — catalyst-driven momentum",
}

PREMIUM_CATS  = {"💥 Squeeze Radar"}
ALL_COMPOSITE_FREE = ["🔥💥 Squeeze + Buzz","💡 Hidden Movers","🎭 Social Catalyst"]
ALL_COMPOSITE_PREM = ["⚡📈 Volume Breakout","🎯 Smart Reversal","🌊 Momentum Leaders"]
FREE_CATS     = [c for c in CATEGORIES if c not in PREMIUM_CATS]

SECTOR_ETFS  = {"Technology":"XLK","Healthcare":"XLV","Financials":"XLF","Energy":"XLE",
                "Cons Disc":"XLY","Industrials":"XLI","Materials":"XLB","Utilities":"XLU",
                "Real Estate":"XLRE","Comm Svcs":"XLC"}
INDEXES      = {"NASDAQ":"^IXIC","S&P 500":"^GSPC","DOW":"^DJI","VIX":"^VIX","Russell":"^RUT"}
BROAD_UNIVERSE = list(set(
    ["AAPL","MSFT","NVDA","AMD","TSLA","META","AMZN","GOOGL","PLTR","MSTR",
     "GME","AMC","HOOD","RIVN","MRNA","BNTX","SMCI","ARM","SOUN","ASTS",
     "IONQ","JPM","BAC","XOM","LLY","ABBV","VRTX","CRSP","AVGO","QCOM",
     "IBM","MULN","FFIE","NKLA","SPCE","BBIG","BBAI","QUBT","RGTI","ACHR",
     "NIO","LI","XPEV","LCID","BLNK","CHPT","EDIT","CRSP","BEAM","NTLA"]
))

# ─────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────
def _hp(pw): return hashlib.sha256(pw.encode()).hexdigest()
def init():
    now=datetime.now().strftime("%Y-%m-%d")
    d={
        "page":"landing","user":None,"role":"guest",
        "watchlist":[],"saved_screeners":[],"alerts":[],
        "detail_ticker":None,"detail_data":{},"discover_cat":"💻 Tech",
        "hero_panel":0,"api_override":"",
        "users_db":{
            "owner@stockwins.com":  {"pw":_hp("owner123"), "name":"Owner",      "role":"owner",   "verified":True,"joined":now,"plan":"Annual"},
            "admin@stockwins.com":  {"pw":_hp("admin123"), "name":"Admin",       "role":"admin",   "verified":True,"joined":now,"plan":"Annual"},
            "demo@stockwins.com":   {"pw":_hp("demo123"),  "name":"Demo User",   "role":"free",    "verified":True,"joined":now,"plan":"Free"},
            "premium@stockwins.com":{"pw":_hp("premium1"), "name":"Alex Rivera", "role":"premium", "verified":True,"joined":now,"plan":"Monthly"},
        },
        "site_stats":{
            "total_signups":1847,"premium_users":312,"daily_active":634,
            "conversion_rate":16.9,"top_watchlisted":["NVDA","TSLA","AAPL","AMD","MSTR"],
        },
    }
    for k,v in d.items():
        if k not in st.session_state: st.session_state[k]=v
init()

# ─────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────
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
    db[email]={"pw":hp(pw),"name":name,"role":"free","verified":False,
               "joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Free"}
    st.session_state.site_stats["total_signups"]+=1
    st.session_state.user={"email":email,"name":name}
    st.session_state.role="free"
    return True,"Welcome!"

def logout():
    st.session_state.user=None; st.session_state.role="guest"; nav("landing")

def is_owner():   return st.session_state.role=="owner"
def is_admin():   return st.session_state.role in ("owner","admin")
def is_premium(): return st.session_state.role in ("owner","admin","premium")
def is_authed():  return st.session_state.user is not None
def nav(p):       st.session_state.page=p; st.rerun()
def get_db_user():
    if not is_authed(): return {}
    return st.session_state.users_db.get(st.session_state.user["email"],{})
def get_key():
    try:    return st.secrets.get("TWELVE_DATA_API_KEY","") or st.session_state.api_override
    except: return st.session_state.api_override

# ─────────────────────────────────────────────────────────────────────
# DATA — yfinance primary (free), Twelve Data optional (admin-set)
# ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def yf_quote(ticker):
    try:
        tk=yf.Ticker(ticker)
        h=tk.history(period="2d",interval="1d")
        i=tk.info
        if len(h)<1: return None
        price=round(float(h["Close"].iloc[-1]),2)
        prev=round(float(h["Close"].iloc[-2]),2) if len(h)>=2 else price
        return {"price":price,"prev":prev,"open":round(float(h["Open"].iloc[-1]),2),
                "high":round(float(h["High"].iloc[-1]),2),"low":round(float(h["Low"].iloc[-1]),2),
                "volume":int(h["Volume"].iloc[-1]),
                "pct":round(((price-prev)/prev)*100,2) if prev else 0,
                "chg":round(price-prev,2),
                "name":i.get("shortName",i.get("longName",ticker))[:30]}
    except: return None

@st.cache_data(ttl=600)
def yf_ohlcv(ticker, n=60):
    try:
        h=yf.Ticker(ticker).history(period=f"{min(n+15,130)}d")
        if len(h)<5: return None
        df=h.tail(n).reset_index()
        df.columns=[c.lower() for c in df.columns]
        df=df.rename(columns={"date":"datetime"})
        return df[["datetime","open","high","low","close","volume"]].copy()
    except: return None

@st.cache_data(ttl=3600)
def yf_fund(ticker):
    try:
        i=yf.Ticker(ticker).info
        return {"mktcap":i.get("marketCap",0),"sf":i.get("shortPercentOfFloat",0),
                "dtc":i.get("shortRatio",0),"avgvol":i.get("averageVolume",0),
                "sector":i.get("sector","N/A"),"industry":i.get("industry","N/A"),
                "pe":i.get("trailingPE",None),"hi52":i.get("fiftyTwoWeekHigh",0),
                "lo52":i.get("fiftyTwoWeekLow",0),"beta":i.get("beta",None),
                "desc":(i.get("longBusinessSummary","")[:280]+"...") if i.get("longBusinessSummary") else ""}
    except: return {}

@st.cache_data(ttl=300)
def td_quote(ticker, key):
    if not key: return None
    try:
        d=requests.get(f"https://api.twelvedata.com/quote?symbol={ticker}&apikey={key}",timeout=8).json()
        if "close" not in d: return None
        return {"price":float(d["close"]),"open":float(d.get("open",0)),
                "high":float(d.get("high",0)),"low":float(d.get("low",0)),
                "volume":int(d.get("volume",0)),"prev":float(d.get("previous_close",0)),
                "chg":float(d.get("change",0)),"pct":float(d.get("percent_change",0)),
                "name":d.get("name",ticker)}
    except: return None

def get_quote(ticker):
    key=get_key()
    if key:
        q=td_quote(ticker,key)
        if q: return q
    return yf_quote(ticker)

@st.cache_data(ttl=600)
def td_ohlcv(ticker, key, n=60):
    if not key: return None
    try:
        d=requests.get(f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&outputsize={n}&apikey={key}",timeout=10).json()
        if "values" not in d: return None
        df=pd.DataFrame(d["values"])
        for c in ["open","high","low","close","volume"]: df[c]=df[c].astype(float)
        return df.iloc[::-1].reset_index(drop=True)
    except: return None

def get_ohlcv(ticker, n=60):
    key=get_key()
    if key:
        df=td_ohlcv(ticker,key,n)
        if df is not None: return df
    return yf_ohlcv(ticker,n)

@st.cache_data(ttl=900)
def st_hot():
    try:
        d=requests.get("https://api.stocktwits.com/api/2/trending/symbols.json",timeout=8).json()
        return [s["symbol"] for s in d.get("symbols",[])]
    except: return ["NVDA","TSLA","AAPL","AMD","MSTR","PLTR","META","MSFT","GME","AMC"]

@st.cache_data(ttl=900)
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

@st.cache_data(ttl=300)
def get_indexes():
    out={}
    for n,t in INDEXES.items():
        try:
            h=yf.Ticker(t).history(period="5d")
            if len(h)>=2:
                p=h["Close"].iloc[-1]; pv=h["Close"].iloc[-2]
                trend=[round(float(v),2) for v in h["Close"].tail(5).values]
                out[n]={"price":round(p,2),"pct":round(((p-pv)/pv)*100,2),"trend":trend}
        except: out[n]={"price":0,"pct":0,"trend":[]}
    return out

@st.cache_data(ttl=900)
def get_sectors():
    out={}
    for s,e in SECTOR_ETFS.items():
        try:
            h=yf.Ticker(e).history(period="5d")
            if len(h)>=2: out[s]=round(((h["Close"].iloc[-1]-h["Close"].iloc[-2])/h["Close"].iloc[-2])*100,2)
        except: out[s]=0.0
    return out

@st.cache_data(ttl=600)
def get_bi_movers():
    out=[]
    for t in BROAD_UNIVERSE[:30]:
        try:
            h=yf.Ticker(t).history(period="5d")
            if len(h)>=2:
                p=h["Close"].iloc[-1]; pv=h["Close"].iloc[-2]
                v=h["Volume"].iloc[-1]; av=h["Volume"].mean()
                out.append({"t":t,"price":round(p,2),"pct":round(((p-pv)/pv)*100,2),
                             "vol":int(v),"vr":round(v/av,1) if av>0 else 1})
        except: continue
    return out

# ─────────────────────────────────────────────────────────────────────
# SCORING ENGINE
# ─────────────────────────────────────────────────────────────────────
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
    elif bd.get("Momentum",0)==25:   op="Oversold Bounce"
    elif bd.get("Trend",0)>=18:      op="Uptrend Continuation"
    elif bd.get("Volume",0)>=11:     op="Volume Surge"
    elif bd.get("MACD",0)==15:       op="MACD Breakout"
    else:                            op="Mixed Signals"

    try:
        vol_std=df["close"].pct_change().std()*100
        beta=info.get("beta",1) or 1 if info else 1
        sf=(info.get("sf",0) or 0)*100 if info else 0
        mc=info.get("mktcap",0) or 0 if info else 0
        rs=0
        if beta>2: rs+=3
        elif beta>1.5: rs+=2
        elif beta>1: rs+=1
        if vol_std>4: rs+=3
        elif vol_std>2: rs+=2
        elif vol_std>1: rs+=1
        if sf>20: rs+=2
        elif sf>10: rs+=1
        if mc<500e6: rs+=2
        elif mc<2e9: rs+=1
        risk="Very High" if rs>=6 else "High" if rs>=4 else "Medium" if rs>=2 else "Low"
    except: risk="Unknown"

    conf="High" if sc>=65 else "Medium" if sc>=40 else "Low"
    return sc,bd,op,risk,conf

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
        bb=ta.volatility.BollingerBands(dfc["close"])
        dfc["bb"]=bb.bollinger_pband()
        lat=dfc.iloc[-1]; prev=dfc.iloc[-2]
        rsi=lat["rsi"]; price=lat["close"]

        if pd.notna(rsi):
            if rsi<30:      out.append(("RSI Oversold","The stock has dropped hard and fast. Historically, extreme selloffs like this can lead to a bounce as buyers step in.","bull","Medium"))
            elif rsi>70:    out.append(("RSI Overbought","The stock has surged quickly and is stretched. Sharp rises can face profit-taking — be cautious.","bear","Medium"))
            elif 55<rsi<=70:out.append(("Strong Momentum","Momentum is healthy and moving in the right direction without being dangerously overbought yet.","bull","Medium"))
            else:           out.append(("Neutral Momentum","Neither overbought nor oversold — no extreme pressure in either direction right now.","neu","Low"))

        if pd.notna(lat["ma20"]) and pd.notna(lat["ma50"]):
            if price>lat["ma20"] and price>lat["ma50"]:
                out.append(("Above Key Averages","Trading above both its 20-day and 50-day average prices. Buyers have been consistently in control — a healthy uptrend.","bull","High"))
            elif price<lat["ma20"] and price<lat["ma50"]:
                out.append(("Below Key Averages","Below its recent averages — sellers have been winning. The trend is currently pointing down.","bear","High"))
            if prev["ma20"]<prev["ma50"] and lat["ma20"]>lat["ma50"]:
                out.append(("Golden Cross ✨","A major bullish event: the short-term trend just crossed above the long-term trend. Many traders treat this as a serious buy signal.","bull","High"))
            elif prev["ma20"]>prev["ma50"] and lat["ma20"]<lat["ma50"]:
                out.append(("Death Cross 💀","A serious warning: the short-term trend just crossed below long-term. Often signals a deepening downtrend.","bear","High"))

        if pd.notna(lat["macd"]) and pd.notna(lat["macd_s"]):
            if lat["macd"]>lat["macd_s"] and prev["macd"]<=prev["macd_s"]:
                out.append(("MACD Bullish Crossover","Momentum just flipped positive. Buyers are entering the market — often a good signal for upside continuation.","bull","High"))
            elif lat["macd"]<lat["macd_s"] and prev["macd"]>=prev["macd_s"]:
                out.append(("MACD Bearish Crossover","Momentum turned negative. Selling pressure is building.","bear","High"))
            elif lat["macd"]>0: out.append(("MACD Positive","Overall momentum currently favors buyers.","bull","Medium"))
            else:               out.append(("MACD Negative","Overall momentum currently favors sellers.","bear","Medium"))

        if "volume" in dfc.columns:
            avg=dfc["volume"].rolling(20).mean().iloc[-1]
            if pd.notna(avg) and avg>0:
                r=lat["volume"]/avg
                if r>=2:
                    d_="bull" if lat["close"]>prev["close"] else "bear"
                    out.append(("Volume Spike 🔊",f"Volume is {r:.1f}× above normal. High-volume moves tend to be more reliable and sustained.",d_,"High"))
                elif r<0.5:
                    out.append(("Low Volume Warning","Very low activity today — moves on thin volume can easily reverse.","neu","Low"))

        if info:
            sf=(info.get("sf",0) or 0)*100; dtc=info.get("dtc",0) or 0
            if sf>=20:
                out.append(("High Short Interest 🎯",f"{sf:.1f}% of shares are sold short. If the stock rises, forced buying can accelerate the move (short squeeze).","bull","High"))
            if dtc>=5:
                out.append(("High Days-to-Cover",f"~{dtc:.0f} days of average volume needed to close all shorts. Significant squeeze potential fuel.","bull","Medium"))

        if pd.notna(lat["bb"]):
            if lat["bb"]<0:   out.append(("Near Lower Band","At the bottom of its typical range — historically this can precede a bounce.","bull","Medium"))
            elif lat["bb"]>1: out.append(("Near Upper Band","Stretched to the top of its normal range — may face resistance.","bear","Medium"))
    except: pass
    return out

def why_text(ticker, ig, sc, sent, info):
    sf=(info.get("sf",0) or 0)*100 if info else 0
    if sf>=20 and sc>=50: return f"Short float {sf:.0f}% + rising momentum = squeeze candidate"
    for lbl,_,_,_ in ig:
        if "Golden Cross" in lbl: return "Short-term trend just crossed above long-term — major bullish signal"
        if "Oversold" in lbl:    return "May have dropped too far too fast — bounce setup forming"
        if "Volume Spike" in lbl: return "Unusual trading activity — potential catalyst-driven move"
        if "Bullish Cross" in lbl: return "MACD just turned positive — buyers gaining control"
    bull=sent.get("bull",50) if sent else 50
    if bull>=70: return f"{bull}% of StockTwits traders are bullish right now"
    if sc>=70:   return "Strong multi-factor signal — momentum, trend, and volume align"
    return "Flagged by StockWins composite scoring engine"

def risk_color(r):
    return {"Low":"#22c55e","Low-Medium":"#4ade80","Medium":"#fbbf24",
            "Medium-High":"#fb923c","High":"#ef4444","Very High":"#dc2626"}.get(r,"#64748b")

# ─────────────────────────────────────────────────────────────────────
# COMPOSITE CATEGORY ENGINE
# ─────────────────────────────────────────────────────────────────────
def get_composite_stocks(cat_name, limit=12):
    """
    Run the composite scoring logic to surface unique stock opportunities.
    Each composite category combines 2+ independent signals.
    """
    hot=st_hot()
    universe=list(set(BROAD_UNIVERSE+hot[:8]))[:35]
    results=[]

    prog=st.progress(0,f"Computing {cat_name}...")
    for i,t in enumerate(universe[:limit*2]):
        prog.progress((i+1)/(limit*2),f"Analyzing {t}...")
        try:
            q=get_quote(t)
            df=get_ohlcv(t,60)
            info=yf_fund(t)
            sent=st_sent(t)
            sc,bd,op,risk,conf=compute_scores(df,info,sent)
            ig=get_insights(df,info)
            if not q: continue

            sf=(info.get("sf",0) or 0)*100
            bull=sent.get("bull",50)
            in_hot=t in hot

            # COMPOSITE SCORE based on category type
            if cat_name=="🔥💥 Squeeze + Buzz":
                # Short interest + social trending = explosive combo
                comp=sf*1.5 + (30 if in_hot else 0) + (bull-50)*0.5 + bd.get("Volume",0)
                include = sf>=10 and (in_hot or bull>=60)
                cat_why = f"Short float {sf:.0f}% + {'🔥 trending' if in_hot else f'{bull}% bullish social'}"
                cat_badge = "b-squeeze-buzz"

            elif cat_name=="⚡📈 Volume Breakout":
                # Volume spike + breaking above MA = institutional confirmation
                vol_score=bd.get("Volume",0)
                trend_score=bd.get("Trend",0)
                comp=vol_score*2 + trend_score + bd.get("MACD",0)
                include = vol_score>=7 and trend_score>=12
                cat_why = f"Volume surge + breaking above key averages = confirmed breakout"
                cat_badge = "b-vol-break"

            elif cat_name=="🎯 Smart Reversal":
                # RSI oversold + positive sentiment shift + MACD turning
                mom_score=bd.get("Momentum",0)
                macd_score=bd.get("MACD",0)
                comp=mom_score + macd_score + (bull-50)*0.3 + bd.get("Squeeze",0)
                include = mom_score>=20 and macd_score>=9
                cat_why = f"RSI oversold ({round(mom_score*1.2)}ish) + MACD turning positive = bounce setup"
                cat_badge = "b-reversal"

            elif cat_name=="💡 Hidden Movers":
                # Strong technicals, low social noise = early discovery
                sent_score=bd.get("Sentiment",0)
                wl=sent.get("wl",0)
                comp=sc - sent_score*0.5 - (30 if in_hot else 0) - min(wl/100,20)
                include = sc>=45 and not in_hot and bull<65
                cat_why = f"Strong SW score ({sc}) with low social attention — early discovery signal"
                cat_badge = "b-hidden"

            elif cat_name=="🌊 Momentum Leaders":
                # RSI sweet spot + above both MAs + bullish MACD
                comp=bd.get("Momentum",0) + bd.get("Trend",0) + bd.get("MACD",0) + bull*0.1
                include = (bd.get("Momentum",0)>=12 and bd.get("Trend",0)>=16 and bd.get("MACD",0)>=9)
                cat_why = f"RSI, trend, and MACD all bullish simultaneously — all systems green"
                cat_badge = "b-momentum"

            elif cat_name=="🎭 Social Catalyst":
                # High StockTwits activity + abnormal volume today
                vol_score=bd.get("Volume",0)
                wl=sent.get("wl",0); msgs=sent.get("msgs",0)
                comp=vol_score*1.5 + (50 if in_hot else 0) + bull*0.3 + min(msgs*2,30)
                include = (in_hot or msgs>=5) and vol_score>=4
                cat_why = f"{'🔥 StockTwits trending' if in_hot else f'{msgs} recent posts'} + volume {bd.get('Volume',0)/15*100:.0f}% above avg"
                cat_badge = "b-hot"
            else:
                include=True; comp=sc; cat_why=why_text(t,ig,sc,sent,info); cat_badge="b-new"

            if include:
                results.append({"t":t,"q":q,"sc":sc,"bd":bd,"ig":ig,"op":op,"risk":risk,
                                 "conf":conf,"hot":in_hot,"df":df,"info":info,"sent":sent,
                                 "comp":comp,"cat_why":cat_why,"cat_badge":cat_badge})
        except: continue

    prog.empty()
    results.sort(key=lambda x:x["comp"],reverse=True)
    return results[:limit]

# ─────────────────────────────────────────────────────────────────────
# UI COMPONENTS
# ─────────────────────────────────────────────────────────────────────
def sc_pill(sc):
    cls="sc-hi" if sc>=65 else "sc-md" if sc>=40 else "sc-lo"
    return f'<span class="sc-pill {cls}">{sc}</span>'

def render_ins(label, text, sentiment, confidence):
    cls="ins-bull" if sentiment=="bull" else "ins-bear" if sentiment=="bear" else ""
    bc="b-bull" if sentiment=="bull" else "b-bear" if sentiment=="bear" else "b-neu"
    bl="Bullish" if sentiment=="bull" else "Bearish" if sentiment=="bear" else "Neutral"
    st.markdown(f"""<div class="ins {cls}">
        <div class="ins-label">{label} <span class="b {bc}">{bl}</span>
            <span style="font-size:10px;color:#2a3a50;margin-left:4px;">· {confidence} confidence</span>
        </div>
        <div class="ins-text">{text}</div>
    </div>""", unsafe_allow_html=True)

def render_lock(name="This Feature"):
    st.markdown(f"""<div class="lock">
        <div style="font-size:28px;margin-bottom:10px;">🔒</div>
        <div style="font-size:17px;font-weight:800;color:#e2e8f0;margin-bottom:6px;">{name} — Premium Only</div>
        <div style="font-size:13px;color:#3a5068;margin-bottom:16px;">Upgrade to unlock all premium categories, squeeze scanner, advanced screener, and full BI analytics.</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    if st.button("🚀 Go Premium →",type="primary",key=f"lock_{name.replace(' ','_')}"): nav("pricing")

def render_stock_row(s, show_cat_why=False):
    """Render a compact stock row with all info."""
    ticker=s["t"]; q=s["q"]; sc=s["sc"]; ig=s["ig"]
    info=s.get("info",{}); sent=s.get("sent",{}); hot=s.get("hot",False)
    op=s.get("op",""); risk=s.get("risk",""); cat_why=s.get("cat_why","")
    cat_badge=s.get("cat_badge","b-new")
    if not q: return
    pct=q.get("pct",0); price=q.get("price",0)
    cc="#22c55e" if pct>=0 else "#ef4444"
    ar="▲" if pct>=0 else "▼"
    rc=risk_color(risk)
    hot_b='<span class="b b-hot">🔥 HOT</span>' if hot else ""
    op_b=f'<span class="b b-new">{op}</span>' if op and not show_cat_why else ""
    sigs="".join([f'<span class="b b-{"bull" if s_=="bull" else "bear" if s_=="bear" else "neu"}">{l[:15]}</span>'
                  for l,_,s_,_ in ig[:2]])
    display_why=cat_why if show_cat_why and cat_why else why_text(ticker,ig,sc,sent,info)

    st.markdown(f"""<div class="sr">
        <div style="flex:2.5;">
            <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                <span class="sr-tick">{ticker}</span>{hot_b}{op_b}
            </div>
            <div class="sr-name">{q.get('name','')[:28]}</div>
            <div class="sr-why">→ {display_why}</div>
            <div style="margin-top:5px;">{sigs}</div>
        </div>
        <div style="text-align:center;min-width:80px;">
            <div style="font-size:10px;color:#2a3a50;margin-bottom:2px;">RISK</div>
            <div style="font-size:11px;font-weight:700;color:{rc};">{risk}</div>
        </div>
        <div style="text-align:right;min-width:110px;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">${price:,.2f}</div>
            <div style="font-size:12px;font-weight:700;color:{cc};font-family:'JetBrains Mono',monospace;">{ar}{abs(pct):.2f}%</div>
            <div style="margin-top:4px;">{sc_pill(sc)}</div>
        </div>
    </div>""", unsafe_allow_html=True)

def render_stock_buttons(s, cat_key=""):
    """Render Detail + Watchlist buttons for a stock."""
    bc1,bc2=st.columns(2,gap="small")
    with bc1:
        if st.button("📊 Details",key=f"d_{s['t']}_{cat_key}",use_container_width=True):
            st.session_state.detail_ticker=s["t"]
            st.session_state.detail_data=s
            nav("stock_detail")
    with bc2:
        wl=st.session_state.watchlist
        in_wl=s["t"] in wl
        lbl="✅ Watching" if in_wl else "➕ Watch"
        if st.button(lbl,key=f"w_{s['t']}_{cat_key}",use_container_width=True):
            if in_wl: wl.remove(s["t"])
            else:     wl.append(s["t"])
            st.rerun()

def render_topbar(active=""):
    """Clean top navigation bar — no label_visibility on buttons."""
    c1,c2,c3=st.columns([2,7,3])
    with c1:
        # Logo as button (no label_visibility — just use it normally)
        if st.button("📈 StockWins",key="logo_home_btn"):
            nav("landing" if not is_authed() else "dashboard")
    with c2:
        if is_authed():
            pages=[("📊 Dashboard","dashboard"),("🔭 Discover","discover"),
                   ("⭐ Watchlist","watchlist"),("🔍 Screener","screener"),
                   ("📈 BI Analytics","bi_dashboard"),("💰 Pricing","pricing")]
            if is_admin(): pages.append(("🛠 Admin","admin"))
            ncols=st.columns(len(pages))
            for col,(lbl,pg) in zip(ncols,pages):
                with col:
                    if st.button(lbl,key=f"top_{pg}",
                                 type="primary" if active==pg else "secondary"):
                        nav(pg)
    with c3:
        if is_authed():
            cc1,cc2,cc3=st.columns([3,1,1])
            role_icon={"owner":"👑","admin":"🛡","premium":"⭐","free":"👤"}.get(st.session_state.role,"👤")
            with cc1:
                st.markdown(f'<div style="font-size:12px;color:#4a6080;padding-top:9px;">{role_icon} {st.session_state.user["name"]}</div>',unsafe_allow_html=True)
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
    st.divider()

def render_sidebar():
    """Sidebar nav — fixed, no label_visibility on buttons."""
    with st.sidebar:
        st.markdown("""<div style="padding:18px 16px 10px;">
            <div class="sw-logo">Stock<span class="w">W</span>ins</div>
            <div style="font-size:10px;color:#1e2d42;margin-top:2px;">Market Intelligence Platform</div>
        </div>""", unsafe_allow_html=True)
        st.divider()

        if is_authed():
            cur=st.session_state.page
            st.markdown('<div class="nav-sec">Market</div>',unsafe_allow_html=True)
            nav_items=[
                ("📊 Market Overview","dashboard"),
                ("🔥 Trending Now","discover"),
                ("📡 Social Buzz","discover"),
                ("🔥💥 Squeeze + Buzz","discover"),
                ("📈 Momentum Movers","discover"),
                ("🔄 Smart Reversal","discover"),
            ]
            for lbl,pg in nav_items:
                # Simple button — no label_visibility
                if st.button(lbl,key=f"sb_{lbl.replace(' ','_').replace('+','p')}",use_container_width=True):
                    if pg=="discover": st.session_state.discover_cat=lbl
                    nav(pg)

            st.markdown('<div class="nav-sec">Tools</div>',unsafe_allow_html=True)
            for lbl,pg in [("🔍 Smart Screener","screener"),("📊 BI Analytics","bi_dashboard"),("⭐ Watchlist","watchlist"),("💰 Pricing","pricing")]:
                if st.button(lbl,key=f"sb_tool_{pg}",use_container_width=True): nav(pg)

            if is_admin():
                st.markdown('<div class="nav-sec">Admin</div>',unsafe_allow_html=True)
                if st.button("🛠️ Admin Panel",key="sb_admin_btn",use_container_width=True): nav("admin")

            st.divider()
            key_set=bool(get_key())
            if key_set:
                st.markdown('<div style="padding:4px 16px;font-size:11px;color:#22c55e;">✅ Live Data Active</div>',unsafe_allow_html=True)
            if not is_premium():
                if st.button("⚡ Upgrade to Premium",key="sb_upgrade_btn",type="primary",use_container_width=True):
                    nav("pricing")
        else:
            st.markdown("""<div style="padding:12px 16px;">
                <div style="font-size:12px;color:#2a3a50;margin-bottom:10px;">Sign in for the full dashboard.</div>
            </div>""", unsafe_allow_html=True)
            if st.button("Login →",key="sb_login_btn",use_container_width=True): nav("login")
            if st.button("Sign Up Free →",key="sb_signup_btn",type="primary",use_container_width=True): nav("signup")
            st.markdown("""<div style="margin:12px 8px;background:#080d18;border:1px solid #111c2e;border-radius:8px;padding:12px;">
                <div style="font-size:10px;font-weight:700;color:#1e2d42;margin-bottom:6px;text-transform:uppercase;letter-spacing:1px;">What You Get Free</div>
                <div style="font-size:12px;color:#2a3a50;line-height:2;">✅ Market overview<br>✅ 5+ categories<br>✅ Social sentiment<br>✅ Plain-English insights<br>✅ Watchlist (10 stocks)</div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<div style="padding:6px 16px;font-size:10px;color:#111c2e;margin-top:8px;">© 2026 StockWins · Educational use only</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# DEMO PANELS for hero
# ─────────────────────────────────────────────────────────────────────
DEMO_PANELS=[
    # Market Overview
    """<div style="background:#0d1525;border:1px solid #1a2840;border-radius:10px;overflow:hidden;">
    <div style="background:#080d18;border-bottom:1px solid #111c2e;padding:9px 14px;display:flex;align-items:center;gap:6px;">
        <div style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></div>
        <span style="font-size:11px;color:#2a3a50;margin-left:8px;font-family:'JetBrains Mono',monospace;">Market Overview</span>
    </div>
    <div style="padding:14px;">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:12px;">
            <div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:10px;"><div style="font-size:9px;color:#3a5068;">NASDAQ</div><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">18,965</div><div style="font-size:11px;font-weight:700;color:#22c55e;">▲ 2.99%</div></div>
            <div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:10px;"><div style="font-size:9px;color:#3a5068;">S&P 500</div><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">5,318</div><div style="font-size:11px;font-weight:700;color:#22c55e;">▲ 1.25%</div></div>
            <div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:10px;"><div style="font-size:9px;color:#3a5068;">VIX</div><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">18.40</div><div style="font-size:11px;font-weight:700;color:#ef4444;">▼ 3.92%</div></div>
        </div>
        <div style="font-size:10px;color:#3a5068;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px;">StockTwits Hot Stocks</div>
        <div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:9px 12px;margin-bottom:5px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:13px;">AAPL</span><div style="font-size:10px;color:#2a3a50;">Trending on StockTwits</div><div style="margin-top:4px;"><span style="background:#052e16;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;">RSI Oversold</span><span style="background:#1c0800;color:#f97316;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;margin-left:3px;">🔥 HOT</span></div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#e2e8f0;">$182.58</div><div style="font-size:11px;font-weight:700;color:#22c55e;">▲ 1.99%</div><div style="font-size:10px;color:#4ade80;background:#052e16;padding:1px 8px;border-radius:3px;margin-top:3px;">76</div></div>
        </div>
        <div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:9px 12px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:13px;">NVDA</span><div style="font-size:10px;color:#2a3a50;">AI momentum leader</div><div style="margin-top:4px;"><span style="background:#052e16;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;">Golden Cross ✨</span></div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#e2e8f0;">$875.40</div><div style="font-size:11px;font-weight:700;color:#22c55e;">▲ 3.21%</div><div style="font-size:10px;color:#4ade80;background:#052e16;padding:1px 8px;border-radius:3px;margin-top:3px;">88</div></div>
        </div>
    </div></div>""",

    # Squeeze Scanner
    """<div style="background:#0d1525;border:1px solid #1a2840;border-radius:10px;overflow:hidden;">
    <div style="background:#080d18;border-bottom:1px solid #111c2e;padding:9px 14px;display:flex;align-items:center;gap:6px;">
        <div style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></div>
        <span style="font-size:11px;color:#2a3a50;margin-left:8px;font-family:'JetBrains Mono',monospace;">Short Squeeze Candidates</span>
        <span style="background:#1c1000;color:#f59e0b;font-size:9px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:auto;">PREMIUM</span>
    </div>
    <div style="padding:14px;">
        <div style="font-size:10px;color:#3a5068;margin-bottom:8px;">Short 239 · StockWins composite signal</div>
        <div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:9px 12px;margin-bottom:5px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:13px;">AMC</span><div style="font-size:10px;color:#2a3a50;">Strong uptrend · Short watchers continue rising</div><div style="margin-top:4px;"><span style="background:#052e16;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;">🔥💥 Squeeze + Buzz</span></div></div>
            <div style="text-align:right;"><div style="font-size:9px;color:#2a3a50;">Short Score</div><div style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:#ef4444;">29.99%</div></div>
        </div>
        <div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:9px 12px;margin-bottom:5px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:13px;">CVNA</span><div style="font-size:10px;color:#2a3a50;">⚡📈 Volume Breakout confirmed</div></div>
            <div style="text-align:right;"><div style="font-size:9px;color:#2a3a50;">Short Score</div><div style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:#22c55e;">38.75</div><div style="font-size:10px;color:#22c55e;">+5.42%</div></div>
        </div>
        <div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:9px 12px;display:flex;justify-content:space-between;align-items:center;">
            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:13px;">MSTR</span><div style="font-size:10px;color:#2a3a50;">Trending above avg — squeeze building</div></div>
            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#e2e8f0;">$11,601</div><div style="font-size:11px;font-weight:700;color:#22c55e;">▲ 85.84%</div></div>
        </div>
    </div></div>""",

    # Plain-English Insights
    """<div style="background:#0d1525;border:1px solid #1a2840;border-radius:10px;overflow:hidden;">
    <div style="background:#080d18;border-bottom:1px solid #111c2e;padding:9px 14px;display:flex;align-items:center;gap:6px;">
        <div style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;display:inline-block;"></div>
        <div style="width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;"></div>
        <span style="font-size:11px;color:#2a3a50;margin-left:8px;font-family:'JetBrains Mono',monospace;">Smart Insights — Plain Language</span>
    </div>
    <div style="padding:14px;">
        <div style="background:#0a1020;border-left:2px solid #22c55e;border-radius:0 6px 6px 0;padding:10px 12px;margin-bottom:6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:13px;">TSLA</span>
                <span style="font-size:11px;font-weight:700;color:#22c55e;">▲ 4.27%</span>
            </div>
            <div style="font-size:11px;color:#3a5068;"><span style="color:#2dd4bf;font-weight:700;">The Moving Average</span> is breaking out above an important price range, which can sometimes lead to further upside.</div>
        </div>
        <div style="background:#0a1020;border-left:2px solid #4ade80;border-radius:0 6px 6px 0;padding:10px 12px;margin-bottom:6px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:13px;">PLUG</span>
                <span style="background:#052e16;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;">BULLISH</span>
            </div>
            <div style="font-size:11px;color:#3a5068;">There are a lot of <span style="color:#c9d3e0;font-weight:600;">traders</span> betting against this stock, and momentum is building.</div>
        </div>
        <div style="background:#0a1020;border-left:2px solid #ef4444;border-radius:0 6px 6px 0;padding:10px 12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:13px;">AAPL</span>
                <span style="font-size:10px;color:#f97316;font-weight:700;">🔥 Hot!</span>
            </div>
            <div style="font-size:11px;color:#3a5068;">The stock <span style="color:#c9d3e0;font-weight:600;">may have risen too much too quickly</span> and could be due for <span style="color:#c9d3e0;font-style:italic;font-weight:600;">a pullback</span>.</div>
        </div>
    </div></div>""",
]

# ─────────────────────────────────────────────────────────────────────
# PAGE: LANDING
# ─────────────────────────────────────────────────────────────────────
def page_landing():
    # Top nav
    nc1,_,nc2=st.columns([2,5,3])
    with nc1:
        if st.button("📈 StockWins",key="land_logo"): pass  # already on landing
    with nc2:
        lc1,lc2,lc3=st.columns(3)
        with lc1:
            if st.button("Features",key="land_feat"):
                st.session_state.page="landing"; st.rerun()
        with lc2:
            if st.button("Login",key="land_log"): nav("login")
        with lc3:
            if st.button("Start Free",key="land_su",type="primary"): nav("signup")
    st.divider()

    # Hero — left text, right rotating demo panel
    hl,hr=st.columns([5,5],gap="large")
    panel_idx=st.session_state.get("hero_panel",0)

    with hl:
        st.markdown("""<div style="padding:48px 0 32px 48px;">
            <div class="hero-eyebrow">Smart Stock Discovery Platform</div>
            <div class="hero-h1">Spot Market Opportunities<br><span class="hi">Before They Get Crowded</span></div>
            <div style="height:8px;"></div>
            <div class="hero-sub">Discover trending stocks, social buzz, short squeeze candidates, and momentum shifts in one powerful dashboard. No API key required — just sign up and go.</div>
        </div>""",unsafe_allow_html=True)

        bc1,bc2,bc3=st.columns(3)
        with bc1:
            if st.button("Start Free",key="h_su",type="primary",use_container_width=True): nav("signup")
        with bc2:
            if st.button("Try Live Dashboard",key="h_dash",use_container_width=True): nav("login")
        with bc3:
            if st.button("View Pricing",key="h_price",use_container_width=True): nav("pricing")

        st.markdown("<br>",unsafe_allow_html=True)
        labels=["📊 Market Overview","💥 Squeeze Scanner","💡 Plain-English Insights"]
        dc=st.columns(3)
        for i,(col,lbl) in enumerate(zip(dc,labels)):
            with col:
                if st.button(lbl,key=f"demo_{i}",type="primary" if panel_idx==i else "secondary",use_container_width=True):
                    st.session_state.hero_panel=i; st.rerun()

    with hr:
        st.markdown(f'<div style="padding:32px 48px 24px 0;">{DEMO_PANELS[panel_idx]}</div>',unsafe_allow_html=True)

    # Stats bar
    st.markdown("""<div class="stats-bar">
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:20px;">📊</span><div><div class="stats-val">5,000+</div><div class="stats-lbl">US Stocks Covered</div></div></div>
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:20px;">🔬</span><div><div class="stats-val">10+</div><div class="stats-lbl">Smart Stock Categories</div></div></div>
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:20px;">💰</span><div><div class="stats-val">$0</div><div class="stats-lbl">To Get Started</div></div></div>
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:20px;">⚡</span><div><div class="stats-val">Real-Time</div><div class="stats-lbl">Sentiment Data</div></div></div>
    </div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Section 1: Find Trending Stocks (matching image 2 layout)
    st.markdown("""<div style="padding:40px 48px;background:radial-gradient(ellipse at 20% 50%,#060f2e,#060a12);border-top:1px solid #111c2e;border-bottom:1px solid #111c2e;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:start;">
            <div>
                <div style="font-size:32px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Find Trending Stocks<br><span style="color:#2563eb;">Before the Crowd</span></div>
                <div style="font-size:14px;color:#3a5068;margin-bottom:20px;line-height:1.7;">Discover top stocks making waves across social media and the market in one smart dashboard.</div>
                <div style="background:#0d1525;border:1px solid #1a2840;border-radius:10px;overflow:hidden;">
                    <div style="background:#080d18;border-bottom:1px solid #111c2e;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:12px;font-weight:700;color:#c9d3e0;">StockTwits Hot Stocks</span>
                        <span style="font-size:10px;color:#2a3a50;">LIVE ●</span>
                    </div>
                    <div style="padding:10px 14px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #111c2e;">
                            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;">TSLA</span><span style="font-size:10px;color:#3a5068;margin-left:8px;">Tesla · Momentum is strongly trending</span></div>
                            <div style="text-align:right;"><span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#22c55e;">+12.72</span></div>
                        </div>
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #111c2e;">
                            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;">NVDA</span><span style="font-size:10px;color:#3a5068;margin-left:8px;">Nvidia · AI sector leader</span></div>
                            <div style="text-align:right;"><span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#22c55e;">+33.99</span></div>
                        </div>
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;">
                            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;">AI</span><span style="font-size:10px;color:#3a5068;margin-left:8px;">C3.ai · Smart Entrainment play</span></div>
                            <div style="text-align:right;"><span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#ef4444;">-29.75</span></div>
                        </div>
                    </div>
                    <div style="background:#080d18;border-top:1px solid #111c2e;padding:8px 14px;display:flex;gap:6px;">
                        <span style="background:#0e1525;color:#60a5fa;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid #1a2840;">Momentum</span>
                        <span style="background:#0e1525;color:#60a5fa;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid #1a2840;">Breakout Watch</span>
                        <span style="background:#0e1525;color:#60a5fa;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;border:1px solid #1a2840;">Tech Stocks</span>
                    </div>
                </div>
            </div>
            <div>
                <div style="font-size:32px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Scan For Short Squeeze<br><span style="color:#2563eb;">Candidates</span></div>
                <div style="font-size:14px;color:#3a5068;margin-bottom:20px;line-height:1.7;">Spot stocks with heavy short interest and growing momentum before the move.</div>
                <div style="background:#0d1525;border:1px solid #1a2840;border-radius:10px;overflow:hidden;">
                    <div style="background:#080d18;border-bottom:1px solid #111c2e;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:12px;font-weight:700;color:#c9d3e0;">Short Squeeze Candidates</span>
                        <span style="background:#1c1000;color:#f59e0b;font-size:9px;font-weight:700;padding:2px 8px;border-radius:20px;">Short 239</span>
                    </div>
                    <div style="padding:10px 14px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #111c2e;">
                            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;">AMC</span><div style="font-size:10px;color:#3a5068;">Strong uptrend · squeeze watchers rising</div></div>
                            <div style="text-align:right;"><div style="font-size:9px;color:#2a3a50;">Short Score</div><div style="font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700;color:#ef4444;">29.99</div></div>
                        </div>
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #111c2e;">
                            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;">CVNA</span><div style="font-size:10px;color:#3a5068;">Volume breakout confirmed</div></div>
                            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#22c55e;">+19.35%</div><div style="font-size:12px;color:#3a5068;">Score: 38.75</div></div>
                        </div>
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;">
                            <div><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;">MSTR</span><div style="font-size:10px;color:#3a5068;">Trending above average — squeeze building</div></div>
                            <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#22c55e;">+185.84%</div><div style="font-size:12px;color:#3a5068;">Score: 38.58</div></div>
                        </div>
                    </div>
                    <div style="background:#080d18;border-top:1px solid #111c2e;padding:8px 14px;display:flex;gap:6px;">
                        <span style="background:#1c0800;color:#f97316;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;">Meme Stocks</span>
                        <span style="background:#1c0800;color:#f97316;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;">High Short Interest</span>
                        <span style="background:#1c0800;color:#f97316;font-size:9px;font-weight:700;padding:3px 8px;border-radius:4px;">Squeeze Radar</span>
                    </div>
                </div>
            </div>
        </div>
    </div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Section 2: Smart Insights + Go Premium (matching image 2 bottom)
    st.markdown("""<div style="padding:40px 48px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:start;">
            <div>
                <div style="font-size:32px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Smart Insights<br>in Simple <span style="color:#2563eb;">Language</span></div>
                <div style="font-size:14px;color:#3a5068;margin-bottom:20px;line-height:1.7;">Understand technical setups with plain-English explanations that actually make sense.</div>
                <div style="background:#0d1525;border:1px solid #1a2840;border-radius:10px;padding:14px;">
                    <div style="background:#0a1020;border-left:2px solid #22c55e;border-radius:0 6px 6px 0;padding:12px 14px;margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">TSLA</span><span style="color:#22c55e;font-weight:700;font-size:13px;">▲ 4.27%</span></div>
                        <div style="font-size:12px;color:#3a5068;line-height:1.5;"><span style="color:#2dd4bf;font-weight:600;">The Moving Average</span> is breaking out above an important price range, which can sometimes lead to further upside.</div>
                    </div>
                    <div style="background:#0a1020;border-left:2px solid #4ade80;border-radius:0 6px 6px 0;padding:12px 14px;margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">PLUG</span><span style="background:#052e16;color:#4ade80;font-size:10px;font-weight:700;padding:2px 8px;border-radius:3px;">BULLISH</span></div>
                        <div style="font-size:12px;color:#3a5068;line-height:1.5;">There are a lot of <span style="color:#c9d3e0;font-weight:600;">traders</span> betting against this stock, and <span style="color:#c9d3e0;font-weight:600;">momentum is building</span> — squeeze potential rising.</div>
                    </div>
                    <div style="background:#0a1020;border-left:2px solid #ef4444;border-radius:0 6px 6px 0;padding:12px 14px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-family:'JetBrains Mono',monospace;font-weight:700;color:#60a5fa;font-size:14px;">AAPL</span><span style="color:#f97316;font-weight:700;font-size:11px;">🔥 Hot!</span></div>
                        <div style="font-size:12px;color:#3a5068;line-height:1.5;">The stock <span style="color:#c9d3e0;font-weight:600;">may have risen too much too quickly</span> and could be due for <span style="color:#c9d3e0;font-style:italic;font-weight:600;">a pullback</span>.</div>
                    </div>
                </div>
            </div>
            <div>
                <div style="font-size:32px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Go Premium For<br><span style="color:#f59e0b;">Real-Time Signals</span> &<br><span style="color:#f59e0b;">Deeper Analysis</span></div>
                <div style="font-size:14px;color:#3a5068;margin-bottom:20px;line-height:1.7;">Upgrade to unlock advanced screening, unlimited alerts, and premium watchlists.</div>
                <div style="background:#0d1525;border:1px solid #1a2840;border-radius:10px;overflow:hidden;">
                    <div style="background:linear-gradient(135deg,#06163a,#0d1525);border-bottom:1px solid #1a2840;padding:12px 16px;text-align:center;font-size:13px;font-weight:700;color:#60a5fa;letter-spacing:1px;">Premium Features</div>
                    <div style="padding:16px;">
                        <div style="font-size:13px;color:#3a5068;line-height:2.4;">
                            ✅ Advanced Stock Screeners<br>
                            ✅ Real-Time Alerts<br>
                            ✅ Unlimited Watchlists<br>
                            ✅ Enhanced Analysis<br>
                            ✅ Premium Signals<br>
                            ✅ Full Dashboard Access
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>""",unsafe_allow_html=True)

    # Go Premium CTA button
    _,pc,_=st.columns([1,2,1])
    with pc:
        if st.button("🚀 Go Premium →",key="land_go_prem",type="primary",use_container_width=True):
            nav("pricing")
    st.markdown("<br>",unsafe_allow_html=True)

    # Composite Categories preview
    st.markdown('<div style="padding:0 48px;"><div class="sec">Our Proprietary Signal Categories</div>',unsafe_allow_html=True)
    st.markdown('<div style="font-size:13px;color:#3a5068;margin-bottom:16px;">StockWins combines multiple independent data signals into unique composite categories you won\'t find anywhere else.</div>',unsafe_allow_html=True)
    cat_grid=st.columns(3,gap="small")
    composite_list=list(COMPOSITE_CATS.items())
    for i,(cat,desc) in enumerate(composite_list):
        with cat_grid[i%3]:
            color=["#7e22ce","#0e7490","#b45309","#1d4ed8","#16a34a","#b45309"][i%6]
            lock_label=' <span style="font-size:9px;background:#1c1000;color:#f59e0b;padding:2px 6px;border-radius:3px;">PRO</span>' if cat in ALL_COMPOSITE_PREM else ""
            st.markdown(f"""<div class="sw-card" style="border-left:3px solid {color};">
                <div style="font-size:15px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">{cat}{lock_label}</div>
                <div style="font-size:12px;color:#3a5068;line-height:1.5;">{desc}</div>
            </div>""",unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
    if st.button("Explore All Categories →",key="land_cats",use_container_width=False):
        nav("signup")

    st.markdown("<br>",unsafe_allow_html=True)

    # Features
    st.markdown('<div style="padding:0 48px;"><div class="sec">Why Traders Choose StockWins</div>',unsafe_allow_html=True)
    feats=[("📡","Live Sentiment Signals","Track thousands of traders in real time — know when the crowd turns before price moves."),
           ("💬","Plain-English Insights","Every RSI, MACD, and MA signal explained clearly. No finance degree needed."),
           ("💥","Short Squeeze Scanner","Identify stocks with heavy short interest before the squeeze runs."),
           ("📊","BI Dashboards","Sector heatmaps, volume leaders, momentum leaderboards — all in one place."),
           ("🔊","Volume Surge Detection","Be first to spot unusual activity — often the earliest signal of a major move."),
           ("🎯","Proprietary Scoring","0–100 score combining momentum, trend, MACD, volume, sentiment, and squeeze potential.")]
    for i in range(0,len(feats),3):
        cols=st.columns(3,gap="small")
        for j,col in enumerate(cols):
            if i+j<len(feats):
                ic,t,d=feats[i+j]
                col.markdown(f'<div class="sw-card card-blue"><div style="font-size:22px;margin-bottom:8px;">{ic}</div><div style="font-size:13px;font-weight:700;color:#c9d3e0;margin-bottom:5px;">{t}</div><div style="font-size:12px;color:#3a5068;line-height:1.6;">{d}</div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Testimonials
    st.markdown('<div style="padding:0 48px;"><div class="sec">What Traders Are Saying</div>',unsafe_allow_html=True)
    for col,(stars,txt,name) in zip(st.columns(3,gap="small"),[
        ("⭐⭐⭐⭐⭐","Plain-English explanations changed how I analyze stocks. The composite categories are genius — Squeeze + Buzz saved me hours of research.","Michael T., Active Trader"),
        ("⭐⭐⭐⭐⭐","No API key setup, just sign in and it works. The squeeze scanner flagged AMC 3 days before it ran.","Sarah K., Day Trader"),
        ("⭐⭐⭐⭐⭐","The Hidden Movers category is my secret weapon. Found 3 stocks before they went viral on StockTwits.","David R., Swing Trader"),
    ]):
        col.markdown(f'<div class="sw-card"><div style="margin-bottom:6px;">{stars}</div><div style="font-size:12px;color:#3a5068;line-height:1.6;margin-bottom:10px;">"{txt}"</div><div style="font-size:11px;font-weight:600;color:#2563eb;">— {name}</div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # FAQ
    st.markdown('<div style="padding:0 48px;"><div class="sec">FAQ</div>',unsafe_allow_html=True)
    for q,a in [
        ("Is this financial advice?","No. StockWins is an educational analysis tool. All signals are algorithmic outputs. Always consult a licensed financial advisor before making investment decisions."),
        ("Do I need to enter an API key?","No. Regular users never enter any API key. All data is fetched automatically. Just sign up and start exploring immediately."),
        ("What are the proprietary composite categories?","We combine multiple independent signals — like StockTwits social buzz + short interest data — to surface unique opportunities. For example, '🔥💥 Squeeze + Buzz' finds stocks with high short float that are also trending socially, creating explosive potential."),
        ("How is the StockWins Score calculated?","0–100 combining: RSI momentum (0–25), price vs moving averages (0–20), MACD signal (0–15), volume activity (0–15), social sentiment (0–15), and short squeeze potential (0–10)."),
        ("Can I cancel Premium anytime?","Yes. Cancel at any time and keep access through the end of your billing period."),
    ]:
        with st.expander(q):
            st.markdown(f'<div style="font-size:13px;color:#3a5068;line-height:1.7;">{a}</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

    # Footer
    st.markdown("""<div style="background:#060a12;border-top:1px solid #111c2e;padding:32px 48px;margin-top:32px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:12px;">
            <div class="sw-logo">Stock<span class="w">W</span>ins</div>
            <div style="font-size:12px;color:#1e2d42;display:flex;gap:20px;cursor:pointer;">
                <span>Privacy Policy</span><span>Terms of Service</span><span>Risk Disclaimer</span><span>Contact</span>
            </div>
        </div>
        <div class="disc">⚠️ <strong>Risk Disclaimer:</strong> Trading stocks involves substantial risk of financial loss. StockWins provides algorithmic, educational content only. Nothing constitutes financial, investment, legal, or tax advice. All signals may be inaccurate or delayed. Past performance does not guarantee future results. Always consult a licensed financial professional.</div>
        <div style="font-size:10px;color:#111c2e;margin-top:10px;text-align:right;">© 2026 StockWins. All rights reserved.</div>
    </div>""",unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# AUTH PAGES
# ─────────────────────────────────────────────────────────────────────
def page_login():
    render_topbar()
    _,cc,_=st.columns([1,2,1])
    with cc:
        st.markdown('<div style="text-align:center;padding:32px 0 20px;"><div style="font-size:24px;font-weight:800;color:#e2e8f0;">Welcome Back 👋</div><div style="font-size:13px;color:#3a5068;margin-top:6px;">Sign in to your StockWins account</div></div>',unsafe_allow_html=True)
        with st.form("lf"):
            email=st.text_input("Email",placeholder="you@example.com")
            pw=st.text_input("Password",type="password",placeholder="••••••••")
            sub=st.form_submit_button("Sign In →",type="primary",use_container_width=True)
            if sub:
                if login(email,pw): nav("dashboard")
                else: st.error("Invalid email or password. Check the demo accounts below.")
        st.markdown("""<div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:12px 14px;margin-top:10px;font-size:12px;color:#3a5068;">
            <span style="color:#2563eb;font-weight:600;">Demo accounts:</span><br>
            Free: demo@stockwins.com / demo123<br>
            Premium: premium@stockwins.com / premium1<br>
            Admin: admin@stockwins.com / admin123
        </div>""",unsafe_allow_html=True)
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("No account? Create one free →",key="login_to_signup",use_container_width=True): nav("signup")
        if st.button("Forgot password?",key="login_forgot",use_container_width=True): nav("forgot_pw")
        if st.button("← Back to Home",key="login_home",use_container_width=True): nav("landing")

def page_signup():
    render_topbar()
    _,cc,_=st.columns([1,2,1])
    with cc:
        st.markdown('<div style="text-align:center;padding:32px 0 20px;"><div style="font-size:24px;font-weight:800;color:#e2e8f0;">Create Your Account 🚀</div><div style="font-size:13px;color:#3a5068;margin-top:6px;">Free forever. No credit card. No API keys.</div></div>',unsafe_allow_html=True)
        with st.form("sf"):
            name=st.text_input("Full name",placeholder="Jane Doe")
            email=st.text_input("Email",placeholder="you@example.com")
            pw=st.text_input("Password",type="password",placeholder="Min 6 characters")
            pw2=st.text_input("Confirm password",type="password")
            agree=st.checkbox("I agree to the Terms of Service and understand this is not financial advice.")
            sub=st.form_submit_button("Create Free Account →",type="primary",use_container_width=True)
            if sub:
                if not all([name,email,pw,pw2]): st.error("Please fill in all fields.")
                elif pw!=pw2: st.error("Passwords don't match.")
                elif len(pw)<6: st.error("Password must be 6+ characters.")
                elif not agree: st.error("Please agree to the Terms of Service.")
                else:
                    ok,msg=signup(email,pw,name)
                    if ok:
                        st.success(f"✅ Account created! Welcome, {name}!")
                        time.sleep(0.5); nav("verify_email")
                    else: st.error(msg)
        if st.button("Already have an account? Sign In",key="signup_to_login",use_container_width=True): nav("login")

def page_verify():
    render_topbar()
    _,cc,_=st.columns([1,2,1])
    with cc:
        st.markdown("""<div class="sw-card" style="text-align:center;padding:40px 28px;margin-top:32px;">
            <div style="font-size:40px;margin-bottom:14px;">📧</div>
            <div style="font-size:20px;font-weight:800;color:#e2e8f0;margin-bottom:8px;">Verify Your Email</div>
            <div style="font-size:13px;color:#3a5068;line-height:1.7;margin-bottom:20px;">
                We've sent a verification link to your email. Click it to complete your account setup.<br>
                <span style="font-size:11px;color:#1e2d42;">(Simulated in demo — click Continue below)</span>
            </div>
        </div>""",unsafe_allow_html=True)
        if st.button("✅ Email Verified — Continue to Dashboard",key="verify_continue",type="primary",use_container_width=True):
            email=st.session_state.user["email"] if is_authed() else ""
            if email in st.session_state.users_db:
                st.session_state.users_db[email]["verified"]=True
            nav("dashboard")
        if st.button("Resend verification email",key="verify_resend",use_container_width=True):
            st.info("Verification email resent! (simulated)")
        if st.button("Skip for now → Go to Dashboard",key="verify_skip",use_container_width=True):
            nav("dashboard")

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
        if st.button("← Back to Login",key="forgot_back",use_container_width=True): nav("login")

# ─────────────────────────────────────────────────────────────────────
# CATEGORY RENDERER
# ─────────────────────────────────────────────────────────────────────
def render_category(cat, limit=12, show_cat_why=False):
    """Render any category — standard or composite."""
    is_composite=cat in COMPOSITE_CATS

    if is_composite:
        # Premium check for premium composite cats
        if cat in ALL_COMPOSITE_PREM and not is_premium():
            render_lock(cat); return
        st.markdown(f'<div style="font-size:12px;color:#3a5068;margin-bottom:12px;font-style:italic;">{COMPOSITE_CATS[cat]}</div>',unsafe_allow_html=True)
        stocks=get_composite_stocks(cat,limit)
    else:
        tickers=list(CATEGORIES.get(cat,[]))
        hot=st_hot()
        if cat=="🔥 Trending Now": tickers=hot
        if not tickers: st.info("No tickers for this category."); return
        scan=min(len(tickers),limit)
        st.caption(f"Analyzing top {scan} stocks · via Yahoo Finance & StockTwits")
        stocks=[]; prog=st.progress(0,f"Loading {cat}...")
        for i,t in enumerate(tickers[:scan]):
            prog.progress((i+1)/scan,f"Analyzing {t}...")
            q=get_quote(t); df=get_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            sc,bd,op,risk,conf=compute_scores(df,info,sent); ig=get_insights(df,info)
            if q: stocks.append({"t":t,"q":q,"sc":sc,"bd":bd,"ig":ig,"op":op,"risk":risk,"conf":conf,"hot":t in hot,"df":df,"info":info,"sent":sent,"comp":sc,"cat_why":"","cat_badge":"b-new"})
        prog.empty()
        stocks.sort(key=lambda x:x["sc"],reverse=True)

    if not stocks: st.info(f"No stocks currently meeting criteria for {cat}."); return

    for s in stocks:
        ca,cb=st.columns([5,2],gap="small")
        with ca: render_stock_row(s,show_cat_why=is_composite)
        with cb: render_stock_buttons(s,cat_key=cat.replace(" ","_").replace("+","p"))

# ─────────────────────────────────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────────────────────────────────
def page_dashboard():
    render_topbar("dashboard")
    st.markdown('<div class="pg">',unsafe_allow_html=True)

    db_user=get_db_user()
    if not db_user.get("verified",True):
        st.markdown('<div style="background:#06163a;border:1px solid #1e3a8a;border-radius:6px;padding:10px 16px;margin-bottom:14px;font-size:13px;color:#60a5fa;">📧 Please verify your email to unlock all features.</div>',unsafe_allow_html=True)

    # Indexes
    st.markdown('<div class="sec">📊 Market Overview <span class="cnt">Live</span></div>',unsafe_allow_html=True)
    with st.spinner("Loading market data..."):
        idx=get_indexes(); secs=get_sectors()

    idx_cols=st.columns(len(idx))
    for col,(name,d) in zip(idx_cols,idx.items()):
        c="color:#22c55e" if d["pct"]>=0 else "color:#ef4444"
        ar="▲" if d["pct"]>=0 else "▼"
        trend=d.get("trend",[])
        bars=""
        if trend:
            mn,mx=min(trend),max(trend); rng=mx-mn if mx!=mn else 1
            bars=''.join([f'<div style="height:{int(12*(v-mn)/rng+4)}px;width:5px;background:{"#22c55e" if d["pct"]>=0 else "#ef4444"};border-radius:2px;display:inline-block;margin-right:1px;vertical-align:bottom;"></div>' for v in trend])
        col.markdown(f"""<div class="idx">
            <div class="idx-name">{name}</div>
            <div class="idx-price">{d['price']:,.2f}</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;{c};">{ar} {abs(d['pct']):.2f}%</div>
            <div style="margin-top:8px;height:18px;display:flex;align-items:flex-end;">{bars}</div>
        </div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Sector + Sentiment
    sc,mc=st.columns([3,2],gap="small")
    with sc:
        st.markdown('<div class="sec" style="font-size:13px;">Sector Performance</div>',unsafe_allow_html=True)
        row1=st.columns(5); row2=st.columns(5)
        for i,(sec,chg) in enumerate(secs.items()):
            col=row1[i%5] if i<5 else row2[i%5]
            cls="hm-hi" if chg>0.2 else "hm-lo" if chg<-0.2 else "hm-neu"
            ar="▲" if chg>=0 else "▼"
            col.markdown(f'<div class="hm {cls}" style="margin-bottom:4px;"><div style="font-size:9px;margin-bottom:2px;">{sec}</div>{ar}{abs(chg):.1f}%</div>',unsafe_allow_html=True)
    with mc:
        st.markdown('<div class="sec" style="font-size:13px;">Market Pulse</div>',unsafe_allow_html=True)
        movers=get_bi_movers()
        avg_pct=sum(m["pct"] for m in movers)/len(movers) if movers else 0
        gainers=[m for m in movers if m["pct"]>0]
        losers=[m for m in movers if m["pct"]<0]
        sent_lbl="Risk-On 🟢" if avg_pct>0.3 else "Risk-Off 🔴" if avg_pct<-0.3 else "Neutral ⚪"
        sc_="color:#22c55e" if avg_pct>0 else "color:#ef4444"
        hot=st_hot()
        st.markdown(f"""<div class="sw-card" style="padding:12px 14px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="font-size:13px;font-weight:700;{sc_};">{sent_lbl}</span>
                <span style="font-size:12px;color:#2a3a50;">Avg {avg_pct:+.2f}%</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:12px;color:#3a5068;margin-bottom:8px;">
                <span>🟢 {len(gainers)} advancing</span>
                <span>🔴 {len(losers)} declining</span>
            </div>
            <div style="font-size:10px;color:#2a3a50;margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px;">🔥 StockTwits Trending</div>
            <div style="line-height:2.2;">{" ".join([f'<span style="background:#1c0800;color:#f97316;font-size:10px;font-weight:700;padding:2px 7px;border-radius:3px;margin-right:3px;">{t}</span>' for t in hot[:6]])}</div>
        </div>""",unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # ── Proprietary Composite Categories dashboard ──
    st.markdown('<div class="sec">🎯 Our Proprietary Signal Categories <span class="cnt">Unique to StockWins</span></div>',unsafe_allow_html=True)
    st.caption("Combining multiple independent signals to surface unique opportunities — StockWins composite analytics")

    # Show composite category cards in 2 cols
    comp_left,comp_right=st.columns(2,gap="small")
    comp_items=list(COMPOSITE_CATS.items())[:4]
    for i,(cat,desc) in enumerate(comp_items):
        col=comp_left if i%2==0 else comp_right
        is_prem_cat=cat in ALL_COMPOSITE_PREM
        color_map={"🔥💥 Squeeze + Buzz":"#7e22ce","⚡📈 Volume Breakout":"#0e7490",
                   "🎯 Smart Reversal":"#b45309","💡 Hidden Movers":"#1d4ed8",
                   "🌊 Momentum Leaders":"#16a34a","🎭 Social Catalyst":"#92400e"}
        c=color_map.get(cat,"#2563eb")
        with col:
            prem_badge=f'<span style="float:right;background:#1c1000;color:#f59e0b;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;">PREMIUM</span>' if is_prem_cat else '<span style="float:right;background:#052e16;color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;">FREE</span>'
            st.markdown(f"""<div class="sw-card" style="border-left:3px solid {c};cursor:pointer;">
                {prem_badge}
                <div style="font-size:14px;font-weight:700;color:#e2e8f0;margin-bottom:4px;">{cat}</div>
                <div style="font-size:11px;color:#3a5068;">{desc}</div>
            </div>""",unsafe_allow_html=True)
            btn_key=f"dash_comp_{cat.replace(' ','_').replace('+','p')}"
            if st.button(f"Explore {cat} →",key=btn_key,use_container_width=True):
                if is_prem_cat and not is_premium():
                    nav("pricing")
                else:
                    st.session_state.discover_cat=cat; nav("discover")

    st.markdown("<br>",unsafe_allow_html=True)

    # Two-column: StockTwits Hot + Squeeze preview
    left,right=st.columns(2,gap="small")
    with left:
        st.markdown('<div class="sec">📡 StockTwits Hot Stocks <span class="cnt">Live</span></div>',unsafe_allow_html=True)
        hot=st_hot()
        if hot:
            prog=st.progress(0,"Loading...")
            for i,t in enumerate(hot[:6]):
                prog.progress((i+1)/6,f"Loading {t}...")
                q=get_quote(t)
                if q:
                    s=st_sent(t)
                    cc_="#22c55e" if q["pct"]>=0 else "#ef4444"
                    ar="▲" if q["pct"]>=0 else "▼"
                    st.markdown(f"""<div class="sr">
                        <div style="flex:2.5;"><span class="sr-tick">{t}</span><span class="b b-hot" style="margin-left:6px;">🔥</span>
                        <div class="sr-name">{q.get('name','')[:24]}</div>
                        <div class="sr-why">→ {s['bull']}% bullish · {s.get('wl',0):,} watching</div></div>
                        <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">${q['price']:,.2f}</div>
                        <div style="font-size:12px;font-weight:700;color:{cc_};">{ar}{abs(q['pct']):.2f}%</div></div>
                    </div>""",unsafe_allow_html=True)
            prog.empty()

    with right:
        st.markdown('<div class="sec">🔥💥 Squeeze + Buzz Preview <span class="cnt">Composite</span></div>',unsafe_allow_html=True)
        st.caption("High short float + social trending = explosive combo")
        preview_tickers=["GME","AMC","MSTR","BBIG","MULN"]
        prog=st.progress(0,"Scanning squeeze candidates...")
        shown=0
        for i,t in enumerate(preview_tickers):
            prog.progress((i+1)/len(preview_tickers))
            info=yf_fund(t); sf=(info.get("sf",0) or 0)*100
            if sf>=8:
                q=get_quote(t)
                if q:
                    shown+=1
                    cc_="#22c55e" if q["pct"]>=0 else "#ef4444"
                    st.markdown(f"""<div class="sr">
                        <div style="flex:2.5;"><span class="sr-tick">{t}</span>
                        <div class="sr-name">{q.get('name','')[:24]}</div>
                        <div class="sr-why">→ Short float: <span style="color:#ef4444;font-weight:700;">{sf:.1f}%</span> · Days-to-cover: {info.get('dtc',0) or 0:.1f}</div></div>
                        <div style="text-align:right;"><div style="font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:700;color:#e2e8f0;">${q['price']:,.2f}</div>
                        <div style="font-size:12px;font-weight:700;color:{cc_};">{"▲" if q['pct']>=0 else "▼"}{abs(q['pct']):.2f}%</div></div>
                    </div>""",unsafe_allow_html=True)
        prog.empty()
        if shown==0: st.info("No squeeze candidates above threshold right now.")
        if st.button("Full Squeeze Scanner →",key="dash_squeeze_btn",use_container_width=True):
            if is_premium(): st.session_state.discover_cat="💥 Squeeze Radar"; nav("discover")
            else: nav("pricing")

    st.markdown("<br>",unsafe_allow_html=True)

    # Standard category explorer
    st.markdown('<div class="sec">📈 Browse Stock Categories</div>',unsafe_allow_html=True)
    avail=FREE_CATS if not is_premium() else list(CATEGORIES.keys())
    sel=st.selectbox("Select category",avail,key="dash_cat_sel",label_visibility="collapsed")
    render_category(sel)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE: DISCOVER
# ─────────────────────────────────────────────────────────────────────
def page_discover():
    render_topbar("discover")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    avail_std=FREE_CATS if not is_premium() else list(CATEGORIES.keys())
    avail_comp_free=ALL_COMPOSITE_FREE
    avail_comp_prem=ALL_COMPOSITE_PREM if is_premium() else []
    all_avail=avail_std+avail_comp_free+avail_comp_prem

    # Default to what sidebar set
    default_cat=st.session_state.get("discover_cat",avail_std[0])
    if default_cat not in all_avail: default_cat=all_avail[0]
    default_idx=all_avail.index(default_cat) if default_cat in all_avail else 0

    fc,mc=st.columns([1,4],gap="small")
    with fc:
        st.markdown('<div style="font-size:11px;font-weight:700;color:#2a3a50;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Standard</div>',unsafe_allow_html=True)
        for cat in avail_std:
            if st.button(cat,key=f"disc_std_{cat.replace(' ','_')}",use_container_width=True):
                st.session_state.discover_cat=cat; st.rerun()

        st.markdown('<div style="font-size:11px;font-weight:700;color:#22c55e;text-transform:uppercase;letter-spacing:1px;margin:12px 0 8px;">🎯 Composite (Free)</div>',unsafe_allow_html=True)
        for cat in ALL_COMPOSITE_FREE:
            if st.button(cat,key=f"disc_cf_{cat.replace(' ','_').replace('+','p')}",use_container_width=True):
                st.session_state.discover_cat=cat; st.rerun()

        st.markdown('<div style="font-size:11px;font-weight:700;color:#f59e0b;text-transform:uppercase;letter-spacing:1px;margin:12px 0 8px;">⭐ Composite (Premium)</div>',unsafe_allow_html=True)
        for cat in ALL_COMPOSITE_PREM:
            if st.button(cat,key=f"disc_cp_{cat.replace(' ','_').replace('+','p')}",use_container_width=True):
                if is_premium(): st.session_state.discover_cat=cat; st.rerun()
                else: nav("pricing")

        if not is_premium():
            st.markdown('<div style="margin-top:12px;">',unsafe_allow_html=True)
            if st.button("⚡ Unlock All →",key="disc_upgrade",type="primary",use_container_width=True): nav("pricing")
            st.markdown('</div>',unsafe_allow_html=True)

    with mc:
        sel=st.session_state.get("discover_cat",avail_std[0])
        is_prem_comp=sel in ALL_COMPOSITE_PREM
        st.markdown(f'<div class="sec">{sel} <span class="cnt">{"Premium" if is_prem_comp else "Composite" if sel in COMPOSITE_CATS else "Live"}</span></div>',unsafe_allow_html=True)
        if is_prem_comp and not is_premium():
            render_lock(sel)
        else:
            render_category(sel,show_cat_why=sel in COMPOSITE_CATS)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE: STOCK DETAIL
# ─────────────────────────────────────────────────────────────────────
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
    if not q: st.error(f"Could not load data for {ticker}."); return

    pct=q.get("pct",0); price=q.get("price",0)
    cc="#22c55e" if pct>=0 else "#ef4444"
    ar="▲" if pct>=0 else "▼"
    rc=risk_color(risk)
    sf=(info.get("sf",0) or 0)*100

    st.markdown('<div class="pg">',unsafe_allow_html=True)

    h1,h2,h3=st.columns([3,2,2],gap="small")
    with h1:
        hot_b='<span class="b b-hot" style="margin-right:6px;">🔥 HOT</span>' if hot else ""
        st.markdown(f"""<div>
            {hot_b}<span style="font-family:'JetBrains Mono',monospace;font-size:26px;font-weight:700;color:#60a5fa;">{ticker}</span>
            <div style="font-size:14px;color:#4a6080;margin-top:3px;">{q.get('name','')}</div>
            <div style="font-size:12px;color:#2a3a50;margin-top:2px;">{info.get('sector','N/A')} · {info.get('industry','N/A')}</div>
            <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap;">
                <span class="b b-new">{op}</span>
                <span style="font-size:11px;font-weight:700;color:{rc};">⚡ {risk} Risk</span>
                <span style="font-size:11px;color:#2a3a50;">{conf} confidence</span>
            </div>
        </div>""",unsafe_allow_html=True)
    with h2:
        st.markdown(f"""<div style="text-align:right;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:34px;font-weight:700;color:#e2e8f0;">${price:,.2f}</div>
            <div style="font-size:16px;font-weight:700;color:{cc};">{ar} {abs(pct):.2f}% today</div>
            <div style="font-size:11px;color:#2a3a50;">Prev. ${q.get('prev',0):,.2f}</div>
        </div>""",unsafe_allow_html=True)
    with h3:
        sc_c="#22c55e" if sc>=65 else "#fbbf24" if sc>=40 else "#ef4444"
        sc_bg="#052e16" if sc>=65 else "#1c1000" if sc>=40 else "#1c0000"
        st.markdown(f"""<div style="background:{sc_bg};border:1px solid {sc_c};border-radius:10px;padding:14px;text-align:center;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:36px;font-weight:700;color:{sc_c};">{sc}</div>
            <div style="font-size:10px;color:{sc_c};text-transform:uppercase;letter-spacing:1px;margin-top:2px;">StockWins Score</div>
            <div style="font-size:11px;color:#2a3a50;margin-top:4px;">{op}</div>
        </div>""",unsafe_allow_html=True)

    st.divider()

    mc_v=info.get("mktcap",0)
    mc_s=f"${mc_v/1e12:.2f}T" if mc_v>=1e12 else f"${mc_v/1e9:.2f}B" if mc_v>=1e9 else f"${mc_v/1e6:.0f}M" if mc_v else "N/A"
    items=[("Open",f"${q.get('open',0):,.2f}"),("High",f"${q.get('high',0):,.2f}"),
           ("Low",f"${q.get('low',0):,.2f}"),("Volume",f"{q.get('volume',0)/1e6:.2f}M"),
           ("Mkt Cap",mc_s),("52W High",f"${info.get('hi52',0):,.2f}"),
           ("52W Low",f"${info.get('lo52',0):,.2f}"),("Beta",f"{info.get('beta','N/A')}"),
           ("P/E",f"{info.get('pe','N/A')}"),("Short Float",f"{sf:.1f}%")]
    scols=st.columns(5)
    for i,(l,v) in enumerate(items):
        with scols[i%5]:
            st.markdown(f'<div class="stat" style="margin-bottom:8px;"><div class="stat-l">{l}</div><div style="font-family:\'JetBrains Mono\',monospace;font-size:14px;font-weight:700;color:#e2e8f0;">{v}</div></div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    cc_col,ci_col=st.columns([3,2],gap="small")
    with cc_col:
        st.markdown('<div class="sec" style="font-size:13px;">📈 Price Chart</div>',unsafe_allow_html=True)
        if df is not None and len(df)>1:
            cdf=df[["datetime","close"]].copy().rename(columns={"datetime":"Date","close":"Price"}).set_index("Date")
            st.line_chart(cdf,color="#2563eb")
        else:
            st.info("Chart data unavailable.")
        if bd:
            st.markdown('<div class="sec" style="font-size:13px;margin-top:12px;">Score Breakdown</div>',unsafe_allow_html=True)
            if is_premium():
                for comp,pts in bd.items():
                    c_="#22c55e" if pts>=12 else "#fbbf24" if pts>=6 else "#ef4444"
                    st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:5px;">
                        <div style="width:80px;font-size:11px;color:#3a5068;">{comp}</div>
                        <div style="flex:1;background:#111c2e;border-radius:3px;height:5px;"><div style="background:{c_};width:{pts}%;height:5px;border-radius:3px;"></div></div>
                        <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:{c_};width:24px;text-align:right;">{pts}</div>
                    </div>""",unsafe_allow_html=True)
            else:
                st.markdown('<div style="background:#0a1020;border:1px solid #854d0e;border-radius:6px;padding:10px;font-size:12px;color:#f59e0b;">🔒 Score breakdown is Premium only.</div>',unsafe_allow_html=True)

    with ci_col:
        st.markdown('<div class="sec" style="font-size:13px;">💡 Plain-English Insights</div>',unsafe_allow_html=True)
        for lbl,txt,s,conf in ig[:6]: render_ins(lbl,txt,s,conf)
        if not ig: st.info("No indicators available.")

        st.markdown('<div class="sec" style="font-size:13px;margin-top:12px;">📡 Social Sentiment</div>',unsafe_allow_html=True)
        bull=sent.get("bull",50)
        st.markdown(f"""<div class="sw-card" style="padding:12px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:7px;">
                <span style="font-size:12px;font-weight:700;color:#22c55e;">🟢 Bullish {bull}%</span>
                <span style="font-size:12px;font-weight:700;color:#ef4444;">🔴 Bearish {100-bull}%</span>
            </div>
            <div style="background:#111c2e;border-radius:5px;height:8px;overflow:hidden;">
                <div style="background:linear-gradient(90deg,#22c55e,#16a34a);width:{bull}%;height:8px;"></div>
            </div>
            <div style="font-size:11px;color:#2a3a50;margin-top:7px;">👥 {sent.get('wl',0):,} watching · {sent.get('msgs',0)} recent posts</div>
        </div>""",unsafe_allow_html=True)

    # Why flagged
    st.markdown("<br>",unsafe_allow_html=True)
    st.markdown('<div class="sec" style="font-size:13px;">🎯 Why This Stock Is On Your Radar</div>',unsafe_allow_html=True)
    reasons=[]
    if sc>=70: reasons.append(("Strong multi-factor signal — momentum, trend, MACD, and volume all align","bull"))
    if sent.get("bull",50)>=65: reasons.append((f"{sent['bull']}% of StockTwits traders are bullish right now","bull"))
    if sf>=20: reasons.append((f"{sf:.0f}% of shares are sold short — forced buying could accelerate a squeeze","bull"))
    if hot: reasons.append(("Currently trending on StockTwits Hot list","bull"))
    for lbl,_,s_,_ in ig[:4]: reasons.append((lbl,s_))
    rc2=st.columns(2)
    for i,(r,s_) in enumerate(reasons[:6]):
        em="🟢" if s_=="bull" else "🔴" if s_=="bear" else "⚪"
        with rc2[i%2]:
            st.markdown(f'<div style="background:#0a1020;border:1px solid #111c2e;border-radius:6px;padding:9px 13px;margin-bottom:5px;font-size:12px;color:#3a5068;">{em} {r}</div>',unsafe_allow_html=True)

    # Related
    sector=info.get("sector","N/A")
    if sector!="N/A":
        st.markdown(f'<div class="sec" style="font-size:13px;margin-top:12px;">🔗 Related — {sector}</div>',unsafe_allow_html=True)
        all_t=list(set([t for tl in CATEGORIES.values() for t in tl]))
        related=[rt for rt in all_t if rt!=ticker and yf_fund(rt).get("sector")==sector][:5]
        if related:
            rcols=st.columns(len(related))
            for col,rt in zip(rcols,related):
                rq=get_quote(rt)
                if rq:
                    rc_="#22c55e" if rq["pct"]>=0 else "#ef4444"
                    col.markdown(f'<div class="stat"><div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;font-weight:700;color:#60a5fa;">{rt}</div><div style="font-family:\'JetBrains Mono\',monospace;font-size:13px;font-weight:700;color:#e2e8f0;">${rq["price"]:,.2f}</div><div style="font-size:11px;font-weight:700;color:{rc_};">{"▲" if rq["pct"]>=0 else "▼"}{abs(rq["pct"]):.2f}%</div></div>',unsafe_allow_html=True)
                    if col.button("View",key=f"rel_{rt}_detail",use_container_width=True):
                        st.session_state.detail_ticker=rt; st.session_state.detail_data={}; st.rerun()

    if info.get("desc"):
        with st.expander(f"About {q.get('name',ticker)}"):
            st.markdown(f'<div style="font-size:13px;color:#3a5068;line-height:1.7;">{info["desc"]}</div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    wl=st.session_state.watchlist; in_wl=ticker in wl
    wb1,wb2,_=st.columns([1,1,2])
    with wb1:
        if st.button("✅ Remove from Watchlist" if in_wl else "➕ Add to Watchlist",key="det_wl",type="primary",use_container_width=True):
            if in_wl: wl.remove(ticker)
            else:     wl.append(ticker)
            st.rerun()
    with wb2:
        if st.button("🔔 Set Alert",key="det_alert",use_container_width=True):
            st.session_state.alerts.append({"ticker":ticker,"price":price,"type":"Price Alert","active":True})
            st.success(f"Alert set for {ticker}")

    st.markdown('<div class="disc">⚠️ For educational purposes only. StockWins Score is a data-based metric, not a buy/sell recommendation. Trading involves risk.</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE: BI ANALYTICS
# ─────────────────────────────────────────────────────────────────────
def page_bi():
    render_topbar("bi_dashboard")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec">📊 BI Analytics Dashboard <span class="cnt">Live Intelligence</span></div>',unsafe_allow_html=True)

    with st.spinner("Loading analytics..."):
        movers=get_bi_movers(); secs=get_sectors(); idx=get_indexes(); hot=st_hot()

    gainers=sorted(movers,key=lambda x:x["pct"],reverse=True)
    losers=sorted(movers,key=lambda x:x["pct"])
    vol_ldrs=sorted(movers,key=lambda x:x["vr"],reverse=True)
    top_g=gainers[0] if gainers else {}; top_l=losers[0] if losers else {}; top_v=vol_ldrs[0] if vol_ldrs else {}
    bull_sec=max(secs,key=secs.get) if secs else "N/A"; bear_sec=min(secs,key=secs.get) if secs else "N/A"

    # Summary widgets
    sw=st.columns(5)
    for col,(v,l,c) in zip(sw,[
        (top_g.get("t","—"),f"Top Gainer +{top_g.get('pct',0):.1f}%","#22c55e"),
        (top_l.get("t","—"),f"Top Loser {top_l.get('pct',0):.1f}%","#ef4444"),
        (top_v.get("t","—"),f"Vol King {top_v.get('vr',0):.1f}x","#60a5fa"),
        (bull_sec,f"Best Sector +{secs.get(bull_sec,0):.1f}%","#22c55e"),
        (bear_sec,f"Weak Sector {secs.get(bear_sec,0):.1f}%","#ef4444"),
    ]):
        col.markdown(f'<div class="stat"><div style="font-family:\'JetBrains Mono\',monospace;font-size:16px;font-weight:700;color:{c};">{v}</div><div class="stat-l">{l}</div></div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    # Composite Opportunity Heatmap (unique BI feature)
    st.markdown('<div class="sec">🎯 Composite Opportunity Matrix <span class="cnt">StockWins Exclusive</span></div>',unsafe_allow_html=True)
    st.caption("Cross-reference of signal types across our broad universe — green = strong composite signal")
    matrix_tickers=["NVDA","TSLA","AMD","AAPL","MSTR","GME","AMC","PLTR","META","MSFT"]
    signal_types=["Momentum","Trend","Volume","Sentiment","Squeeze"]
    matrix_data={}
    prog=st.progress(0,"Computing opportunity matrix...")
    for i,t in enumerate(matrix_tickers):
        prog.progress((i+1)/len(matrix_tickers),f"Analyzing {t}...")
        df=get_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
        _,bd,_,_,_=compute_scores(df,info,sent)
        matrix_data[t]=bd
    prog.empty()

    # Render matrix
    hdr_cols=st.columns([1]+[1]*len(signal_types))
    hdr_cols[0].markdown('<div style="font-size:10px;color:#2a3a50;text-align:center;">TICKER</div>',unsafe_allow_html=True)
    for i,sig in enumerate(signal_types):
        hdr_cols[i+1].markdown(f'<div style="font-size:10px;color:#2a3a50;text-align:center;">{sig.upper()}</div>',unsafe_allow_html=True)

    max_vals={"Momentum":25,"Trend":20,"Volume":15,"Sentiment":15,"Squeeze":10}
    for t in matrix_tickers:
        row_cols=st.columns([1]+[1]*len(signal_types))
        row_cols[0].markdown(f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;font-weight:700;color:#60a5fa;text-align:center;padding:6px 0;">{t}</div>',unsafe_allow_html=True)
        bd=matrix_data.get(t,{})
        for i,sig in enumerate(signal_types):
            pts=bd.get(sig,0); mx=max_vals.get(sig,10); pct_=pts/mx if mx>0 else 0
            bg="#052e16" if pct_>=0.8 else "#0a2010" if pct_>=0.6 else "#151000" if pct_>=0.3 else "#0e1525"
            tc="#4ade80" if pct_>=0.8 else "#86efac" if pct_>=0.6 else "#fbbf24" if pct_>=0.3 else "#506070"
            row_cols[i+1].markdown(f'<div style="background:{bg};border-radius:4px;padding:6px;text-align:center;font-family:\'JetBrains Mono\',monospace;font-size:11px;font-weight:700;color:{tc};">{pts}</div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)

    tabs=st.tabs(["📈 Leaderboards","🗺️ Sectors","📡 Social","🔊 Volume","📋 Summary"])
    with tabs[0]:
        lc1,lc2,lc3=st.columns(3,gap="small")
        with lc1:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#22c55e;margin-bottom:8px;">🏆 Top Gainers</div>',unsafe_allow_html=True)
            for m in gainers[:10]: st.markdown(f'<div class="mv"><span style="font-family:\'JetBrains Mono\',monospace;font-weight:700;color:#60a5fa;font-size:12px;">{m["t"]}</span><span style="color:#3a5068;font-size:11px;">${m["price"]:,.2f}</span><span style="color:#22c55e;font-weight:700;font-size:12px;">▲{m["pct"]:.2f}%</span></div>',unsafe_allow_html=True)
        with lc2:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#ef4444;margin-bottom:8px;">📉 Top Losers</div>',unsafe_allow_html=True)
            for m in losers[:10]: st.markdown(f'<div class="mv"><span style="font-family:\'JetBrains Mono\',monospace;font-weight:700;color:#60a5fa;font-size:12px;">{m["t"]}</span><span style="color:#3a5068;font-size:11px;">${m["price"]:,.2f}</span><span style="color:#ef4444;font-weight:700;font-size:12px;">▼{abs(m["pct"]):.2f}%</span></div>',unsafe_allow_html=True)
        with lc3:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#60a5fa;margin-bottom:8px;">🔊 Volume Leaders</div>',unsafe_allow_html=True)
            for m in vol_ldrs[:10]:
                c="#ef4444" if m["vr"]>=3 else "#fbbf24" if m["vr"]>=2 else "#60a5fa"
                st.markdown(f'<div class="mv"><span style="font-family:\'JetBrains Mono\',monospace;font-weight:700;color:#60a5fa;font-size:12px;">{m["t"]}</span><span style="color:#3a5068;font-size:11px;">{m["vol"]/1e6:.1f}M</span><span style="font-weight:700;font-size:12px;color:{c};">{m["vr"]:.1f}x</span></div>',unsafe_allow_html=True)
    with tabs[1]:
        sec_sorted=sorted(secs.items(),key=lambda x:x[1],reverse=True)
        for sec,chg in sec_sorted:
            c="#22c55e" if chg>0 else "#ef4444"; bar=min(abs(chg)*8,100)
            st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:7px;">
                <div style="width:100px;font-size:11px;color:#4a6080;">{sec}</div>
                <div style="flex:1;background:#111c2e;border-radius:3px;height:18px;overflow:hidden;">
                    <div style="background:{"#052e16" if chg>=0 else "#1c0000"};width:{bar}%;height:18px;display:flex;align-items:center;padding-left:8px;">
                        <span style="color:{c};font-size:11px;font-weight:700;">{"▲" if chg>=0 else "▼"}{abs(chg):.2f}%</span>
                    </div>
                </div>
            </div>""",unsafe_allow_html=True)
    with tabs[2]:
        sc1,sc2=st.columns(2)
        with sc1:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#c9d3e0;margin-bottom:8px;">🔥 Trending on StockTwits</div>',unsafe_allow_html=True)
            for i,t in enumerate(hot[:8],1):
                s=st_sent(t); bc="#22c55e" if s["bull"]>=60 else "#ef4444" if s["bull"]<40 else "#94a3b8"
                st.markdown(f'<div class="mv"><span style="color:#2a3a50;font-size:10px;">#{i}</span> <span style="font-family:\'JetBrains Mono\',monospace;font-weight:700;color:#60a5fa;font-size:12px;">{t}</span> <span style="color:#2a3a50;font-size:11px;">{s.get("wl",0):,}</span> <span style="color:{bc};font-weight:700;font-size:12px;">{s["bull"]}% bull</span></div>',unsafe_allow_html=True)
        with sc2:
            st.markdown('<div style="font-size:12px;font-weight:700;color:#c9d3e0;margin-bottom:8px;">Sentiment Leaderboard</div>',unsafe_allow_html=True)
            targets=["NVDA","TSLA","AMD","AAPL","MSTR","PLTR","GME","META"]
            discussed=sorted([(t,st_sent(t)) for t in targets],key=lambda x:x[1].get("wl",0),reverse=True)
            for t,s in discussed[:6]:
                bc="#22c55e" if s["bull"]>=60 else "#ef4444" if s["bull"]<40 else "#94a3b8"
                st.markdown(f'<div class="mv"><span style="font-family:\'JetBrains Mono\',monospace;font-weight:700;color:#60a5fa;font-size:12px;">{t}</span> <span style="color:#2a3a50;font-size:11px;">{s.get("wl",0):,} watching</span> <span style="color:{bc};font-weight:700;font-size:12px;">{s["bull"]}% bull</span></div>',unsafe_allow_html=True)
    with tabs[3]:
        surge=[m for m in movers if m["vr"]>=1.5]; surge.sort(key=lambda x:x["vr"],reverse=True)
        if surge:
            st.dataframe(pd.DataFrame([{"Ticker":m["t"],"Price":f"${m['price']:,.2f}","Day Change":f"{m['pct']:+.2f}%","Volume":f"{m['vol']/1e6:.2f}M","Vol Ratio":f"{m['vr']:.1f}x avg"} for m in surge]),use_container_width=True,hide_index=True)
        else: st.info("No significant volume surges right now.")
    with tabs[4]:
        avg_pct=sum(m["pct"] for m in movers)/len(movers) if movers else 0
        bull_s=[s for s,c in secs.items() if c>0.5]; bear_s=[s for s,c in secs.items() if c<-0.5]
        sc_,sc2_=st.columns(2)
        with sc_:
            st.markdown(f"""<div class="sw-card"><div style="font-size:13px;font-weight:700;color:#c9d3e0;margin-bottom:10px;">Market Overview</div>
                <div class="mv"><span style="color:#3a5068;">Overall Sentiment</span><span style="color:{"#22c55e" if avg_pct>0 else "#ef4444"};font-weight:700;">{"Bullish" if avg_pct>0.3 else "Bearish" if avg_pct<-0.3 else "Neutral"}</span></div>
                <div class="mv"><span style="color:#3a5068;">Avg Stock Move</span><span style="color:{"#22c55e" if avg_pct>0 else "#ef4444"};font-weight:700;">{avg_pct:+.2f}%</span></div>
                <div class="mv"><span style="color:#3a5068;">Bullish Sectors</span><span style="color:#22c55e;font-weight:700;">{len(bull_s)}/10</span></div>
                <div class="mv"><span style="color:#3a5068;">Bearish Sectors</span><span style="color:#ef4444;font-weight:700;">{len(bear_s)}/10</span></div>
                <div class="mv"><span style="color:#3a5068;">Volume Surges</span><span style="color:#60a5fa;font-weight:700;">{len([m for m in movers if m["vr"]>=2])} stocks</span></div>
            </div>""",unsafe_allow_html=True)
        with sc2_:
            st.markdown(f"""<div class="sw-card"><div style="font-size:13px;font-weight:700;color:#c9d3e0;margin-bottom:10px;">Key Highlights</div>
                <div style="font-size:12px;color:#3a5068;line-height:2.2;">
                🟢 <b style="color:#4a6080;">Best sectors:</b> {', '.join(bull_s[:3]) if bull_s else 'None'}<br>
                🔴 <b style="color:#4a6080;">Weak sectors:</b> {', '.join(bear_s[:3]) if bear_s else 'None'}<br>
                🔥 <b style="color:#4a6080;">Social buzz:</b> {', '.join(hot[:5])}<br>
                🔊 <b style="color:#4a6080;">Volume king:</b> {top_v.get('t','—')} ({top_v.get('vr',0):.1f}x avg)<br>
                📈 <b style="color:#4a6080;">Top gainer:</b> {top_g.get('t','—')} (+{top_g.get('pct',0):.2f}%)
                </div>
            </div>""",unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE: WATCHLIST
# ─────────────────────────────────────────────────────────────────────
def page_watchlist():
    render_topbar("watchlist")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec">⭐ My Watchlist</div>',unsafe_allow_html=True)
    wl=st.session_state.watchlist
    if not wl:
        st.markdown('<div class="sw-card" style="text-align:center;padding:48px;"><div style="font-size:30px;margin-bottom:10px;">📋</div><div style="font-size:15px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">Watchlist is empty</div><div style="font-size:13px;color:#3a5068;">Browse categories and click ➕ to add stocks.</div></div>',unsafe_allow_html=True)
        if st.button("Browse Stocks →",key="wl_browse",type="primary"): nav("dashboard")
        st.markdown('</div>',unsafe_allow_html=True); return
    st.caption(f"{len(wl)} stocks in watchlist")
    rows=[]; prog=st.progress(0,"Loading watchlist...")
    for i,t in enumerate(wl):
        prog.progress((i+1)/len(wl),f"Loading {t}...")
        q=get_quote(t); df=get_ohlcv(t,30); info=yf_fund(t); sent=st_sent(t)
        sc,_,op,risk,_=compute_scores(df,info,sent)
        if q: rows.append({"Ticker":t,"Name":q.get("name","")[:20],"Price":f"${q['price']:,.2f}",
                           "Change":f"{q['pct']:+.2f}%","SW Score":sc,"Opportunity":op,
                           "Risk":risk,"Short Float":f"{(info.get('sf',0) or 0)*100:.1f}%",
                           "Bull Sent":f"{sent.get('bull',50)}%","Sector":info.get("sector","N/A")})
    prog.empty()
    if rows:
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        if is_premium():
            st.markdown("<br>",unsafe_allow_html=True)
            st.markdown('<div class="sec" style="font-size:13px;">Watchlist Analytics</div>',unsafe_allow_html=True)
            wc=st.columns(4)
            avg_sc=sum(r["SW Score"] for r in rows)/len(rows)
            pos=sum(1 for r in rows if "+" in r["Change"])
            high_r=sum(1 for r in rows if r["Risk"] in ("High","Very High"))
            avg_b=sum(int(r["Bull Sent"].replace("%","")) for r in rows)/len(rows)
            for col,(v,l) in zip(wc,[(f"{avg_sc:.0f}","Avg SW Score"),(f"{pos}/{len(rows)}","In the Green"),(f"{high_r}","High Risk"),(f"{avg_b:.0f}%","Avg Bull Sent.")]):
                col.markdown(f'<div class="stat"><div class="stat-v">{v}</div><div class="stat-l">{l}</div></div>',unsafe_allow_html=True)
    if st.button("🗑️ Clear Watchlist",key="wl_clear"): st.session_state.watchlist=[]; st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE: SCREENER
# ─────────────────────────────────────────────────────────────────────
def page_screener():
    render_topbar("screener")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec">🔍 Smart Stock Screener</div>',unsafe_allow_html=True)
    if not is_premium(): render_lock("Advanced Stock Screener"); st.markdown('</div>',unsafe_allow_html=True); return
    with st.expander("⚙️ Screener Filters",expanded=True):
        c1,c2,c3,c4=st.columns(4)
        with c1: min_sc=st.slider("Min SW Score",0,100,40); min_rsi=st.slider("Min RSI",0,100,20)
        with c2: max_rsi=st.slider("Max RSI",0,100,80); min_sf=st.slider("Min Short Float %",0,50,0)
        with c3:
            req_bull=st.checkbox("MACD Bullish only"); req_above=st.checkbox("Above 20-day MA")
            req_vol=st.checkbox("Volume spike >1.5x"); req_hot=st.checkbox("StockTwits trending")
        with c4:
            sel_cats=st.multiselect("Categories",list(CATEGORIES.keys()),default=["💻 Tech","🤖 AI"])
    sn,sb=st.columns([3,1])
    with sn: scr_name=st.text_input("Save this screener as...",placeholder="My Growth Screen",label_visibility="visible")
    with sb:
        if st.button("💾 Save",key="scr_save",use_container_width=True) and scr_name:
            st.session_state.saved_screeners.append({"name":scr_name,"cats":sel_cats,"min_sc":min_sc})
            st.success("Saved!")
    if st.session_state.saved_screeners:
        st.caption("Saved: "+", ".join([s["name"] for s in st.session_state.saved_screeners]))
    if st.button("🔍 Run Screener",key="scr_run",type="primary",use_container_width=True):
        hot_list=st_hot() if req_hot else []
        universe=list(set([t for c in sel_cats for t in CATEGORIES.get(c,[])]))[:30]
        results=[]; prog=st.progress(0,"Screening...")
        for i,t in enumerate(universe):
            prog.progress((i+1)/len(universe),f"Screening {t}...")
            if req_hot and t not in hot_list: continue
            q=get_quote(t); df=get_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            sc,_,op,risk,_=compute_scores(df,info,sent)
            if df is None or len(df)<20: continue
            try:
                rsi=ta.momentum.RSIIndicator(df["close"].copy(),14).rsi().iloc[-1]
                ma20=df["close"].rolling(20).mean().iloc[-1]
                mac=ta.trend.MACD(df["close"].copy()); mv=mac.macd().iloc[-1]; ms=mac.macd_signal().iloc[-1]
                price=df["close"].iloc[-1]
                avg_v=df["volume"].rolling(20).mean().iloc[-1]; cur_v=df["volume"].iloc[-1]
                sf=(info.get("sf",0) or 0)*100
                if sc<min_sc: continue
                if pd.notna(rsi) and (rsi<min_rsi or rsi>max_rsi): continue
                if sf<min_sf: continue
                if req_bull and pd.notna(mv) and mv<ms: continue
                if req_above and pd.notna(ma20) and price<ma20: continue
                if req_vol and pd.notna(avg_v) and avg_v>0 and cur_v<avg_v*1.5: continue
                results.append({"Ticker":t,"Price":f"${price:,.2f}" if q else "N/A",
                                "RSI":round(rsi,1) if pd.notna(rsi) else "N/A","SW Score":sc,
                                "Opportunity":op,"Risk":risk,"Short Float":f"{sf:.1f}%",
                                "MACD":"Bullish" if (pd.notna(mv) and mv>ms) else "Bearish",
                                "vs MA20":"Above" if price>ma20 else "Below",
                                "Vol Ratio":f"{cur_v/avg_v:.1f}x" if pd.notna(avg_v) and avg_v>0 else "N/A"})
            except: continue
        prog.empty()
        if results:
            st.success(f"✅ {len(results)} stocks passed your filters!")
            st.dataframe(pd.DataFrame(results).sort_values("SW Score",ascending=False),use_container_width=True,hide_index=True)
        else: st.info("No stocks matched. Try relaxing the filters.")
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE: PRICING
# ─────────────────────────────────────────────────────────────────────
def page_pricing():
    render_topbar("pricing")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec">💰 Plans & Pricing</div>',unsafe_allow_html=True)
    p1,p2,p3=st.columns([1,1.1,1],gap="small")
    with p1:
        st.markdown("""<div class="pc"><div style="font-size:15px;font-weight:700;color:#c9d3e0;">Free</div>
            <div class="pc-price">$0</div><div style="font-size:11px;color:#2a3a50;margin-bottom:14px;">forever</div>
            <hr style="border-color:#111c2e;margin:14px 0;">
            <div style="font-size:12px;color:#3a5068;line-height:2.2;">
            ✅ Market overview & indexes<br>✅ 5 stock categories<br>✅ StockTwits hot list<br>
            ✅ Basic RSI & MACD signals<br>✅ Plain-English insights<br>✅ Watchlist (10 stocks)<br>
            ✅ 3 composite categories (free)<br>❌ Short squeeze scanner<br>
            ❌ Advanced screener<br>❌ 3 premium composite cats<br>❌ Score breakdowns</div></div>""",unsafe_allow_html=True)
        if not is_authed():
            if st.button("Get Started Free",key="price_free",use_container_width=True): nav("signup")
    with p2:
        st.markdown("""<div class="pc-feat"><div style="background:#2563eb;color:white;font-size:9px;font-weight:700;padding:3px 10px;border-radius:20px;display:inline-block;margin-bottom:8px;letter-spacing:1.5px;">⭐ MOST POPULAR</div>
            <div style="font-size:15px;font-weight:700;color:#c9d3e0;">Premium Monthly</div>
            <div class="pc-price">$29</div><div style="font-size:11px;color:#2a3a50;margin-bottom:14px;">per month · cancel anytime</div>
            <hr style="border-color:#111c2e;margin:14px 0;">
            <div style="font-size:12px;color:#3a5068;line-height:2.2;">
            ✅ Everything in Free<br>✅ All 13+ stock categories<br>✅ All 6 composite categories<br>
            ✅ Short squeeze scanner<br>✅ Advanced screener<br>✅ Full BI analytics<br>
            ✅ Score breakdowns<br>✅ Volume surge alerts<br>✅ Unlimited watchlist<br>
            ✅ Watchlist analytics<br>✅ Saved screeners</div></div>""",unsafe_allow_html=True)
        if st.button("🚀 Go Premium →",key="price_prem",type="primary",use_container_width=True):
            st.info("💳 Payment processing coming soon. Contact support@stockwins.com to upgrade.")
    with p3:
        st.markdown("""<div class="pc"><div style="background:linear-gradient(90deg,#854d0e,#d97706);color:white;font-size:9px;font-weight:700;padding:3px 10px;border-radius:20px;display:inline-block;margin-bottom:4px;">BEST VALUE</div>
            <div style="font-size:15px;font-weight:700;color:#c9d3e0;">Annual Plan</div>
            <div class="pc-price">$199</div><div style="font-size:11px;color:#2a3a50;margin-bottom:14px;">per year · save 43%</div>
            <hr style="border-color:#111c2e;margin:14px 0;">
            <div style="font-size:12px;color:#3a5068;line-height:2.2;">
            ✅ Everything in Premium<br>✅ Priority support<br>✅ Early feature access<br>
            ✅ Export to CSV<br>✅ Custom alerts<br>✅ API access (Q3 2026)<br>
            ✅ Backtesting (coming)<br>✅ Portfolio tracker (coming)</div></div>""",unsafe_allow_html=True)
        if st.button("Get Annual →",key="price_annual",use_container_width=True):
            st.info("💳 Payment processing coming soon!")
    st.markdown('<div class="disc">⚠️ Educational platform only. Not financial advice. Trading involves risk.</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE: SETTINGS
# ─────────────────────────────────────────────────────────────────────
def page_settings():
    render_topbar()
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec">⚙️ Account Settings</div>',unsafe_allow_html=True)
    db_user=get_db_user(); email=st.session_state.user["email"] if is_authed() else ""
    tabs=st.tabs(["👤 Profile","🔐 Security","🔔 Alerts","📊 Subscription"])
    with tabs[0]:
        with st.form("pf"):
            new_name=st.text_input("Display Name",value=st.session_state.user.get("name",""))
            st.text_input("Email (cannot change)",value=email,disabled=True)
            verified=db_user.get("verified",False)
            if not verified: st.warning("⚠️ Email not verified.")
            else: st.markdown('<span style="font-size:12px;color:#22c55e;">✅ Email verified</span>',unsafe_allow_html=True)
            if st.form_submit_button("Save Changes",type="primary") and new_name:
                st.session_state.user["name"]=new_name
                if email in st.session_state.users_db: st.session_state.users_db[email]["name"]=new_name
                st.success("✅ Profile updated!")
    with tabs[1]:
        with st.form("pwf"):
            cp=st.text_input("Current Password",type="password")
            np=st.text_input("New Password",type="password")
            np2=st.text_input("Confirm New",type="password")
            if st.form_submit_button("Update Password",type="primary"):
                if hp(cp)!=db_user.get("pw",""): st.error("Current password incorrect.")
                elif np!=np2: st.error("New passwords don't match.")
                elif len(np)<6: st.error("Must be 6+ characters.")
                else: st.session_state.users_db[email]["pw"]=hp(np); st.success("✅ Password updated!")
        if st.button("🚪 Logout",key="settings_logout",use_container_width=False): logout()
    with tabs[2]:
        with st.form("af"):
            ac1,ac2,ac3=st.columns(3)
            with ac1: at=st.text_input("Ticker",placeholder="AAPL").upper()
            with ac2: ap=st.number_input("Alert Price",value=100.0,min_value=0.01)
            with ac3: atype=st.selectbox("Type",["Price Above","Price Below","% Move Up","% Move Down"])
            if st.form_submit_button("➕ Add Alert",type="primary") and at:
                st.session_state.alerts.append({"ticker":at,"price":ap,"type":atype,"active":True})
                st.success(f"Alert set: {at} {atype} ${ap:.2f}")
        if st.session_state.alerts:
            for i,a in enumerate(st.session_state.alerts):
                ac1_,ac2_=st.columns([4,1])
                with ac1_: st.markdown(f'<div class="sw-card" style="padding:10px 14px;margin-bottom:4px;"><span style="font-family:\'JetBrains Mono\',monospace;font-weight:700;color:#60a5fa;">{a["ticker"]}</span> <span style="font-size:12px;color:#3a5068;">{a["type"]} ${a["price"]:.2f}</span></div>',unsafe_allow_html=True)
                with ac2_:
                    if st.button("🗑",key=f"da_{i}"): st.session_state.alerts.pop(i); st.rerun()
        else: st.caption("No active alerts.")
    with tabs[3]:
        role=st.session_state.role
        rl={"free":"Free","premium":"Premium Monthly","admin":"Admin","owner":"Owner"}.get(role,"Free")
        rc_={"free":"#506070","premium":"#a78bfa","admin":"#60a5fa","owner":"#f59e0b"}.get(role,"#506070")
        st.markdown(f"""<div class="sw-card card-blue"><div style="font-size:15px;font-weight:800;color:#e2e8f0;">Current Plan: <span style="color:{rc_};">{rl}</span></div><div style="font-size:12px;color:#3a5068;margin-top:4px;">Member since {db_user.get('joined','N/A')}</div></div>""",unsafe_allow_html=True)
        if not is_premium():
            uc1,uc2=st.columns(2)
            with uc1:
                if st.button("🚀 Upgrade Monthly ($29/mo)",key="set_prem",type="primary",use_container_width=True): nav("pricing")
            with uc2:
                if st.button("💰 Get Annual ($199/yr)",key="set_annual",use_container_width=True): nav("pricing")
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE: ADMIN
# ─────────────────────────────────────────────────────────────────────
def page_admin():
    if not is_admin(): st.error("Access denied."); return
    render_topbar("admin")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec">🛠️ Admin Panel <span class="cnt">{"👑 Owner" if is_owner() else "🛡 Admin"}</span></div>',unsafe_allow_html=True)
    tabs=st.tabs(["📊 Overview","👥 Users","🔑 API Settings","📈 Analytics"])
    with tabs[0]:
        ss=st.session_state.site_stats
        oc=st.columns(5)
        for col,(v,l,c) in zip(oc,[(ss["total_signups"],"Total Signups","#60a5fa"),(ss["premium_users"],"Premium Users","#a78bfa"),(ss["daily_active"],"Daily Active","#22c55e"),(f"{ss['conversion_rate']:.1f}%","Conversion Rate","#fbbf24"),(len(st.session_state.users_db),"Accounts","#94a3b8")]):
            col.markdown(f'<div class="stat"><div style="font-family:\'JetBrains Mono\',monospace;font-size:20px;font-weight:700;color:{c};">{v}</div><div class="stat-l">{l}</div></div>',unsafe_allow_html=True)
        st.markdown("<br>",unsafe_allow_html=True)
        hc=st.columns(3)
        key_set=bool(get_key())
        for col,(name,status,note) in zip(hc,[("Yahoo Finance","✅ Online","Free · No key needed"),("StockTwits","✅ Online","Public API · Free"),("Twelve Data",f"{'✅ Configured' if key_set else '⚠️ Not Set'}","Optional · Premium quality")]):
            c_="#22c55e" if "✅" in status else "#fbbf24"
            col.markdown(f'<div class="sw-card"><div style="font-size:12px;font-weight:700;color:#c9d3e0;margin-bottom:4px;">{name}</div><div style="font-size:12px;font-weight:700;color:{c_};">{status}</div><div style="font-size:11px;color:#2a3a50;margin-top:3px;">{note}</div></div>',unsafe_allow_html=True)
    with tabs[1]:
        db=st.session_state.users_db
        for email,u in list(db.items()):
            role=u["role"]
            uc1,uc2,uc3,uc4=st.columns([3,1,2,1])
            with uc1: st.markdown(f'<div style="padding:8px 0;"><div style="font-size:13px;font-weight:600;color:#c9d3e0;">{u["name"]}</div><div style="font-size:11px;color:#2a3a50;">{"✅" if u.get("verified") else "⚠️"} {email}</div></div>',unsafe_allow_html=True)
            with uc2: st.markdown(f'<div style="padding:10px 0;"><span style="background:#06163a;color:#60a5fa;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;">{role.upper()}</span></div>',unsafe_allow_html=True)
            with uc3:
                if is_owner() and role!="owner":
                    new_role=st.selectbox("Role",["free","premium","admin"],index=["free","premium","admin"].index(role) if role in ["free","premium","admin"] else 0,key=f"role_{email}",label_visibility="collapsed")
                    if st.button("Update",key=f"upd_{email}",use_container_width=True):
                        st.session_state.users_db[email]["role"]=new_role; st.rerun()
            with uc4:
                if is_owner() and email!=st.session_state.user["email"]:
                    if st.button("🗑",key=f"del_{email}",use_container_width=True):
                        del st.session_state.users_db[email]; st.rerun()
            st.markdown('<div style="border-bottom:1px solid #0e1525;margin-bottom:4px;"></div>',unsafe_allow_html=True)
    with tabs[2]:
        st.markdown('<div class="sw-card card-green"><div style="font-size:12px;font-weight:700;color:#4ade80;margin-bottom:4px;">✅ Yahoo Finance + StockTwits — Always Active (No Key Needed)</div><div style="font-size:12px;color:#3a5068;">All price, volume, fundamental, and sentiment data works automatically for all users with no configuration required.</div></div>',unsafe_allow_html=True)
        st.markdown('<div class="sec" style="font-size:13px;margin-top:8px;">Twelve Data API (Optional — Admin Only)</div>',unsafe_allow_html=True)
        cur_key=st.session_state.api_override
        masked=f"{'*'*(len(cur_key)-4)}{cur_key[-4:]}" if len(cur_key)>4 else ("Set ✅" if cur_key else "Not set")
        st.markdown(f'<div style="font-size:12px;color:#3a5068;margin-bottom:6px;">Session key: {masked}</div>',unsafe_allow_html=True)
        with st.form("api_form"):
            new_key=st.text_input("Twelve Data API Key (admin only)",type="password",placeholder="Paste key here — never shown to users")
            if st.form_submit_button("Save Key",type="primary"):
                st.session_state.api_override=new_key
                st.success("✅ Key saved for this session. For permanent setup, add TWELVE_DATA_API_KEY to Streamlit Cloud Secrets.")
        if st.button("Clear Key",key="clear_api_key"): st.session_state.api_override=""; st.success("Cleared.")
        st.markdown('<div class="disc">🔒 API keys are stored server-side only. Regular users never see this section. For production, use Streamlit Cloud Secrets (Settings → Secrets).</div>',unsafe_allow_html=True)
    with tabs[3]:
        dates=pd.date_range(end=datetime.now(),periods=30,freq='D')
        signups_data=[random.randint(40,120) for _ in range(30)]
        premium_data=[random.randint(5,25) for _ in range(30)]
        chart_df=pd.DataFrame({"New Signups":signups_data,"Premium Upgrades":premium_data},index=dates)
        st.line_chart(chart_df)
        st.markdown('<div class="disc">📊 Analytics are simulated. In production, connect Mixpanel, PostHog, or your analytics provider.</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────────────
render_sidebar()

page=st.session_state.page
guard={"dashboard","discover","watchlist","screener","bi_dashboard","stock_detail","settings","admin"}
if page in guard and not is_authed():
    page_login()
elif page=="landing":         page_landing()
elif page=="login":           page_login()
elif page=="signup":          page_signup()
elif page=="verify_email":    page_verify()
elif page=="forgot_pw":       page_forgot()
elif page=="pricing":         page_pricing()
elif page=="dashboard":       page_dashboard()
elif page=="discover":        page_discover()
elif page=="watchlist":       page_watchlist()
elif page=="screener":        page_screener()
elif page=="bi_dashboard":    page_bi()
elif page=="stock_detail":    page_detail()
elif page=="settings":        page_settings()
elif page=="admin":
    if is_admin(): page_admin()
    else:          st.error("Access denied."); nav("dashboard")
else:                         page_landing()
