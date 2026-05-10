# ═══════════════════════════════════════════════════════════════
# STOCKWINS v7.0 — Premium Fintech SaaS
# "I trust this. I understand this. I want more."
# ═══════════════════════════════════════════════════════════════

import streamlit as st
import requests, pandas as pd, ta, yfinance as yf
import hashlib, time, random
from datetime import datetime, timedelta

try:
    import io as _io
    import xlsxwriter as _xlsxwriter
    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

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

# ── Module-level DB: persists within the server process across reruns ──
_GLOBAL_USERS_DB: dict = {}

def _get_global_db() -> dict:
    """Returns the shared in-process user database. Seeds from Secrets on first call."""
    global _GLOBAL_USERS_DB
    if not _GLOBAL_USERS_DB:
        _GLOBAL_USERS_DB = _load_seed_accounts()
    return _GLOBAL_USERS_DB

def _save_global_db(db: dict):
    """Sync session users_db back to global store."""
    global _GLOBAL_USERS_DB
    _GLOBAL_USERS_DB = db

# ─────────────────────────────────────────────────────────────
# FILE-BASED PERSISTENCE (alerts + users readable by worker)
# ─────────────────────────────────────────────────────────────
import json as _json, os as _os

ALERTS_DB_PATH = _os.environ.get("ALERTS_DB_PATH", "/tmp/sw_alerts.json")
USERS_DB_PATH  = _os.environ.get("USERS_DB_PATH",  "/tmp/sw_users.json")

def _read_json(path, default=None):
    try:
        with open(path) as f: return _json.load(f)
    except: return default if default is not None else {}

def _write_json(path, data):
    try:
        with open(path, "w") as f: _json.dump(data, f, indent=2, default=str)
    except: pass

def save_alerts_to_file(email, alerts):
    db = _read_json(ALERTS_DB_PATH, {}); db[email] = alerts
    _write_json(ALERTS_DB_PATH, db)

def save_user_to_file(email, user_data):
    db = _read_json(USERS_DB_PATH, {})
    db[email] = {
        "name":             user_data.get("name", ""),
        "role":             user_data.get("role", "free"),
        "telegram_chat_id": user_data.get("telegram_chat_id", ""),
        "watchlist":        user_data.get("watchlist", []),
        "digest_prefs":     user_data.get("digest_prefs", {}),
        "category_alerts":  user_data.get("category_alerts", []),
    }
    _write_json(USERS_DB_PATH, db)

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
# STRIPE PAYMENT PROCESSING
# ─────────────────────────────────────────────────────────────
def _stripe_key():
    try: return st.secrets.get("STRIPE_SECRET_KEY","")
    except: return ""

def stripe_configured():
    return bool(_stripe_key())

def _get_app_url():
    try: return st.secrets.get("APP_URL","https://stockwins.streamlit.app")
    except: return "https://stockwins.streamlit.app"

def create_checkout_session(plan, user_email):
    """Create Stripe Checkout Session. Returns (url, error)."""
    key = _stripe_key()
    if not key:
        return None, "STRIPE_SECRET_KEY not found in Secrets. Add it and reboot the app."

    # Validate library
    try:
        import stripe as _s
    except ImportError:
        return None, "stripe library not installed. Ensure requirements.txt contains 'stripe' and redeploy."

    # Validate key format
    if not (key.startswith("sk_test_") or key.startswith("sk_live_")):
        return None, (f"STRIPE_SECRET_KEY must start with sk_test_ or sk_live_. "
                      f"Got: {key[:12]}... — Make sure it's the Secret Key, not the Publishable Key (pk_test_)")

    # Get and validate price ID
    price_key = "STRIPE_PRICE_MONTHLY" if plan == "premium" else "STRIPE_PRICE_ANNUAL"
    try: price_id = st.secrets.get(price_key, "")
    except: price_id = ""
    if not price_id:
        return None, f"{price_key} not found in Secrets. Add price_xxx ID from Stripe Products page."
    if not price_id.startswith("price_"):
        return None, f"{price_key} must start with 'price_'. Got: {price_id[:30]} — use the Price ID, not a Payment Link URL."

    try:
        _s.api_key = key
        app_url = _get_app_url()
        # Try new-style API first (stripe 5+), fall back to old-style
        try:
            create_fn = _s.checkout.sessions.create
        except AttributeError:
            create_fn = _s.checkout.Session.create
        sess = create_fn(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=user_email,
            client_reference_id=user_email,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{app_url}/?payment=success&sid={{CHECKOUT_SESSION_ID}}&plan={plan}",
            cancel_url=f"{app_url}/?payment=cancelled",
            metadata={"user_email": user_email, "plan": plan},
            subscription_data={"metadata": {"user_email": user_email, "plan": plan}},
            allow_promotion_codes=True,
        )
        return sess.url, None
    except Exception as e:
        # Get the most useful error info regardless of stripe version
        err_type = type(e).__name__
        err_msg  = repr(e)
        # Try to extract user-facing message from Stripe errors
        user_msg = getattr(e, "user_message", None) or getattr(e, "message", None) or str(e)
        if not user_msg:
            user_msg = err_msg
        return None, f"{err_type}: {user_msg}"

def verify_checkout_session(session_id):
    """Verify completed Stripe Checkout. Returns (plan, email) or (None, error)."""
    key = _stripe_key()
    if not key: return None,"Stripe not configured"
    try:
        import stripe as _s
        _s.api_key = key
        sess = _s.checkout.sessions.retrieve(session_id)
        if sess.payment_status == "paid":
            plan  = sess.metadata.get("plan","premium")
            email = sess.customer_email or sess.client_reference_id or ""
            return plan, email
        return None, f"Payment status: {sess.payment_status}"
    except Exception as e:
        return None, f"Stripe error: {e}"

def create_portal_session(user_email):
    """Create Stripe Customer Portal session. Returns (url, error)."""
    key = _stripe_key()
    if not key: return None,"Stripe not configured"
    try:
        import stripe as _s
        _s.api_key = key
        customers = _s.Customer.list(email=user_email, limit=1)
        if not customers.data:
            return None,"No billing account found for this email. Contact support."
        portal = _s.billing_portal.sessions.create(
            customer=customers.data[0].id,
            return_url=_get_app_url()+"/?page=settings",
        )
        return portal.url, None
    except Exception as e:
        return None, f"Stripe error: {e}"

def handle_payment_return():
    """Check URL params for Stripe redirect. Returns True if handled."""
    try: params = st.query_params.to_dict()
    except: return False

    if params.get("payment") == "success":
        sid = params.get("sid",""); plan = params.get("plan","premium")
        st.query_params.clear()
        if sid:
            v_plan, v_info = verify_checkout_session(sid)
            if v_plan:
                if is_authed():
                    e = st.session_state.user["email"]
                    # Both premium and annual get premium role
                    new_role = "premium"
                    new_plan = "Monthly" if v_plan=="premium" else "Annual"
                    st.session_state.users_db[e]["role"] = new_role
                    st.session_state.users_db[e]["plan"] = new_plan
                    st.session_state.role = new_role
                    _save_global_db(st.session_state.users_db)
                    save_user_to_file(e, st.session_state.users_db[e])
                st.session_state["_pay_success"] = v_plan
            else:
                st.session_state["_pay_error"] = v_info
        return True

    elif params.get("payment") == "cancelled":
        st.query_params.clear()
        st.session_state["_pay_cancelled"] = True
        return True

    elif params.get("checkout"):
        plan = params.get("checkout","")
        st.query_params.clear()
        if plan in ("premium","annual"):
            if is_authed():
                url, err = create_checkout_session(plan, st.session_state.user["email"])
                if url: st.session_state["_redirect_url"] = url
                else:   st.session_state["_pay_error"] = err
            else:
                st.session_state["_pending_checkout"] = plan
                nav("signup")
        return True

    return False

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
    border:1px solid rgba(255,255,255,0.16) !important;
    color:#b8cce0 !important;
    border-radius:8px !important;
    font-family:'Inter',sans-serif !important;
    font-size:13px !important;font-weight:500 !important;
    padding:8px 16px !important;
    min-height:40px !important;
    transition:all 0.18s ease !important;
    width:100% !important;
    display:flex !important;align-items:center !important;justify-content:center !important;
    -webkit-font-smoothing:antialiased !important;
    text-rendering:optimizeLegibility !important;
    letter-spacing:0.1px !important;
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

/* ── Download button styling ── */
[data-testid="stDownloadButton"]>button{{
    background:rgba(37,99,235,0.1)!important;
    border:1px solid rgba(37,99,235,0.3)!important;
    color:#93b4fd!important;
    font-size:13px!important;font-weight:600!important;
    border-radius:8px!important;
    transition:all 0.2s!important;
}}
[data-testid="stDownloadButton"]>button:hover{{
    background:rgba(37,99,235,0.2)!important;
    border-color:#2563eb!important;
}}
/* ── Tabs styling ── */
[data-testid="stTabs"]>div>[role="tablist"]{{
    gap:4px!important;border-bottom:1px solid rgba(255,255,255,0.08)!important;
}}
button[role="tab"]{{
    font-size:13px!important;font-weight:500!important;
    padding:8px 16px!important;border-radius:6px 6px 0 0!important;
    color:#4a5e7a!important;
}}
button[role="tab"][aria-selected="true"]{{
    color:#e2e8f0!important;font-weight:700!important;
    background:rgba(37,99,235,0.08)!important;
    border-bottom:2px solid #2563eb!important;
}}
/* ── Expander styling ── */
.streamlit-expanderHeader{{
    font-size:13px!important;font-weight:600!important;color:#6b7fa0!important;
}}
/* ── Success/error/info messages ── */
[data-testid="stAlert"]{{border-radius:10px!important;font-size:13px!important;}}
/* ── Mobile & Tablet Responsive ── */
@media (max-width:900px) {{
    /* Hero text */
    .hero-h1{{font-size:32px !important;letter-spacing:-1px !important;}}
    .hero-sub{{font-size:14px !important;}}
    /* Feature grids → single column */
    .sw-feat-grid{{grid-template-columns:1fr !important;}}
    /* Page padding */
    .pg{{padding:12px 14px 28px !important;}}
    /* Footer */
    .sw-footer-wrap{{padding:24px 20px 20px !important;}}
    /* Hide sidebar on mobile */
    [data-testid="stSidebar"]{{display:none !important;}}
    /* Stack hero columns */
    [data-testid="stHorizontalBlock"]{{flex-wrap:wrap !important;}}
    [data-testid="stHorizontalBlock"] [data-testid="column"]{{min-width:100% !important;flex:none !important;}}
    /* Topbar shrink */
    .sw-nav .stButton>button{{font-size:11px !important;padding:4px 8px !important;}}
    /* Cards */
    .card{{padding:12px 14px !important;}}
}}
@media (max-width:600px) {{
    .hero-h1{{font-size:26px !important;}}
    .hero-sub{{font-size:13px !important;}}
    /* Trust bar wrap */
    .sw-trust-bar{{flex-wrap:wrap !important;gap:16px !important;padding:16px !important;}}
}}
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
    "🔥💥 Squeeze + Buzz":    ("High short float stocks trending on StockTwits — social momentum meets squeeze fuel", "premium"),
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
        "prev_page":None,"hero_panel":0,"_page_hist":[],
        "users_db":_get_global_db(),
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
        # Load this user's alerts from file
        user_alerts_db = _read_json(ALERTS_DB_PATH, {})
        st.session_state.alerts = user_alerts_db.get(email, [])
        return True
    return False

def signup(email, pw, name):
    db=st.session_state.users_db
    if email in db: return False,"Account already exists."
    db[email]={"pw":hp(pw),"name":name,"role":"free","verified":False,
               "joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Free"}
    _save_global_db(db)  # persist to process-level store
    save_user_to_file(email, db[email])  # persist to file for worker
    st.session_state.site_stats["total_signups"]+=1
    st.session_state.user={"email":email,"name":name}
    st.session_state.role="free"
    return True,""

def logout():
    keys_to_clear = ["user","role","watchlist","alerts","saved_screeners","sel_plan",
                     "support_chat","_page_hist","prev_page","detail_ticker","detail_data",
                     "_redirect_url","_pay_success","_pay_error","_pay_cancelled",
                     "_login_welcome","_signup_success"]
    for k in keys_to_clear:
        st.session_state.pop(k, None)
    st.session_state["_logged_out"] = True
    nav("landing")

def is_owner():   return st.session_state.get("role")=="owner"
def is_admin():   return st.session_state.get("role") in ("owner","admin")
def is_premium(): return st.session_state.get("role") in ("owner","admin","premium")
def is_authed():  return st.session_state.get("user") is not None

def nav(p):
    cur = st.session_state.get("page")
    if cur and cur != p:
        hist = st.session_state.get("_page_hist", [])
        hist.append(cur)
        if len(hist) > 20: hist = hist[-20:]
        st.session_state["_page_hist"] = hist
    st.session_state.prev_page = cur
    st.session_state.page = p
    st.rerun()

def go_back():
    hist = st.session_state.get("_page_hist", [])
    if hist:
        prev = hist.pop()
        st.session_state["_page_hist"] = hist
        st.session_state.page = prev
        st.rerun()
    else:
        nav("discover" if is_authed() else "landing")
# ─────────────────────────────────────────────────────────────
# EXCEL EXPORT
# ─────────────────────────────────────────────────────────────
def make_excel(rows: list, sheet_name: str = "StockWins Data") -> bytes:
    """Build an Excel workbook from a list of dicts. Returns bytes."""
    import io
    try:
        import xlsxwriter
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet(sheet_name[:31])

        # Formats
        hdr_fmt = wb.add_format({"bold": True, "bg_color": "#0d1525", "font_color": "#60a5fa",
                                  "border": 1, "border_color": "#1e3a5f", "font_size": 11})
        pos_fmt = wb.add_format({"font_color": "#22c55e", "font_size": 10})
        neg_fmt = wb.add_format({"font_color": "#ef4444", "font_size": 10})
        num_fmt = wb.add_format({"num_format": "$#,##0.00", "font_size": 10})
        pct_fmt = wb.add_format({"num_format": "0.00%", "font_size": 10})
        def_fmt = wb.add_format({"font_size": 10})
        gold_fmt = wb.add_format({"font_color": "#f59e0b", "font_size": 10, "bold": True})

        if not rows:
            wb.close()
            return buf.getvalue()

        headers = list(rows[0].keys())
        col_widths = {h: max(len(str(h)), 8) for h in headers}

        # Write headers
        for ci, h in enumerate(headers):
            ws.write(0, ci, h, hdr_fmt)

        # Write data rows
        for ri, row in enumerate(rows, 1):
            for ci, h in enumerate(headers):
                val = row.get(h, "")
                w = max(col_widths[h], len(str(val)))
                col_widths[h] = min(w, 40)
                # Choose format based on content
                if isinstance(val, (int, float)):
                    fmt = num_fmt if h.lower() in ("price","open","high","low","close") else def_fmt
                    ws.write_number(ri, ci, val, fmt)
                elif isinstance(val, str) and val.startswith("+"):
                    ws.write(ri, ci, val, pos_fmt)
                elif isinstance(val, str) and val.startswith("-"):
                    ws.write(ri, ci, val, neg_fmt)
                elif isinstance(val, str) and ("BUY" in val or "STRONG" in val):
                    ws.write(ri, ci, val, gold_fmt)
                else:
                    ws.write(ri, ci, val, def_fmt)

        # Set column widths
        for ci, h in enumerate(headers):
            ws.set_column(ci, ci, col_widths[h] + 2)

        # Add auto-filter
        ws.autofilter(0, 0, len(rows), len(headers) - 1)
        ws.freeze_panes(1, 0)

        wb.close()
        return buf.getvalue()

    except Exception as e:
        # Fallback to CSV bytes if xlsxwriter fails
        import io
        buf = io.StringIO()
        if rows:
            import csv
            w = csv.DictWriter(buf, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        return buf.getvalue().encode()

def export_button(rows: list, filename: str, label: str = "📥 Export to Excel", key: str = "export"):
    """Render a download button for Excel export."""
    if not rows:
        st.info("No data to export.")
        return
    try:
        data = make_excel(rows, filename.replace(".xlsx","")[:31])
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = ".xlsx"
    except:
        import io
        buf = io.StringIO()
        import csv
        w = csv.DictWriter(buf, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
        data = buf.getvalue().encode(); mime = "text/csv"; ext = ".csv"
    st.download_button(label=label, data=data,
                       file_name=filename.replace(".xlsx", ext),
                       mime=mime, key=key, use_container_width=True)



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
    results=[]
    prog_container=st.empty()
    for i,t in enumerate(universe[:limit*3]):
        pct=(i+1)/(limit*3)
        prog_container.markdown(f'''<div style="background:#0d1525;border:1px solid rgba(37,99,235,0.2);border-radius:10px;padding:12px 16px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                <span style="font-size:12px;font-weight:600;color:#60a5fa;">⚡ {cat_name}</span>
                <span style="font-size:11px;color:#374f6e;">{int(pct*100)}% · Scanning {t}…</span>
            </div>
            <div style="background:rgba(255,255,255,0.06);border-radius:4px;height:4px;">
                <div style="background:linear-gradient(90deg,#1d4ed8,#2563eb);width:{int(pct*100)}%;height:4px;border-radius:4px;"></div>
            </div>
        </div>''', unsafe_allow_html=True)
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
    prog_container.empty()
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
            if is_authed():
                db = st.session_state.users_db.get(st.session_state.user["email"], {})
                db["watchlist"] = wl
                save_user_to_file(st.session_state.user["email"], db)
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
        scan=min(len(tickers),limit); stocks=[]
        prog_container=st.empty()
        for i,t in enumerate(tickers[:scan]):
            pct=(i+1)/scan
            prog_container.markdown(f'''<div style="background:#0d1525;border:1px solid rgba(37,99,235,0.2);border-radius:10px;padding:12px 16px;margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                    <span style="font-size:12px;font-weight:600;color:#60a5fa;">⚡ Analyzing {cat}</span>
                    <span style="font-size:11px;color:#374f6e;">{int(pct*100)}% · Scanning {t}…</span>
                </div>
                <div style="background:rgba(255,255,255,0.06);border-radius:4px;height:4px;">
                    <div style="background:linear-gradient(90deg,#1d4ed8,#2563eb);width:{int(pct*100)}%;height:4px;border-radius:4px;transition:width 0.3s;"></div>
                </div>
            </div>''', unsafe_allow_html=True)
            q=get_quote(t); df=yf_ohlcv(t,60); info=yf_fund(t); sent=st_sent(t)
            sc,bd,op,risk,conf=compute_scores(df,info,sent); ig=get_insights(df,info)
            if q: stocks.append({"t":t,"q":q,"sc":sc,"bd":bd,"ig":ig,"op":op,"risk":risk,"conf":conf,"hot":t in hot,"df":df,"info":info,"sent":sent,"comp":sc,"why":""})
        prog.empty()
        stocks.sort(key=lambda x:x["sc"],reverse=True)
    if not stocks:
        st.markdown('''<div style="background:#0d1525;border:1px solid rgba(255,255,255,0.08);
                           border-radius:10px;padding:32px;text-align:center;">
            <div style="font-size:24px;margin-bottom:10px;">🔍</div>
            <div style="font-size:15px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">No stocks matching right now</div>
            <div style="font-size:13px;color:#374f6e;">Market conditions may not meet this category's criteria at the moment. Check back in 15 minutes.</div>
        </div>''', unsafe_allow_html=True)
        return
    for s in stocks: render_sr(s,cat.replace(" ","_").replace("+","p").replace("→","r"),show_why=is_comp)

def render_lock(name=""):
    st.markdown(f"""<div style="background:linear-gradient(135deg,#120d00,#0d1525);
        border:1px solid rgba(245,158,11,0.3);border-radius:14px;padding:40px 32px;text-align:center;">
        <div style="font-size:36px;margin-bottom:14px;">👑</div>
        <div style="font-size:20px;font-weight:800;color:#e2e8f0;margin-bottom:8px;">{name}</div>
        <div style="display:inline-block;background:rgba(245,158,11,0.1);color:{GOLD};
                    font-size:10px;font-weight:700;padding:3px 12px;border-radius:20px;
                    border:1px solid rgba(245,158,11,0.3);margin-bottom:14px;">PREMIUM FEATURE</div>
        <div style="font-size:13px;color:#374f6e;margin-bottom:6px;line-height:1.7;">
            Upgrade to Premium to unlock this composite category and 9 others,<br>
            plus the short squeeze scanner, advanced screener, full BI analytics, and unlimited alerts.
        </div>
        <div style="font-size:12px;color:#2a3a52;margin-bottom:20px;">Starting at $29/month · Cancel anytime · No contracts</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    _,lc,_=st.columns([1,2,1])
    with lc:
        if gold_btn("👑 Unlock Premium", f"lock_{name[:20].replace(' ','_')}"): nav("pricing")
        st.markdown("<br>", unsafe_allow_html=True)
        if is_authed() and st.button("Already subscribed? Refresh →", key=f"lock_ref_{name[:10]}", use_container_width=True):
            st.rerun()

# ─────────────────────────────────────────────────────────────
# NAV CSS + TOPBAR
# ─────────────────────────────────────────────────────────────
NAV_CSS = """<style>
.sw-logo-click-target{display:flex;align-items:center;height:38px;cursor:pointer;padding:0;line-height:1;}
.element-container:has(.sw-logo-click-target)+.element-container{height:0px !important;overflow:visible !important;margin:0 !important;padding:0 !important;}
.element-container:has(.sw-logo-click-target)+.element-container .stButton>button{position:relative !important;top:-44px !important;left:0 !important;width:180px !important;height:44px !important;min-height:44px !important;opacity:0 !important;cursor:pointer !important;z-index:999 !important;background:transparent !important;border:none !important;box-shadow:none !important;}
.sw-divider{border:none;border-top:1px solid rgba(255,255,255,0.06);margin:0 0 24px 0;}
/* Pusher toast notification */
#sw-push-toast{position:fixed;top:80px;right:20px;z-index:9999;display:none;
  background:#0d1525;border:1px solid rgba(37,99,235,0.5);border-radius:12px;
  padding:14px 18px;box-shadow:0 8px 32px rgba(37,99,235,0.3);
  min-width:280px;max-width:360px;animation:slideIn 0.3s ease;}
@keyframes slideIn{from{transform:translateX(120%);opacity:0;}to{transform:translateX(0);opacity:1;}}
#sw-push-toast .toast-ticker{font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:800;color:#60a5fa;}
#sw-push-toast .toast-msg{font-size:12px;color:#374f6e;margin-top:4px;line-height:1.5;}
#sw-push-toast .toast-close{position:absolute;top:8px;right:12px;cursor:pointer;color:#4a5e7a;font-size:16px;}
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
               ("Screener","screener"),("BI Analytics","bi_dashboard"),("Pricing","pricing"),("Contact","contact")]
        if is_admin(): pages.append(("🛠 Admin","admin"))
        c1,c2,c3=st.columns([2,8,3])
        with c1: render_logo_click("top_logo","dashboard")
        with c2:
            st.markdown('<div class="sw-nav">', unsafe_allow_html=True)
            nc=st.columns(len(pages))
            for col,(lbl,pg) in zip(nc,pages):
                with col:
                    if st.button(lbl,key=f"top_{pg}",type="primary" if active==pg else "secondary",use_container_width=True):
                        nav(pg)
            st.markdown('</div>', unsafe_allow_html=True)
        with c3:
            ri={"owner":"👑","admin":"🛡️","premium":"⭐","free":"👤"}.get(st.session_state.role,"👤")
            uc1,uc2,uc3=st.columns([4,1,1])
            with uc1: st.markdown(f'<div style="font-size:12px;color:#6b7fa0;white-space:nowrap;">{ri} {st.session_state.user["name"]}</div>',unsafe_allow_html=True)
            with uc2:
                if st.button("⚙️",key="top_set",help="Account settings"): nav("settings")
            with uc3:
                if st.button("↩️",key="top_out",help="Log out"): logout()
    else:
        c1,_,c3=st.columns([2,5,4])
        with c1: render_logo_click("top_logo","landing")
        with c3:
            st.markdown('<div class="sw-nav">', unsafe_allow_html=True)
            a1,a2,a3,a4,a5=st.columns(5,gap="small")
            with a1:
                if st.button("Features",key="top_features",use_container_width=True): nav("features")
            with a2:
                if st.button("Pricing",key="top_pricing",use_container_width=True): nav("pricing")
            with a3:
                if st.button("Contact",key="top_contact",use_container_width=True): nav("contact")
            with a4:
                if st.button("Login",key="top_login",use_container_width=True): nav("login")
            with a5:
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
            for icon,label,pg in [("📊","Dashboard","dashboard"),("⭐","Watchlist","watchlist"),("🔍","Screener","screener"),("📈","BI Analytics","bi_dashboard"),("💰","Pricing","pricing"),("🔔","Alerts & Settings","settings"),("💬","Contact & Help","contact")]:
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
            role_color={"owner":GOLD,"admin":"#93b4fd","premium":"#a78bfa","free":"#4a5e7a"}.get(st.session_state.role,"#4a5e7a")
            plan_label={"owner":"Owner","admin":"Admin","premium":"Premium ⭐","free":"Free Plan"}.get(st.session_state.role,"Free")
            db_sb = st.session_state.users_db.get(st.session_state.user.get("email",""),{})
            verified = db_sb.get("verified",False)
            v_badge = ' <span style="color:#4ade80;font-size:9px;">✓ verified</span>' if verified else ''
            st.markdown(f'''<div style="padding:8px 14px;background:rgba(255,255,255,0.03);border-top:1px solid rgba(255,255,255,0.06);margin-top:4px;">
                <div style="font-size:12px;font-weight:600;color:{role_color};">{ri} {st.session_state.user["name"]}{v_badge}</div>
                <div style="font-size:10px;color:#2a3a52;margin-top:2px;">{plan_label}</div>
            </div>''',unsafe_allow_html=True)
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


# Additional hero demo panels
DEMO_SCORE = """<div style="background:#0d1525;border:1px solid rgba(255,255,255,.08);border-radius:11px;overflow:hidden;">
<div style="background:#080b14;border-bottom:1px solid rgba(255,255,255,.06);padding:10px 14px;display:flex;align-items:center;justify-content:space-between;">
  <div style="display:flex;align-items:center;gap:6px;"><div style="width:8px;height:8px;border-radius:50%;background:#ef4444;"></div><div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;"></div><div style="width:8px;height:8px;border-radius:50%;background:#22c55e;"></div>
  <span style="font-size:11px;color:#374f6e;margin-left:6px;font-family:'JetBrains Mono',monospace;">Score Breakdown — NVDA</span></div>
  <span style="font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:800;color:#4ade80;">88</span>
</div>
<div style="padding:14px;">
  <div style="margin-bottom:8px;"><div style="display:flex;justify-content:space-between;margin-bottom:3px;"><span style="font-size:11px;color:#374f6e;">Momentum (RSI)</span><span style="font-size:11px;font-weight:700;color:#4ade80;">20/25</span></div><div style="background:rgba(255,255,255,.06);border-radius:3px;height:5px;"><div style="background:#22c55e;width:80%;height:5px;border-radius:3px;"></div></div></div>
  <div style="margin-bottom:8px;"><div style="display:flex;justify-content:space-between;margin-bottom:3px;"><span style="font-size:11px;color:#374f6e;">Trend (MA20/50)</span><span style="font-size:11px;font-weight:700;color:#4ade80;">18/20</span></div><div style="background:rgba(255,255,255,.06);border-radius:3px;height:5px;"><div style="background:#22c55e;width:90%;height:5px;border-radius:3px;"></div></div></div>
  <div style="margin-bottom:8px;"><div style="display:flex;justify-content:space-between;margin-bottom:3px;"><span style="font-size:11px;color:#374f6e;">MACD Signal</span><span style="font-size:11px;font-weight:700;color:#4ade80;">13/15</span></div><div style="background:rgba(255,255,255,.06);border-radius:3px;height:5px;"><div style="background:#22c55e;width:87%;height:5px;border-radius:3px;"></div></div></div>
  <div style="margin-bottom:8px;"><div style="display:flex;justify-content:space-between;margin-bottom:3px;"><span style="font-size:11px;color:#374f6e;">Volume Surge</span><span style="font-size:11px;font-weight:700;color:#fbbf24;">9/15</span></div><div style="background:rgba(255,255,255,.06);border-radius:3px;height:5px;"><div style="background:#f59e0b;width:60%;height:5px;border-radius:3px;"></div></div></div>
  <div style="margin-bottom:8px;"><div style="display:flex;justify-content:space-between;margin-bottom:3px;"><span style="font-size:11px;color:#374f6e;">Social Sentiment</span><span style="font-size:11px;font-weight:700;color:#4ade80;">12/15</span></div><div style="background:rgba(255,255,255,.06);border-radius:3px;height:5px;"><div style="background:#22c55e;width:80%;height:5px;border-radius:3px;"></div></div></div>
  <div style="margin-top:10px;padding:8px 10px;background:#080b14;border-radius:7px;font-size:11px;color:#374f6e;line-height:1.6;">
    ✅ Trading above both 20d and 50d moving averages — buyers in control<br>✅ MACD bullish crossover confirmed — momentum building<br>⚠️ Volume below recent surge levels — watch for expansion
  </div>
</div></div>"""

DEMO_BI = """<div style="background:#0d1525;border:1px solid rgba(255,255,255,.08);border-radius:11px;overflow:hidden;">
<div style="background:#080b14;border-bottom:1px solid rgba(255,255,255,.06);padding:10px 14px;display:flex;align-items:center;justify-content:space-between;">
  <div style="display:flex;align-items:center;gap:6px;"><div style="width:8px;height:8px;border-radius:50%;background:#ef4444;"></div><div style="width:8px;height:8px;border-radius:50%;background:#fbbf24;"></div><div style="width:8px;height:8px;border-radius:50%;background:#22c55e;"></div>
  <span style="font-size:11px;color:#374f6e;margin-left:6px;font-family:'JetBrains Mono',monospace;">Opportunity Matrix</span></div>
  <span style="background:rgba(168,85,247,0.15);color:#c084fc;font-size:9px;font-weight:700;padding:2px 8px;border-radius:20px;border:1px solid rgba(168,85,247,.3);">EXCLUSIVE ✨</span>
</div>
<div style="padding:10px;">
  <div style="display:grid;grid-template-columns:60px 1fr 1fr 1fr 1fr 1fr;gap:3px;font-size:10px;">
    <div style="color:#2a3a52;"></div>
    <div style="text-align:center;color:#6b7fa0;font-weight:600;padding:3px;">Mom</div><div style="text-align:center;color:#6b7fa0;font-weight:600;padding:3px;">Trend</div><div style="text-align:center;color:#6b7fa0;font-weight:600;padding:3px;">Vol</div><div style="text-align:center;color:#6b7fa0;font-weight:600;padding:3px;">Sent</div><div style="text-align:center;color:#6b7fa0;font-weight:600;padding:3px;">Sq</div>
    <div style="font-family:'JetBrains Mono',monospace;color:#60a5fa;font-weight:700;padding:3px 0;display:flex;align-items:center;">NVDA</div>
    <div style="background:#0d5016;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">20</div><div style="background:#0d5016;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">18</div><div style="background:#1a3a00;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">9</div><div style="background:#0d5016;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">12</div><div style="background:#080f1e;border-radius:3px;text-align:center;padding:5px;color:#4a5e7a;font-weight:700;">0</div>
    <div style="font-family:'JetBrains Mono',monospace;color:#60a5fa;font-weight:700;padding:3px 0;display:flex;align-items:center;">TSLA</div>
    <div style="background:#1a3a00;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">14</div><div style="background:#0d5016;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">16</div><div style="background:#0d5016;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">13</div><div style="background:#1a3a00;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">10</div><div style="background:#1a3a00;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">6</div>
    <div style="font-family:'JetBrains Mono',monospace;color:#60a5fa;font-weight:700;padding:3px 0;display:flex;align-items:center;">GME</div>
    <div style="background:#0a2818;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">18</div><div style="background:#080f1e;border-radius:3px;text-align:center;padding:5px;color:#4a5e7a;font-weight:700;">4</div><div style="background:#0d5016;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">15</div><div style="background:#0d5016;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">14</div><div style="background:#0d5016;border-radius:3px;text-align:center;padding:5px;color:white;font-weight:700;">10</div>
  </div>
</div></div>"""

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
            '.tab-row{display:flex;gap:24px;margin-bottom:8px;padding:14px 0 0;}'
            '.tab-item{font-size:13px;font-weight:500;color:#374f6e;cursor:pointer;'
            'padding-bottom:5px;border-bottom:2px solid transparent;transition:all 0.2s;white-space:nowrap;}'
            '.tab-item.active{color:#e2e8f0;font-weight:700;border-bottom-color:#2563eb;}'
            '.tab-item:hover{color:#a8bdd4;}'
            '.dots{display:flex;gap:6px;margin-bottom:10px;}'
            '.dot{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,0.15);cursor:pointer;transition:all 0.3s;}'
            '.dot.active{background:#2563eb;width:18px;border-radius:3px;}'
            '.slide-title{font-size:22px;font-weight:900;color:#f1f5f9;letter-spacing:-0.5px;line-height:1.2;margin-bottom:12px;min-height:52px;}'
            '.hi{color:#2563eb;}.hg{color:#f59e0b;}'
            '</style>'
            '<div>'
            '<div class="tab-row">'
            '<div class="tab-item active" id="t0" onclick="sw(0)">📊 Market Overview</div>'
            '<div class="tab-item" id="t1" onclick="sw(1)">💥 Squeeze Radar</div>'
            '<div class="tab-item" id="t2" onclick="sw(2)">💡 Smart Insights</div>'
            '<div class="tab-item" id="t3" onclick="sw(3)">🎯 Score Breakdown</div>'
            '<div class="tab-item" id="t4" onclick="sw(4)">📈 BI Analytics</div>'
            '</div>'
            '<div class="dots">'
            '<div class="dot active" id="d0" onclick="sw(0)"></div>'
            '<div class="dot" id="d1" onclick="sw(1)"></div>'
            '<div class="dot" id="d2" onclick="sw(2)"></div>'
            '<div class="dot" id="d3" onclick="sw(3)"></div>'
            '<div class="dot" id="d4" onclick="sw(4)"></div>'
            '</div>'
            '<div id="h0" class="slide-title">Find Trending Stocks<br><span class="hi">Before the Crowd</span></div>'
            '<div id="h1" class="slide-title" style="display:none">Scan For Short Squeeze<br><span class="hi">Candidates</span></div>'
            '<div id="h2" class="slide-title" style="display:none">Smart Insights<br>in <span class="hi">Simple Language</span></div>'
            '<div id="h3" class="slide-title" style="display:none">Premium <span class="hg">Score Breakdowns</span><br>&amp; Deep Analysis</div>'
            '<div id="h4" class="slide-title" style="display:none">BI Analytics &amp;<br><span class="hi">Opportunity Matrix</span></div>'
            '<div id="p0">' + DEMO[0] + '</div>'
            '<div id="p1" style="display:none">' + DEMO[1] + '</div>'
            '<div id="p2" style="display:none">' + DEMO[2] + '</div>'
            '<div id="p3" style="display:none">' + DEMO_SCORE + '</div>'
            '<div id="p4" style="display:none">' + DEMO_BI + '</div>'
            '</div>'
            '<script>'
            'var c=0;'
            'function sw(n){'
            '  for(var i=0;i<5;i++){'
            '    document.getElementById("t"+i).className="tab-item"+(i===n?" active":"");'
            '    document.getElementById("d"+i).className="dot"+(i===n?" active":"");'
            '    document.getElementById("h"+i).style.display=i===n?"block":"none";'
            '    document.getElementById("p"+i).style.display=i===n?"block":"none";'
            '  }'
            '  c=n;'
            '}'
            'setInterval(function(){sw((c+1)%5);},5000);'
            '</script>'
        )
        import streamlit.components.v1 as components
        components.html(hero_comp, height=500, scrolling=False)

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
    <style>
    .sw-feat-grid{{display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:0 48px;align-items:stretch;}}
    @media(max-width:900px){{.sw-feat-grid{{grid-template-columns:1fr;gap:20px;padding:0 20px;}}}}
    /* Both content boxes same fixed height */
    .sw-demo-wrap{{overflow:hidden;height:320px;box-sizing:border-box;flex:none!important;}}
    .sw-demo-wrap>div{{height:100%;}}
    .sw-prem-box{{height:320px;box-sizing:border-box;display:flex;flex-direction:column;flex:none!important;}}
    </style>
    <div class="sw-feat-grid" style="margin-bottom:28px;">
      <div style="display:flex;flex-direction:column;height:100%;">
        <div style="min-height:105px;margin-bottom:16px;">
          <div style="font-size:26px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;line-height:1.15;margin-bottom:8px;">Find Trending Stocks<br><span style="color:{BLUE};">Before the Crowd</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Discover top stocks making waves across social media and the market.</div>
        </div>
        <div class="sw-demo-wrap" style="flex:none;height:320px;overflow:hidden;">{DEMO[0]}</div>
      </div>
      <div style="display:flex;flex-direction:column;height:100%;">
        <div style="min-height:105px;margin-bottom:16px;">
          <div style="font-size:26px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;line-height:1.15;margin-bottom:8px;">Scan For Short Squeeze<br><span style="color:{BLUE};">Candidates</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Spot stocks with heavy short interest and growing momentum before the move.</div>
        </div>
        <div class="sw-demo-wrap" style="flex:none;height:320px;overflow:hidden;">{DEMO[1]}</div>
      </div>
    </div>
    <div class="sw-feat-grid">
      <div style="display:flex;flex-direction:column;height:100%;">
        <div style="min-height:105px;margin-bottom:16px;">
          <div style="font-size:26px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;line-height:1.15;margin-bottom:8px;">Smart Insights<br>in Simple <span style="color:{BLUE};">Language</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Every technical signal explained in plain English. No finance degree needed.</div>
        </div>
        <div class="sw-demo-wrap" style="flex:none;height:320px;overflow:hidden;">{DEMO[2]}</div>
      </div>
      <div style="display:flex;flex-direction:column;height:100%;">
        <div style="min-height:105px;margin-bottom:16px;">
          <div style="font-size:26px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;line-height:1.15;margin-bottom:8px;">Go Premium For<br><span style="color:{GOLD};">Real-Time Signals &amp;<br>Deeper Analysis</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Upgrade to unlock advanced screening, unlimited alerts, and premium watchlists.</div>
        </div>
        <div class="sw-prem-box" style="flex:1;height:320px;background:#0d1525;border:1px solid rgba(245,158,11,.25);border-radius:11px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#1a0d00,#0d1525);border-bottom:1px solid rgba(245,158,11,.2);padding:10px 16px;display:flex;align-items:center;gap:8px;">
            <span style="font-size:13px;">👑</span>
            <span style="font-size:11px;font-weight:700;color:{GOLD};letter-spacing:1px;">PREMIUM FEATURES</span>
          </div>
          <div style="padding:14px 16px;font-size:12.5px;color:#374f6e;line-height:2.05;flex:1;">
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

    # ── Testimonials — auto-scrolling ──
    st.markdown('<div style="padding:0 48px;"><div class="sec-hd">What Traders Are Saying</div></div>',unsafe_allow_html=True)

    testimonials = [
        ("⭐⭐⭐⭐⭐", "Michael T.", "Squeeze + Buzz flagged AMC 3 days before it ran 40%. First tool I've used where the BUY signal actually comes with a reason."),
        ("⭐⭐⭐⭐", "Sarah K.", "Hidden Movers is solid. Found 2 stocks quietly building before they showed up on StockTwits. Would be 5 stars if the UI loaded a bit faster."),
        ("⭐⭐⭐⭐⭐", "James M.", "Triple Lock caught a setup on NVDA that my normal screener completely missed. When all 4 signals align it really does feel different."),
        ("⭐⭐⭐⭐", "David R.", "Plain-English explanations are great for someone who doesn't live and breathe TA. Finally understand what a Golden Cross actually means in practice."),
        ("⭐⭐⭐⭐⭐", "Carlos V.", "The composite categories are the only reason I stay. Smart Money Signal and Volume Breakout together have been my best performers this quarter."),
        ("⭐⭐⭐⭐⭐", "Emma W.", "Volatility Squeeze + high volume = coiled spring. Caught 3 clean setups last month. The math behind it is actually explained, which I respect."),
    ]

    # Build scrolling HTML — duplicate cards for seamless loop
    cards_html = ""
    for stars, name, quote in testimonials * 2:
        cards_html += (
            f'<div class="tc">'
            f'<div class="stars">{stars}</div>'
            f'<div class="quote">\u201c{quote}\u201d</div>'
            f'<div class="author">{name}</div>'
            f'</div>'
        )

    testimonial_comp = (
        '<style>'
        'body{margin:0;padding:0;background:transparent;overflow:hidden;}'
        '@keyframes scroll-left{'
        '  0%{transform:translateX(0);}'
        '  100%{transform:translateX(-50%);}'
        '}'
        '.track-wrap{overflow:hidden;padding:4px 0 8px;}'
        '.track{'
        '  display:flex;gap:16px;'
        '  animation:scroll-left 50s linear infinite;'
        '  width:max-content;'
        '}'
        '.track:hover{animation-play-state:paused;}'
        '.tc{'
        '  background:#0d1525;border:1px solid rgba(255,255,255,0.07);'
        '  border-radius:12px;padding:20px 22px;width:320px;flex-shrink:0;'
        '  box-sizing:border-box;'
        '}'
        '.stars{font-size:13px;margin-bottom:10px;letter-spacing:1px;}'
        '.quote{font-size:12px;color:#374f6e;line-height:1.7;margin-bottom:14px;font-style:italic;}'
        '.author{font-size:12px;font-weight:700;color:#2563eb;}'
        '</style>'
        '<div class="track-wrap">'
        '<div class="track">' + cards_html + '</div>'
        '</div>'
    )

    import streamlit.components.v1 as components
    components.html(testimonial_comp, height=160)

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
    # CTA strip at top
    if not is_premium() and is_authed():
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1a0d00,#0d1525);border:1px solid rgba(245,158,11,0.25);
                    border-radius:12px;padding:14px 20px;margin-bottom:20px;
                    display:flex;align-items:center;justify-content:space-between;">
            <div>
                <div style="font-size:14px;font-weight:700;color:{GOLD};">👑 Upgrade to unlock all premium features</div>
                <div style="font-size:12px;color:#374f6e;margin-top:2px;">All 17 categories · Squeeze scanner · BI Analytics · Unlimited alerts</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if gold_btn("Unlock Premium — $29/mo", "feat_top_prem"): nav("pricing")
        st.markdown("<br>", unsafe_allow_html=True)
    elif not is_authed():
        st.markdown(f"""
        <div style="background:#0d1525;border:1px solid rgba(37,99,235,0.25);border-radius:12px;
                    padding:14px 20px;margin-bottom:20px;">
            <div style="font-size:14px;font-weight:700;color:#e2e8f0;">🚀 Start free — no credit card required</div>
            <div style="font-size:12px;color:#374f6e;margin-top:2px;">Create an account in 60 seconds and start discovering trading opportunities immediately.</div>
        </div>
        """, unsafe_allow_html=True)

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
    render_footer()

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
                elif login(email,pw):
                    st.session_state["_login_welcome"] = st.session_state.user.get("name","")
                    nav("dashboard")
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
                    if ok:
                        # Generate verification code and send email
                        code=str(random.randint(100000,999999))
                        st.session_state["_verify_code"]=code
                        st.session_state["_verify_email"]=email
                        st.session_state["_verify_user"]={"name":name}
                        # Log out the just-created session — require verification first
                        st.session_state.pop("user",None); st.session_state.pop("role",None)
                        ok2,info=_send_verification_email(email,code)
                        if not ok2 and info and info.startswith("DEMO_CODE:"):
                            st.session_state["_demo_code"]=info.split(":",1)[1]
                        nav("verify_email")
                    else: st.error(msg)
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
                    st.markdown("""
                    <div style="background:#04200d;border:1px solid rgba(34,197,94,0.3);
                                border-radius:10px;padding:16px;text-align:center;margin-top:8px;">
                        <div style="font-size:24px;margin-bottom:8px;">📧</div>
                        <div style="font-size:14px;font-weight:700;color:#4ade80;margin-bottom:4px;">Reset Link Sent!</div>
                        <div style="font-size:12px;color:#374f6e;">Check your inbox and follow the link to reset your password.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    time.sleep(2); nav("login")
                else: st.error("No account found.")
        if st.button("← Back to Login",key="f2l",use_container_width=True): nav("login")

# ─────────────────────────────────────────────────────────────
# PAGE: DASHBOARD
# ─────────────────────────────────────────────────────────────
def page_dashboard():
    render_topbar("dashboard")
    st.markdown('<div class="pg">',unsafe_allow_html=True)

    # ── Welcome strip ──
    user_name = st.session_state.user.get("name","Trader") if is_authed() else "Trader"
    role_lbl = {"owner":"👑 Owner","admin":"🛡️ Admin","premium":"⭐ Premium","free":"👤 Free"}.get(st.session_state.get("role","free"),"👤 Free")
    role_color = GOLD if is_premium() else "#6b7fa0"

    now_hour = datetime.now().hour
    greeting = "Good morning" if now_hour<12 else ("Good afternoon" if now_hour<18 else "Good evening")

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:18px;">
        <div>
            <div style="font-size:14px;color:#6b7fa0;margin-bottom:2px;">{greeting},</div>
            <div style="font-size:26px;font-weight:800;color:#e2e8f0;letter-spacing:-0.5px;">{user_name} 👋</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:11px;color:#374f6e;margin-bottom:2px;">Account Status</div>
            <div style="font-size:14px;font-weight:700;color:{role_color};">{role_lbl}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Market Overview FIRST (this is the dashboard's purpose) ──
    st.markdown(f'<div style="font-size:11px;font-weight:700;color:#4a5e7a;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">📊 MARKET OVERVIEW</div>',unsafe_allow_html=True)

    with st.spinner("Loading market data…"):
        idx=get_indexes(); secs=get_sectors(); movers=get_bi_movers()

    idx_cols=st.columns(len(idx))
    for col,(name,d) in zip(idx_cols,idx.items()):
        c=GREEN if d["pct"]>=0 else RED; ar="▲" if d["pct"]>=0 else "▼"
        hist=d.get("hist",[])
        bars=""
        if hist:
            mn,mx=min(hist),max(hist); rng=mx-mn if mx!=mn else 1
            bars=''.join([f'<div style="height:{int(14*(v-mn)/rng+3)}px;width:4px;background:{GREEN if d["pct"]>=0 else RED};border-radius:2px;display:inline-block;margin-right:1px;vertical-align:bottom;opacity:0.55;"></div>' for v in hist])
        col.markdown(f"""<div class="idx-w" style="padding:14px;">
            <div class="idx-name">{name}</div>
            <div class="idx-price" style="font-size:18px;">{d['price']:,.2f}</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{c};">{ar}{abs(d['pct']):.2f}%</div>
            <div style="margin-top:10px;height:18px;display:flex;align-items:flex-end;">{bars}</div>
        </div>""",unsafe_allow_html=True)

    # ── Quick stats row ──
    st.markdown('<div style="height:14px;"></div>', unsafe_allow_html=True)
    avg_pct = sum(m["pct"] for m in movers)/len(movers) if movers else 0
    bull_count = sum(1 for m in movers if m["pct"]>0)
    bear_count = sum(1 for m in movers if m["pct"]<0)
    breadth_label = "Bullish" if avg_pct>0.3 else "Bearish" if avg_pct<-0.3 else "Mixed"
    breadth_color = GREEN if avg_pct>0.3 else RED if avg_pct<-0.3 else "#94a3b8"
    top_sec = max(secs,key=secs.get) if secs else "—"
    top_sec_chg = secs.get(top_sec,0) if secs else 0

    qcols = st.columns(4)
    qcols[0].markdown(f"""<div class="stat" style="background:#080b14;border:1px solid {BORDER};padding:12px 14px;border-radius:10px;">
        <div style="font-size:10px;color:#374f6e;letter-spacing:1.5px;font-weight:700;">MARKET BREADTH</div>
        <div style="font-size:18px;font-weight:800;color:{breadth_color};margin-top:4px;">{breadth_label}</div>
        <div style="font-size:10px;color:#4a5e7a;margin-top:2px;">{bull_count} ↑ · {bear_count} ↓</div>
    </div>""", unsafe_allow_html=True)
    qcols[1].markdown(f"""<div class="stat" style="background:#080b14;border:1px solid {BORDER};padding:12px 14px;border-radius:10px;">
        <div style="font-size:10px;color:#374f6e;letter-spacing:1.5px;font-weight:700;">STRONGEST SECTOR</div>
        <div style="font-size:14px;font-weight:800;color:{GREEN};margin-top:4px;">{top_sec}</div>
        <div style="font-size:10px;color:#4a5e7a;margin-top:2px;">+{top_sec_chg:.2f}% today</div>
    </div>""", unsafe_allow_html=True)
    qcols[2].markdown(f"""<div class="stat" style="background:#080b14;border:1px solid {BORDER};padding:12px 14px;border-radius:10px;">
        <div style="font-size:10px;color:#374f6e;letter-spacing:1.5px;font-weight:700;">YOUR WATCHLIST</div>
        <div style="font-size:18px;font-weight:800;color:#e2e8f0;margin-top:4px;">{len(st.session_state.get("watchlist",[]))} stocks</div>
        <div style="font-size:10px;color:#4a5e7a;margin-top:2px;">tracked</div>
    </div>""", unsafe_allow_html=True)
    qcols[3].markdown(f"""<div class="stat" style="background:#080b14;border:1px solid {BORDER};padding:12px 14px;border-radius:10px;">
        <div style="font-size:10px;color:#374f6e;letter-spacing:1.5px;font-weight:700;">ACTIVE ALERTS</div>
        <div style="font-size:18px;font-weight:800;color:#e2e8f0;margin-top:4px;">{len(st.session_state.get("alerts",[]))} active</div>
        <div style="font-size:10px;color:#4a5e7a;margin-top:2px;">monitoring</div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Top Movers + Hot Stocks (2 columns) ──
    left,right=st.columns(2,gap="small")

    with left:
        st.markdown(f'<div style="font-size:11px;font-weight:700;color:#4a5e7a;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">📈 TOP MOVERS TODAY</div>',unsafe_allow_html=True)
        gainers = sorted(movers, key=lambda x:x["pct"], reverse=True)[:5]
        losers = sorted(movers, key=lambda x:x["pct"])[:5]

        st.markdown('<div style="font-size:11px;color:#4ade80;font-weight:700;margin-bottom:6px;">🟢 GAINERS</div>',unsafe_allow_html=True)
        for m in gainers:
            st.markdown(f"""<div class="sr" style="padding:8px 12px;margin-bottom:3px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span class="sr-tick" style="font-size:13px;">{m['t']}</span>
                    <div style="display:flex;gap:14px;align-items:center;">
                        <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#e2e8f0;">${m['price']:,.2f}</span>
                        <span style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{GREEN};">▲{m['pct']:.2f}%</span>
                    </div>
                </div>
            </div>""",unsafe_allow_html=True)

        st.markdown('<div style="font-size:11px;color:#f87171;font-weight:700;margin:10px 0 6px;">🔴 LOSERS</div>',unsafe_allow_html=True)
        for m in losers:
            st.markdown(f"""<div class="sr" style="padding:8px 12px;margin-bottom:3px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span class="sr-tick" style="font-size:13px;">{m['t']}</span>
                    <div style="display:flex;gap:14px;align-items:center;">
                        <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#e2e8f0;">${m['price']:,.2f}</span>
                        <span style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{RED};">▼{abs(m['pct']):.2f}%</span>
                    </div>
                </div>
            </div>""",unsafe_allow_html=True)

    with right:
        st.markdown(f'<div style="font-size:11px;font-weight:700;color:#4a5e7a;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">🔥 SOCIAL BUZZ</div>',unsafe_allow_html=True)
        hot=st_hot()
        for t in hot[:8]:
            q=get_quote(t)
            if q:
                s=st_sent(t); cc_=GREEN if q["pct"]>=0 else RED; ar="▲" if q["pct"]>=0 else "▼"
                bull_color = GREEN if s['bull']>=60 else RED if s['bull']<40 else "#94a3b8"
                st.markdown(f"""<div class="sr" style="padding:8px 12px;margin-bottom:3px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <span class="sr-tick" style="font-size:13px;">{t}</span>
                            <span style="font-size:10px;color:{bull_color};margin-left:8px;font-weight:700;">{s['bull']}% bullish</span>
                        </div>
                        <div style="display:flex;gap:12px;align-items:center;">
                            <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#e2e8f0;">${q['price']:,.2f}</span>
                            <span style="font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:{cc_};">{ar}{abs(q['pct']):.2f}%</span>
                        </div>
                    </div>
                </div>""",unsafe_allow_html=True)

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Sector Heatmap ──
    st.markdown(f'<div style="font-size:11px;font-weight:700;color:#4a5e7a;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">🗺️ SECTOR HEATMAP</div>',unsafe_allow_html=True)
    sec_sorted=sorted(secs.items(),key=lambda x:x[1],reverse=True)
    sc_cols=st.columns(len(sec_sorted))
    for i,(sec,chg) in enumerate(sec_sorted):
        with sc_cols[i]:
            intensity = min(abs(chg)/2.5, 1.0)
            if chg > 0:
                bg = f"rgba(34,197,94,{0.15+intensity*0.5})"
                tc = "#4ade80"
            elif chg < 0:
                bg = f"rgba(239,68,68,{0.15+intensity*0.5})"
                tc = "#f87171"
            else:
                bg = "rgba(255,255,255,0.04)"; tc = "#94a3b8"
            arrow = "▲" if chg>=0 else "▼"
            st.markdown(f"""<div style="background:{bg};border-radius:8px;padding:14px 6px;text-align:center;border:1px solid rgba(255,255,255,0.05);">
                <div style="font-size:11px;color:#e2e8f0;font-weight:600;margin-bottom:4px;">{sec}</div>
                <div style="font-size:14px;font-weight:800;color:{tc};font-family:'JetBrains Mono',monospace;">{arrow}{abs(chg):.2f}%</div>
            </div>""",unsafe_allow_html=True)

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Quick action panel ──
    st.markdown(f'<div style="font-size:11px;font-weight:700;color:#4a5e7a;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">⚡ QUICK ACTIONS</div>',unsafe_allow_html=True)
    qa1,qa2,qa3,qa4=st.columns(4,gap="small")
    with qa1:
        if st.button("🎯 Discover Categories", key="dash_qa_disc", use_container_width=True, type="primary"):
            nav("discover")
    with qa2:
        if st.button("⭐ My Watchlist", key="dash_qa_wl", use_container_width=True):
            nav("watchlist")
    with qa3:
        if st.button("📊 BI Analytics", key="dash_qa_bi", use_container_width=True):
            nav("bi_dashboard")
    with qa4:
        if st.button("🔔 Manage Alerts", key="dash_qa_al", use_container_width=True):
            nav("settings")

    # ── Premium teaser if free user ──
    if not is_premium():
        st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1a0d00,#0d1525);border:1px solid rgba(245,158,11,0.3);
                    border-radius:14px;padding:24px 28px;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
                <div>
                    <div style="font-size:11px;font-weight:700;color:{GOLD};letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;">👑 UPGRADE TO PREMIUM</div>
                    <div style="font-size:18px;font-weight:800;color:#e2e8f0;margin-bottom:6px;">Unlock 11 Premium Composite Categories + Real-Time Telegram Alerts</div>
                    <div style="font-size:13px;color:#6b7fa0;">Squeeze Setup · Smart Money Signal · Volatility Squeeze · Triple Lock · BI Analytics · Advanced Screener</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if gold_btn("Start Premium — $29/month →", "dash_upgrade"): nav("pricing")

    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: DISCOVER
# ─────────────────────────────────────────────────────────────
def page_discover():
    render_topbar("discover")
    st.markdown(f"""<style>
    .disc-tabs{{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 4px;padding:0;}}
    .disc-section-label{{font-size:10px;font-weight:700;color:#4a5e7a;letter-spacing:2px;text-transform:uppercase;margin:14px 0 8px;}}
    .disc-cat-header{{background:linear-gradient(135deg,#0d1525 0%,#080b14 100%);
        border:1px solid {BORDER};border-radius:14px;padding:24px 28px;margin-bottom:18px;
        box-shadow:0 2px 12px rgba(0,0,0,0.2);}}
    .disc-cat-title{{font-size:28px;font-weight:900;color:#f1f5f9;letter-spacing:-0.8px;margin-bottom:6px;}}
    .disc-cat-desc{{font-size:14px;color:#6b7fa0;line-height:1.5;}}
    .disc-cat-meta{{display:flex;gap:12px;margin-top:14px;flex-wrap:wrap;}}
    .disc-meta-pill{{font-size:11px;font-weight:600;padding:5px 12px;border-radius:20px;
        background:rgba(37,99,235,0.08);color:#93b4fd;border:1px solid rgba(37,99,235,0.2);}}
    </style>""", unsafe_allow_html=True)

    sel = st.session_state.get("discover_cat","💡 Hidden Movers")

    # Category metadata
    is_comp = sel in COMPOSITE_CATS
    tier_str=""; tier_color = GREEN
    if is_comp:
        _,tier = COMPOSITE_CATS[sel]
        tier_color = GOLD if tier=="premium" else GREEN
        tier_lbl = "PREMIUM ⭐" if tier=="premium" else "FREE"
        tier_str = f'<span class="disc-meta-pill" style="background:{"rgba(245,158,11,.1)" if tier=="premium" else "rgba(34,197,94,.1)"};color:{tier_color};border-color:{"rgba(245,158,11,.25)" if tier=="premium" else "rgba(34,197,94,.25)"};">{tier_lbl}</span>'
    desc_str = COMPOSITE_CATS[sel][0] if is_comp else f"Browse all {sel} stocks"
    is_locked = is_comp and COMPOSITE_CATS.get(sel,("",None))[1]=="premium" and not is_premium()

    # ── Big anchor header at top ──
    st.markdown(f"""
    <div class="disc-cat-header">
        <div class="disc-cat-title">{sel}</div>
        <div class="disc-cat-desc">{desc_str}</div>
        <div class="disc-cat-meta">
            {tier_str}
            <span class="disc-meta-pill">📊 Real-time Yahoo Finance data</span>
            <span class="disc-meta-pill">🔄 Updates every market session</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Category selector grid (horizontal, all visible) ──
    st.markdown('<div class="disc-section-label">⭐ Composite Categories — StockWins Exclusive</div>', unsafe_allow_html=True)

    # Render composite cats in a grid (4 per row)
    comp_items = list(COMPOSITE_CATS.items())
    for row_start in range(0, len(comp_items), 4):
        cols = st.columns(4, gap="small")
        for col_idx, (cat, (desc, tier)) in enumerate(comp_items[row_start:row_start+4]):
            with cols[col_idx]:
                is_l = tier=="premium" and not is_premium()
                safe = cat.replace(" ","_").replace("+","p").replace("→","r").replace("🌡️","T").replace("📉","D").replace("📈","U").replace("⚡","E")[:30]
                is_active = cat==sel
                lbl = cat+(" 🔒" if is_l else "")
                btn_type = "primary" if is_active else "secondary"
                if st.button(lbl, key=f"disc_c_{safe}_{row_start}_{col_idx}", use_container_width=True, type=btn_type):
                    if is_l: nav("pricing")
                    else: st.session_state.discover_cat=cat; st.rerun()

    # Standard categories
    st.markdown('<div class="disc-section-label">🌐 Standard Categories</div>', unsafe_allow_html=True)
    std_items = list(CATEGORIES.keys())
    for row_start in range(0, len(std_items), 4):
        cols = st.columns(4, gap="small")
        for col_idx, cat in enumerate(std_items[row_start:row_start+4]):
            with cols[col_idx]:
                is_active = cat==sel
                btn_type = "primary" if is_active else "secondary"
                if st.button(cat, key=f"disc_s_{cat[:24].replace(' ','_')}_{row_start}_{col_idx}", use_container_width=True, type=btn_type):
                    st.session_state.discover_cat=cat; st.rerun()

    # Spacing
    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Results area immediately below ──
    if is_locked:
        render_lock(sel)
    else:
        # Big loading indicator
        loading_placeholder = st.empty()
        loading_placeholder.markdown(f"""
        <div style="background:#0d1525;border:1px solid rgba(37,99,235,0.3);border-radius:12px;
                    padding:18px 24px;margin-bottom:14px;">
            <div style="display:flex;align-items:center;justify-content:space-between;">
                <div style="display:flex;align-items:center;gap:12px;">
                    <div class="loader-spin" style="width:18px;height:18px;border:2px solid rgba(37,99,235,0.2);border-top-color:#2563eb;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
                    <div>
                        <div style="font-size:14px;font-weight:700;color:#e2e8f0;">⚡ Analyzing {sel}</div>
                        <div style="font-size:11px;color:#374f6e;">Scanning stocks against composite criteria…</div>
                    </div>
                </div>
            </div>
        </div>
        <style>@keyframes spin{{to{{transform:rotate(360deg);}}}}</style>
        """, unsafe_allow_html=True)

        render_cat(sel, show_why=is_comp)
        loading_placeholder.empty()

    # Upgrade nudge for free users at bottom
    if not is_premium():
        st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1a0d00,#0d1525);border:1px solid rgba(245,158,11,0.25);
                    border-radius:12px;padding:18px 24px;text-align:center;">
            <div style="font-size:14px;font-weight:700;color:{GOLD};margin-bottom:4px;">👑 Unlock All 11 Premium Composite Categories</div>
            <div style="font-size:12px;color:#374f6e;">Squeeze Setup, Smart Money Signal, Volatility Squeeze, Triple Lock & more.</div>
        </div>
        """, unsafe_allow_html=True)
        if gold_btn("Upgrade to Premium →", "disc_upgrade_bottom"): nav("pricing")

# ─────────────────────────────────────────────────────────────
# PAGE: STOCK DETAIL
# ─────────────────────────────────────────────────────────────
def page_detail():
    render_topbar()
    ticker=st.session_state.get("detail_ticker")
    data=st.session_state.get("detail_data",{})

    # ── Back button ──
    bc1, bc2, _ = st.columns([1,1,5])
    with bc1:
        if st.button("← Back", key="back_det", use_container_width=True):
            go_back()
    with bc2:
        ticker_for_wl = st.session_state.get("detail_ticker","")
        wl = st.session_state.get("watchlist",[])
        in_wl = ticker_for_wl in wl
        if st.button("✅ Watching" if in_wl else "➕ Watchlist", key="top_wl_det", use_container_width=True):
            if in_wl: wl.remove(ticker_for_wl)
            else: wl.append(ticker_for_wl)
            st.session_state.watchlist = wl
            if is_authed():
                db = st.session_state.users_db.get(st.session_state.user["email"],{})
                db["watchlist"] = wl
                save_user_to_file(st.session_state.user["email"], db)
            st.rerun()
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
    if st.button("← Back", key="bi_back"): go_back()

    # ── Page intro ──
    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
        <div>
            <div style="font-size:22px;font-weight:800;color:#e2e8f0;margin-bottom:4px;">📊 BI Analytics Dashboard</div>
            <div style="font-size:13px;color:#374f6e;">Market-wide intelligence across gainers, sectors, sentiment, volume surges, and composite signals.</div>
        </div>
        <span class="tag tag-live" style="font-size:11px;padding:5px 12px;margin-top:4px;">● Live</span>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading analytics…"):
        movers=get_bi_movers(); secs=get_sectors(); idx=get_indexes(); hot=st_hot()

    gainers=sorted(movers,key=lambda x:x["pct"],reverse=True)
    losers=sorted(movers,key=lambda x:x["pct"])
    vol_ldrs=sorted(movers,key=lambda x:x["vr"],reverse=True)
    top_g=gainers[0] if gainers else {}; top_l=losers[0] if losers else {}; top_v=vol_ldrs[0] if vol_ldrs else {}
    bull_sec=max(secs,key=secs.get) if secs else "N/A"; avg_pct=sum(m["pct"] for m in movers)/len(movers) if movers else 0

    # ── Stat bar — bigger and clearer ──
    sw=st.columns(5)
    stat_data=[
        (top_g.get("t","—"), f"Top Gainer · +{top_g.get('pct',0):.1f}%", GREEN),
        (top_l.get("t","—"), f"Top Loser · {top_l.get('pct',0):.1f}%", RED),
        (top_v.get("t","—"), f"Volume King · {top_v.get('vr',0):.1f}× avg", "#60a5fa"),
        (bull_sec, f"Strongest Sector · +{secs.get(bull_sec,0):.1f}%", GREEN),
        ("Bullish" if avg_pct>0.3 else "Bearish" if avg_pct<-0.3 else "Neutral", f"Market Mood · {avg_pct:+.2f}% avg", GREEN if avg_pct>0 else RED if avg_pct<0 else "#6b7fa0"),
    ]
    for col,(v,l,c) in zip(sw,stat_data):
        col.markdown(f'<div class="stat"><div style="font-family:\'JetBrains Mono\',monospace;font-size:18px;font-weight:800;color:{c};margin-bottom:3px;">{v}</div><div style="font-size:11px;color:#374f6e;">{l}</div></div>',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    tabs=st.tabs(["📈 Leaderboards","🗺️ Sector","📡 Sentiment","🔊 Volume","🎯 Opportunity Matrix"])

    CHART_LAYOUT = dict(
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0,r=70,t=10,b=0),height=320,
        font=dict(family="Inter",size=13,color="#94a3b8"),
        xaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=12)),
        yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=13,color="#60a5fa")),
    )

    with tabs[0]:
        lc1,lc2,lc3=st.columns(3,gap="small")
        with lc1:
            st.markdown(f'<div style="font-size:14px;font-weight:700;color:{GREEN};margin-bottom:10px;">🏆 Top Gainers</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                top10g=gainers[:10]
                fig=go.Figure(go.Bar(x=[m["pct"] for m in top10g],y=[m["t"] for m in top10g],orientation="h",marker_color=GREEN,text=[f"+{m['pct']:.1f}%" for m in top10g],textposition="outside",textfont=dict(color=GREEN,size=13,family="JetBrains Mono")))
                fig.update_layout(**CHART_LAYOUT); st.plotly_chart(fig,use_container_width=True)
        with lc2:
            st.markdown(f'<div style="font-size:14px;font-weight:700;color:{RED};margin-bottom:10px;">📉 Top Losers</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                top10l=losers[:10]
                fig=go.Figure(go.Bar(x=[m["pct"] for m in top10l],y=[m["t"] for m in top10l],orientation="h",marker_color=RED,text=[f"{m['pct']:.1f}%" for m in top10l],textposition="outside",textfont=dict(color=RED,size=13,family="JetBrains Mono")))
                fig.update_layout(**CHART_LAYOUT); st.plotly_chart(fig,use_container_width=True)
        with lc3:
            st.markdown(f'<div style="font-size:14px;font-weight:700;color:#60a5fa;margin-bottom:10px;">🔊 Volume Leaders</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                top10v=vol_ldrs[:10]
                colors_v=[RED if m["vr"]>=3 else GOLD if m["vr"]>=2 else "#60a5fa" for m in top10v]
                fig=go.Figure(go.Bar(x=[m["vr"] for m in top10v],y=[m["t"] for m in top10v],orientation="h",marker_color=colors_v,text=[f"{m['vr']:.1f}×" for m in top10v],textposition="outside",textfont=dict(size=13,family="JetBrains Mono")))
                fig.update_layout(**CHART_LAYOUT); st.plotly_chart(fig,use_container_width=True)

    # Export leaderboard data
    if movers:
        bi_export_rows=[{"Ticker":m["t"],"Price":f"${m['price']:,.2f}","Change %":f"{m['pct']:+.2f}%","Volume":f"{m['vol']:,}","Vol Ratio":f"{m['vr']:.1f}×"} for m in sorted(movers,key=lambda x:x["pct"],reverse=True)]
        export_button(bi_export_rows,"stockwins_bi_leaderboard.xlsx","📥 Export Leaderboard","bi_export")

    with tabs[1]:
        sec_sorted=sorted(secs.items(),key=lambda x:x[1],reverse=True)
        if HAS_PLOTLY:
            df_s=pd.DataFrame(sec_sorted,columns=["Sector","Change %"])
            colors=[f"rgba(34,197,94,{min(0.9,abs(c)/3+0.3)})" if c>0 else f"rgba(239,68,68,{min(0.9,abs(c)/3+0.3)})" for c in df_s["Change %"]]
            fig=go.Figure(go.Bar(x=df_s["Sector"],y=df_s["Change %"],marker_color=colors,text=[f"{'▲' if c>=0 else '▼'}{abs(c):.2f}%" for c in df_s["Change %"]],textposition="outside",textfont=dict(color="#94a3b8",size=13,family="JetBrains Mono")))
            fig.add_hline(y=0,line=dict(color="rgba(255,255,255,0.15)",width=1))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=10,b=0),height=340,font=dict(size=13),xaxis=dict(showgrid=False,color="#4a5e7a",tickfont=dict(size=12)),yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a"))
            st.plotly_chart(fig,use_container_width=True)

    with tabs[2]:
        sc1,sc2=st.columns(2)
        with sc1:
            st.markdown(f'<div style="font-size:14px;font-weight:700;color:#e2e8f0;margin-bottom:10px;">🔥 Trending on StockTwits</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                sent_data=[{"ticker":t,"bull":st_sent(t)["bull"]} for t in hot[:8]]
                df_sent=pd.DataFrame(sent_data).sort_values("bull",ascending=False)
                colors_s=[GREEN if b>=60 else RED if b<40 else "#6b7fa0" for b in df_sent["bull"]]
                fig=go.Figure(go.Bar(x=df_sent["ticker"],y=df_sent["bull"],marker_color=colors_s,text=[f"{b}%" for b in df_sent["bull"]],textposition="outside",textfont=dict(size=13,family="JetBrains Mono")))
                fig.add_hline(y=50,line=dict(color="rgba(255,255,255,0.15)",width=1,dash="dot"))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=10,b=0),height=280,yaxis=dict(range=[0,115],showgrid=False,color="#4a5e7a"),xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=13)))
                st.plotly_chart(fig,use_container_width=True)
        with sc2:
            st.markdown(f'<div style="font-size:14px;font-weight:700;color:#e2e8f0;margin-bottom:10px;">👥 Most Watchlisted</div>',unsafe_allow_html=True)
            if HAS_PLOTLY:
                targets=["NVDA","TSLA","AMD","AAPL","MSTR","PLTR","GME","META"]
                wl_data=sorted([(t,st_sent(t)) for t in targets],key=lambda x:x[1].get("wl",0),reverse=True)
                wl_df=pd.DataFrame([{"t":t,"wl":s["wl"]} for t,s in wl_data])
                fig=go.Figure(go.Bar(x=wl_df["t"],y=wl_df["wl"],marker_color="rgba(96,165,250,0.7)",text=[f"{w:,}" for w in wl_df["wl"]],textposition="outside",textfont=dict(size=13,family="JetBrains Mono")))
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=10,b=0),height=280,yaxis=dict(showgrid=False,color="#4a5e7a"),xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=13)))
                st.plotly_chart(fig,use_container_width=True)

    with tabs[3]:
        surge=[m for m in movers if m["vr"]>=1.5]; surge.sort(key=lambda x:x["vr"],reverse=True)
        if surge and HAS_PLOTLY:
            sg_df=pd.DataFrame(surge[:15])
            fig=go.Figure(go.Scatter(x=sg_df["t"],y=sg_df["pct"],mode="markers",
                marker=dict(size=[min(max(vr*8,10),36) for vr in sg_df["vr"]],color=sg_df["vr"],colorscale=[[0,GREEN],[0.5,GOLD],[1,RED]],showscale=True,colorbar=dict(title="Vol×",tickfont=dict(color="#6b7fa0",size=11))),
                text=[f"{t}: {vr:.1f}×" for t,vr in zip(sg_df["t"],sg_df["vr"])],hoverinfo="text+y"))
            fig.add_hline(y=0,line=dict(color="rgba(255,255,255,0.1)",width=1))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=60,t=10,b=0),height=360,xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=13)),yaxis=dict(showgrid=True,gridcolor="rgba(255,255,255,0.04)",color="#4a5e7a",title="% Change"))
            st.plotly_chart(fig,use_container_width=True)
            st.caption("Bubble size = volume ratio. Green=1.5× | Amber=2× | Red=3×+")
        else: st.info("No significant volume surges right now.")

    with tabs[4]:
        st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
            <div style="font-size:16px;font-weight:700;color:#e2e8f0;">🎯 Composite Opportunity Matrix</div>
            <span style="background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.35);font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;">StockWins Exclusive</span>
        </div>
        <div style="font-size:12px;color:#374f6e;margin-bottom:14px;">Signal strength across 10 tickers × 5 signal types. Darker green = stronger signal.</div>""",unsafe_allow_html=True)
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
            raw=[[matrix_data.get(t,{}).get(sig,0) for sig in signal_types] for t in matrix_tickers]
            max_v=[max_vals.get(s,15) for s in signal_types]
            fig=go.Figure(go.Heatmap(z=z,x=signal_types,y=matrix_tickers,
                text=[[f"{raw[ri][ci]}/{max_v[ci]}" for ci in range(len(signal_types))] for ri in range(len(matrix_tickers))],
                texttemplate="<b>%{text}</b>",textfont=dict(size=15,color="white",family="JetBrains Mono"),
                colorscale=[[0,"#080f1e"],[0.3,"#0a2818"],[0.6,"#0d5016"],[1,GREEN]],
                showscale=True,xgap=3,ygap=3,
                colorbar=dict(thickness=14,tickfont=dict(color="#6b7fa0",size=11),title=dict(text="Score",font=dict(color="#6b7fa0",size=11)))))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=80,t=60,b=0),height=420,
                xaxis=dict(side="top",showgrid=False,color="#94a3b8",tickfont=dict(size=15,color="#94a3b8")),
                yaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=15,color="#60a5fa")))
            st.plotly_chart(fig,use_container_width=True)
            descs={"Momentum":"RSI & momentum (max 25)","Trend":"MA alignment (max 20)","Volume":"vs 20d avg (max 15)","Sentiment":"Bullish % (max 15)","Squeeze":"Short float (max 10)"}
            mc_=st.columns(len(signal_types))
            for col,sig in zip(mc_,signal_types):
                col.markdown(f'<div style="text-align:center;font-size:11px;color:#374f6e;padding:6px 4px;background:#080b14;border-radius:6px;"><div style="font-weight:700;color:#94a3b8;margin-bottom:2px;">{sig}</div>{descs[sig]}</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: WATCHLIST
# ─────────────────────────────────────────────────────────────
def page_watchlist():
    render_topbar("watchlist")
    st.markdown('<div class="pg">',unsafe_allow_html=True)

    wl=st.session_state.get("watchlist",[])
    if st.button("← Back", key="wl_back"): go_back()
    hdr1,hdr2=st.columns([3,1])
    with hdr1: st.markdown('<div style="font-size:22px;font-weight:800;color:#e2e8f0;margin-bottom:4px;">⭐ My Watchlist</div>',unsafe_allow_html=True)
    with hdr2:
        if wl and st.button("🗑 Clear All",key="wl_clear_top",use_container_width=True):
            st.session_state.watchlist=[]; st.rerun()

    if not wl:
        st.markdown(f'''<div class="card" style="text-align:center;padding:48px 24px;">
            <div style="font-size:36px;margin-bottom:12px;">📋</div>
            <div style="font-size:18px;font-weight:700;color:#e2e8f0;margin-bottom:8px;">Your watchlist is empty</div>
            <div style="font-size:13px;color:#374f6e;margin-bottom:20px;">Browse composite categories and click ➕ Watchlist on any stock to track it here.</div>
        </div>''',unsafe_allow_html=True)
        if st.button("Browse Stocks →",key="wl_browse3",type="primary"): nav("discover")
        st.markdown('</div>',unsafe_allow_html=True)
        return

    # Load watchlist data
    rows=[]; prog=st.progress(0,"Loading watchlist…")
    for i,t in enumerate(wl):
        prog.progress((i+1)/len(wl),f"Loading {t}…")
        try:
            q=get_quote(t)
            if not q: continue
            df=yf_ohlcv(t,30); info=yf_fund(t); sent=st_sent(t)
            sc,bd,op,risk,_=compute_scores(df,info,sent)
            rec_lbl,rec_clr,_=get_recommendation(sc,bd,info)
            pct=q.get("pct",0); price=q.get("price",0)
            cc_=GREEN if pct>=0 else RED
            rows.append({
                "Ticker":t,"Name":q.get("name","")[:22],"Price":f"${price:,.2f}",
                "Change":f"{pct:+.2f}%","Signal":rec_lbl,"Score":sc,
                "Risk":risk,"Sector":info.get("sector","N/A"),
                "Short Float":f"{(info.get('sf',0) or 0)*100:.1f}%",
                "_pct":pct,"_cc":cc_,"_rec_clr":rec_clr
            })
        except: continue
    prog.empty()

    if not rows:
        st.info("Could not load watchlist data. Try again in a moment.")
        st.markdown('</div>',unsafe_allow_html=True)
        return

    # Premium score chart
    if is_premium() and HAS_PLOTLY:
        st.markdown('<div style="font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:8px;">📊 Score Distribution</div>',unsafe_allow_html=True)
        scores=[r["Score"] for r in rows]; tickers=[r["Ticker"] for r in rows]
        bar_colors=[GREEN if s>=65 else GOLD if s>=40 else RED for s in scores]
        fig=go.Figure(go.Bar(x=tickers,y=scores,marker_color=bar_colors,
            text=scores,textposition="outside",textfont=dict(size=13,family="JetBrains Mono")))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0,r=0,t=0,b=0),height=160,
            yaxis=dict(range=[0,110],showgrid=False,color="#4a5e7a"),
            xaxis=dict(showgrid=False,color="#60a5fa",tickfont=dict(family="JetBrains Mono",size=12)))
        st.plotly_chart(fig,use_container_width=True)

    # Stock rows
    display_rows=[{k:v for k,v in r.items() if not k.startswith("_")} for r in rows]
    # Export button
    ex1,ex2=st.columns([1,3])
    with ex1:
        export_button(display_rows, "stockwins_watchlist.xlsx", "📥 Export Watchlist", "wl_export")

    st.dataframe(pd.DataFrame(display_rows),use_container_width=True,hide_index=True)

    # Quick actions
    st.markdown('<div style="margin-top:12px;">',unsafe_allow_html=True)
    for r in rows:
        t=r["Ticker"]; cc_=r["_cc"]; rec_clr=r["_rec_clr"]
        r1,r2,r3=st.columns([3,1,1],gap="small")
        with r1:
            st.markdown(f'''<div class="sr" style="padding:10px 14px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <span class="sr-tick">{t}</span>
                    <span style="font-size:11px;color:#374f6e;">{r["Name"]}</span>
                    <span style="background:{rec_clr}22;color:{rec_clr};font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;border:1px solid {rec_clr}44;">{r["Signal"]}</span>
                </div>
                <div style="display:flex;gap:16px;margin-top:4px;font-size:12px;">
                    <span style="font-family:'JetBrains Mono',monospace;color:#e2e8f0;font-weight:700;">{r["Price"]}</span>
                    <span style="font-weight:700;color:{cc_};">{r["Change"]}</span>
                    <span style="color:#374f6e;">Score: {r["Score"]}</span>
                    <span style="color:#374f6e;">{r["Risk"]} Risk</span>
                </div>
            </div>''',unsafe_allow_html=True)
        with r2:
            if st.button("📊 Report",key=f"wl_rep_{t}",use_container_width=True,type="primary"):
                st.session_state.detail_ticker=t; st.session_state.detail_data={}; nav("stock_detail")
        with r3:
            if st.button("✕ Remove",key=f"wl_rm_{t}",use_container_width=True):
                wl.remove(t); st.session_state.watchlist=wl; st.rerun()
    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: SCREENER
# ─────────────────────────────────────────────────────────────
def page_screener():
    render_topbar("screener")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    if st.button("← Back", key="scr_back"): go_back()
    st.markdown('<div style="font-size:22px;font-weight:800;color:#e2e8f0;margin-bottom:4px;">🔍 Advanced Stock Screener</div>',unsafe_allow_html=True)
    st.markdown('<div style="font-size:13px;color:#374f6e;margin-bottom:16px;">Filter stocks by RSI, MACD, volume, sentiment, and more. Save your best screens.</div>',unsafe_allow_html=True)
    if not is_premium():
        render_lock("Advanced Stock Screener")
        st.markdown('</div>',unsafe_allow_html=True); return
    with st.expander("⚙️ Screener Filters",expanded=True):
        c1,c2,c3,c4=st.columns(4)
        with c1:
            min_sc=st.slider("Min SW Score",0,100,40,help="StockWins composite score (0-100). 65+ = strong signal")
            min_rsi=st.slider("Min RSI",0,100,20,help="Minimum RSI. Below 30 = oversold")
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
            sorted_results = pd.DataFrame(results).sort_values("Score",ascending=False)
            sc_ex1,sc_ex2=st.columns([1,3])
            with sc_ex1:
                scr_rows=sorted_results.to_dict("records")
                export_button(scr_rows, "stockwins_screener.xlsx", "📥 Export Results", "scr_export")
            st.dataframe(sorted_results,use_container_width=True,hide_index=True)
        else: st.info("No matches. Try relaxing filters.")
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: PRICING
# ─────────────────────────────────────────────────────────────
def page_pricing():
    render_topbar("pricing")

    # ── Embedded Stripe checkout (show when session created) ──
    if st.session_state.get("_stripe_embed"):
        embed = st.session_state["_stripe_embed"]
        plan_name = "Premium Monthly ($29/mo)" if embed["plan"]=="premium" else "Annual Plan ($199/yr)"
        render_topbar("pricing")
        st.markdown(f"""
        <div style="text-align:center;padding:32px 0 20px;">
            <div style="font-size:11px;font-weight:700;color:{BLUE};letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">Secure Checkout</div>
            <div style="font-size:26px;font-weight:800;color:#e2e8f0;margin-bottom:6px;">Complete Your Subscription</div>
            <div style="font-size:13px;color:#374f6e;">{plan_name} · Powered by Stripe · SSL Encrypted</div>
        </div>
        """, unsafe_allow_html=True)
        import streamlit.components.v1 as _comp
        _comp.html(f"""
        <script src="https://js.stripe.com/v3/"></script>
        <style>
        body{{margin:0;padding:20px;background:#07090f;font-family:Inter,sans-serif;}}
        #checkout-form{{background:#0d1525;border:1px solid rgba(255,255,255,0.1);border-radius:14px;padding:24px;max-width:500px;margin:0 auto;}}
        #submit-btn{{width:100%;padding:14px;background:linear-gradient(135deg,#1d4ed8,#2563eb);color:#fff;border:none;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer;margin-top:16px;}}
        #submit-btn:hover{{background:linear-gradient(135deg,#1e40af,#1d4ed8);}}
        #submit-btn:disabled{{opacity:0.6;cursor:not-allowed;}}
        #msg{{color:#f87171;font-size:12px;margin-top:8px;text-align:center;}}
        </style>
        <div id="checkout-form">
        <div id="payment-element"></div>
        <button id="submit-btn" onclick="submitPayment()">🔒 Subscribe Now</button>
        <div id="msg"></div>
        </div>
        <script>
        var stripe=Stripe('{embed["pub_key"]}');
        var elements=stripe.elements({{clientSecret:'{embed["client_secret"]}',appearance:{{theme:'night',variables:{{colorPrimary:'#2563eb',colorBackground:'#0d1525',colorText:'#e2e8f0',colorDanger:'#ef4444',borderRadius:'8px'}}}}}});
        var paymentElement=elements.create('payment');
        paymentElement.mount('#payment-element');
        async function submitPayment(){{
            var btn=document.getElementById('submit-btn');
            var msg=document.getElementById('msg');
            btn.disabled=true;btn.textContent='Processing...';
            var {{error}}=await stripe.confirmPayment({{
                elements,confirmParams:{{return_url:'{embed["return_url"]}'}},
            }});
            if(error){{msg.textContent=error.message;btn.disabled=false;btn.textContent='🔒 Subscribe Now';}}
        }}
        </script>
        """, height=450, scrolling=False)
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("← Cancel and go back to pricing", key="cancel_embed"):
            st.session_state.pop("_stripe_embed", None)
            st.rerun()
        return

    st.markdown('<div class="pg">', unsafe_allow_html=True)

    # ── Header ──
    st.markdown(f"""
    <div style="text-align:center;padding:32px 0 28px;">
        <div style="font-size:11px;font-weight:700;color:{BLUE};letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">Simple, Transparent Pricing</div>
        <div style="font-size:34px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Choose Your Plan</div>
        <div style="font-size:14px;color:#374f6e;">No hidden fees. No API keys. Cancel anytime.</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Card CSS ──
    st.markdown(f"""<style>
    .sw-pc-col {{
        background:{CARD};border:1px solid rgba(255,255,255,0.1);
        border-radius:14px;padding:24px 20px;
        transition:all 0.25s cubic-bezier(0.4,0,0.2,1);
        display:flex;flex-direction:column;box-sizing:border-box;
        min-height:560px;
    }}
    .sw-pc-col:hover{{border-color:rgba(37,99,235,0.35);}}
    .sw-pc-sel-blue{{
        border:2px solid {BLUE}!important;
        background:linear-gradient(160deg,#04091d,{CARD})!important;
        box-shadow:0 16px 48px rgba(37,99,235,0.35)!important;
        transform:translateY(-6px)!important;
    }}
    .sw-pc-sel-gold{{
        border:2px solid {GOLD}!important;
        background:linear-gradient(160deg,#160c00,#0f0800,{CARD})!important;
        box-shadow:0 16px 48px rgba(245,158,11,0.35)!important;
        transform:translateY(-6px)!important;
    }}
    .sw-pc-badge{{font-size:9px;font-weight:700;padding:3px 10px;border-radius:20px;display:inline-block;letter-spacing:1px;margin-bottom:10px;}}
    .sw-pc-feats{{font-size:12px;color:#374f6e;line-height:2.3;flex:1;}}
    .sw-pc-dim{{color:#1e3050;}}
    /* CTA button integrated into card bottom */
    /* CTA button sits flush under each card via negative margin */
    .sw-pc-cta,.sw-pc-cta-active,.sw-pc-cta-gold-active{{margin-top:-2px!important;}}
    .sw-pc-cta .stButton>button,
    .sw-pc-cta-active .stButton>button,
    .sw-pc-cta-gold-active .stButton>button{{
        border-radius:0 0 14px 14px!important;
        margin-top:0!important;
        font-size:14px!important;font-weight:700!important;
        padding:15px 0!important;
        min-height:52px!important;
        letter-spacing:0.3px!important;
        border-top:none!important;
        border-left:1px solid rgba(255,255,255,0.1)!important;
        border-right:1px solid rgba(255,255,255,0.1)!important;
        border-bottom:1px solid rgba(255,255,255,0.1)!important;
        background:rgba(255,255,255,0.04)!important;
        color:#6b7fa0!important;
        transition:all 0.2s ease!important;
    }}
    .sw-pc-cta .stButton>button:hover{{
        background:rgba(37,99,235,0.1)!important;
        color:#93b4fd!important;
        border-color:rgba(37,99,235,0.3)!important;
    }}
    .sw-pc-cta-active .stButton>button{{
        background:linear-gradient(135deg,#1d4ed8,#2563eb)!important;
        color:#fff!important;
        border-color:{BLUE}!important;
        box-shadow:0 4px 20px rgba(37,99,235,0.4)!important;
    }}
    .sw-pc-cta-active .stButton>button:hover{{
        background:linear-gradient(135deg,#1e40af,#1d4ed8)!important;
    }}
    .sw-pc-cta-gold-active .stButton>button{{
        background:linear-gradient(135deg,#92400e,#d97706,#f59e0b)!important;
        color:#1a0800!important;
        border-color:{GOLD}!important;
        box-shadow:0 4px 20px rgba(245,158,11,0.4)!important;
        font-weight:800!important;
    }}
    /* Remove gap between card and button */
    .sw-pc-col{{border-radius:14px 14px 0 0!important;margin-bottom:0!important;}}
    [data-testid="stHorizontalBlock"]:has(.sw-pc-col){{align-items:flex-end!important;}}
    </style>""", unsafe_allow_html=True)

    if "sel_plan" not in st.session_state:
        st.session_state.sel_plan = "premium"
    sel = st.session_state.sel_plan

    def card_badge(plan):
        if plan == sel:
            return f'<span class="sw-pc-badge" style="background:#1e3a8a;color:#93b4fd;">✓ SELECTED</span>'
        if plan == "premium":
            return f'<span class="sw-pc-badge" style="background:rgba(37,99,235,0.15);color:{BLUE};">⭐ MOST POPULAR</span>'
        if plan == "annual":
            return f'<span class="sw-pc-badge" style="background:linear-gradient(90deg,#92400e,#d97706);color:#fff8e1;">👑 BEST VALUE — SAVE 43%</span>'
        return f'<span class="sw-pc-badge" style="background:rgba(255,255,255,0.06);color:#4a5e7a;">Free Plan</span>'

    c1, c2, c3 = st.columns(3, gap="small")

    # ── FREE ──
    with c1:
        cls = "sw-pc-sel-blue" if sel=="free" else ""
        st.markdown(f"""<div class="sw-pc-col {cls}">
            {card_badge("free")}
            <div style="font-size:14px;font-weight:600;color:#94a3b8;margin-bottom:2px;">Free</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:44px;font-weight:800;color:#e2e8f0;line-height:1.1;margin-bottom:2px;">$0</div>
            <div style="font-size:11px;color:#374f6e;margin-bottom:14px;">forever · no card needed</div>
            <hr style="border-color:{BORDER};margin:10px 0 14px;">
            <div class="sw-pc-feats">
            ✅&nbsp; Market overview &amp; indexes<br>
            ✅&nbsp; RSI &amp; MACD signals<br>
            ✅&nbsp; Plain-English insights<br>
            ✅&nbsp; 7 composite categories<br>
            ✅&nbsp; Watchlist (10 stocks)<br>
            ✅&nbsp; BUY / AVOID signals<br>
            <span class="sw-pc-dim">❌&nbsp; 10 premium categories<br>
            ❌&nbsp; Short squeeze scanner<br>
            ❌&nbsp; Advanced screener<br>
            ❌&nbsp; BI analytics &amp; score details</span>
            </div>
        </div>""", unsafe_allow_html=True)
        cta_cls = "sw-pc-cta-active" if sel=="free" else "sw-pc-cta"
        st.markdown(f'<div class="{cta_cls}">', unsafe_allow_html=True)
        btn_lbl = "Get Started Free →" if sel=="free" else "Select Free Plan"
        if st.button(btn_lbl, key="pc_free", use_container_width=True, type="primary" if sel=="free" else "secondary"):
            if sel != "free":
                st.session_state.sel_plan = "free"; st.rerun()
            else:
                nav("signup" if not is_authed() else "dashboard")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── PREMIUM ──
    with c2:
        cls = "sw-pc-sel-blue" if sel=="premium" else ""
        st.markdown(f"""<div class="sw-pc-col {cls}">
            {card_badge("premium")}
            <div style="font-size:14px;font-weight:600;color:#e2e8f0;margin-bottom:2px;">Premium Monthly</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:44px;font-weight:800;color:#e2e8f0;line-height:1.1;margin-bottom:2px;">$29</div>
            <div style="font-size:11px;color:#374f6e;margin-bottom:14px;">per month · cancel anytime</div>
            <hr style="border-color:{BORDER};margin:10px 0 14px;">
            <div class="sw-pc-feats">
            ✅&nbsp; Everything in Free<br>
            ✅&nbsp; All 17 composite categories<br>
            ✅&nbsp; Short squeeze scanner<br>
            ✅&nbsp; Advanced screener<br>
            ✅&nbsp; Full BI analytics &amp; charts<br>
            ✅&nbsp; Score breakdowns<br>
            ✅&nbsp; Volume surge detection<br>
            ✅&nbsp; Unlimited watchlist<br>
            ✅&nbsp; Watchlist score analytics<br>
            ✅&nbsp; Saved screener configs
            </div>
        </div>""", unsafe_allow_html=True)
        cta_cls = "sw-pc-cta-active" if sel=="premium" else "sw-pc-cta"
        st.markdown(f'<div class="{cta_cls}">', unsafe_allow_html=True)
        btn_lbl = "🚀 Get Premium →" if sel=="premium" else "🚀 Select Premium"
        if st.button(btn_lbl, key="pc_premium", use_container_width=True, type="primary" if sel=="premium" else "secondary"):
            if sel != "premium":
                st.session_state.sel_plan = "premium"; st.rerun()
            else:
                if not is_authed(): st.session_state["_pending_checkout"]="premium"; nav("signup")
                else: _do_checkout("premium")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── ANNUAL ──
    with c3:
        cls = "sw-pc-sel-gold" if sel=="annual" else ""
        st.markdown(f"""<div class="sw-pc-col {cls}">
            {card_badge("annual")}
            <div style="font-size:14px;font-weight:600;color:#e2e8f0;margin-bottom:2px;">Annual Plan</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:44px;font-weight:800;color:{GOLD};line-height:1.1;margin-bottom:2px;">$199</div>
            <div style="font-size:11px;color:#374f6e;margin-bottom:14px;">per year · $16.58/mo · save $149</div>
            <hr style="border-color:rgba(245,158,11,0.15);margin:10px 0 14px;">
            <div class="sw-pc-feats">
            ✅&nbsp; Everything in Premium<br>
            ✅&nbsp; Priority support<br>
            ✅&nbsp; Early feature access<br>
            ✅&nbsp; Export to CSV<br>
            ✅&nbsp; Custom alert schedules<br>
            ✅&nbsp; API access (Q3 2026)<br>
            ✅&nbsp; Backtesting (coming)<br>
            ✅&nbsp; Portfolio tracker (coming)
            </div>
        </div>""", unsafe_allow_html=True)
        cta_cls = "sw-pc-cta-gold-active" if sel=="annual" else "sw-pc-cta"
        st.markdown(f'<div class="{cta_cls}">', unsafe_allow_html=True)
        btn_lbl = "👑 Get Annual — Best Value →" if sel=="annual" else "👑 Select Annual Plan"
        if st.button(btn_lbl, key="pc_annual", use_container_width=True, type="primary" if sel=="annual" else "secondary"):
            if sel != "annual":
                st.session_state.sel_plan = "annual"; st.rerun()
            else:
                if not is_authed(): st.session_state["_pending_checkout"]="annual"; nav("signup")
                else: _do_checkout("annual")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Stripe status bar ──
    if stripe_configured():
        st.markdown("""<div style="text-align:center;margin-top:16px;">
            <span style="font-size:11px;color:#374f6e;">🔒 Secure payments by </span>
            <span style="font-size:12px;font-weight:800;color:#6775ba;letter-spacing:-0.5px;">stripe</span>
            <span style="font-size:11px;color:#374f6e;"> · SSL encrypted · Cancel anytime · 30-day refund policy</span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div style="background:#0e1421;border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:12px 16px;margin-top:12px;font-size:12px;color:#374f6e;">
        ⚙️ <strong style="color:{GOLD};">Payment processing not yet configured.</strong>
        Add <code>STRIPE_SECRET_KEY</code>, <code>STRIPE_PRICE_MONTHLY</code>, <code>STRIPE_PRICE_ANNUAL</code>, <code>APP_URL</code> to Streamlit Secrets, then reboot.
        In the meantime email <a href="mailto:support@stockwins.com" style="color:#93b4fd;">support@stockwins.com</a> to upgrade manually.
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="disc" style="margin-top:14px;">⚠️ Educational platform only. Not financial advice. Trading involves risk.</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


def _do_checkout(plan):
    """Trigger Stripe checkout — embed if possible, redirect as fallback."""
    email = st.session_state.user["email"]
    with st.spinner("Setting up secure checkout..."):
        url, err = create_checkout_session(plan, email)
    if err:
        st.error(f"Checkout error: {err}")
        return
    # Try embedded checkout if client_secret available (newer Stripe SDK)
    # Otherwise store URL for link_button display
    st.session_state["_redirect_url"] = url
    st.rerun()


# ─────────────────────────────────────────────────────────────
# PAGE: SETTINGS
# ─────────────────────────────────────────────────────────────
def page_settings():
    render_topbar()
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    # Settings header with user info
    db_u_hdr = st.session_state.users_db.get(st.session_state.user["email"],{}) if is_authed() else {}
    role_disp = {"owner":"👑 Owner","admin":"🛡️ Admin","premium":"⭐ Premium","free":"👤 Free"}.get(st.session_state.get("role","free"),"👤 Free")
    plan_disp = db_u_hdr.get("plan","Free")
    st.markdown(f'''<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
        <div>
            <div style="font-size:22px;font-weight:800;color:#e2e8f0;">⚙️ Account Settings</div>
            <div style="font-size:13px;color:#374f6e;margin-top:3px;">{st.session_state.user.get("name","")} · {st.session_state.user.get("email","")}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:13px;font-weight:700;color:{GOLD if is_premium() else "#6b7fa0"};">{role_disp}</div>
            <div style="font-size:11px;color:#2a3a52;">Billing: {plan_disp}</div>
        </div>
    </div>''',unsafe_allow_html=True)
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
        # ── Section 1: Proprietary Signals (default ON for premium) ──
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#04200d,#0d1525);border:1px solid rgba(34,197,94,0.25);
                    border-radius:12px;padding:16px 20px;margin-bottom:16px;">
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
                <div>
                    <div style="font-size:13px;font-weight:700;color:#4ade80;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:4px;">✨ AUTOMATIC PROPRIETARY SIGNALS</div>
                    <div style="font-size:13px;color:#e2e8f0;font-weight:600;margin-bottom:4px;">Default ON for Premium subscribers</div>
                    <div style="font-size:12px;color:#6b7fa0;line-height:1.7;">When a stock enters one of our composite categories (Squeeze Setup, Hidden Mover, Sentiment Flip, etc.), you automatically get a notification. No configuration needed.</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if is_premium():
            db_user_a = st.session_state.users_db.get(st.session_state.user["email"],{}) if is_authed() else {}
            prop_signals_enabled = db_user_a.get("prop_signals_enabled", True)  # Default ON
            current_cat_alerts = db_user_a.get("category_alerts", list(COMPOSITE_CATS.keys()))

            colp1, colp2 = st.columns([3,1], gap="small")
            with colp1:
                st.markdown(f"""<div style="background:#0d1525;border:1px solid {BORDER};border-radius:10px;padding:14px;">
                    <div style="font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:8px;">📡 Receiving alerts for {len(current_cat_alerts)} of {len(COMPOSITE_CATS)} composite categories</div>
                    <div style="font-size:11px;color:#374f6e;line-height:1.7;">{', '.join([c.split(' ')[1] if ' ' in c else c for c in current_cat_alerts[:6]])}{'...' if len(current_cat_alerts)>6 else ''}</div>
                </div>""", unsafe_allow_html=True)
            with colp2:
                new_state = st.toggle("Auto-Signals", value=prop_signals_enabled, key="prop_toggle",
                                       help="Toggle automatic proprietary signal notifications")
                if new_state != prop_signals_enabled:
                    st.session_state.users_db[st.session_state.user["email"]]["prop_signals_enabled"] = new_state
                    save_user_to_file(st.session_state.user["email"], st.session_state.users_db[st.session_state.user["email"]])
                    st.toast(f"{'✅ Proprietary signals enabled' if new_state else '⏸ Proprietary signals paused'}", icon="🔔")

            with st.expander("⚙️ Customize which composite categories alert me", expanded=False):
                st.markdown('<div style="font-size:12px;color:#374f6e;margin-bottom:8px;">Uncheck any category you don\'t want to be notified about.</div>', unsafe_allow_html=True)
                selected_cats = []
                cat_cols = st.columns(2, gap="small")
                for idx, cat in enumerate(list(COMPOSITE_CATS.keys())):
                    with cat_cols[idx % 2]:
                        if st.checkbox(cat, value=cat in current_cat_alerts, key=f"propcat_{idx}"):
                            selected_cats.append(cat)
                if st.button("💾 Save Category Preferences", key="save_prop_cats", type="primary", use_container_width=True):
                    st.session_state.users_db[st.session_state.user["email"]]["category_alerts"] = selected_cats
                    save_user_to_file(st.session_state.user["email"], st.session_state.users_db[st.session_state.user["email"]])
                    st.success(f"✅ You'll receive alerts for {len(selected_cats)} categories")
                    st.rerun()
        else:
            st.markdown(f"""<div class="card card-gold">
                <div style="font-size:13px;font-weight:700;color:{GOLD};margin-bottom:6px;">👑 Premium Required</div>
                <div style="font-size:12px;color:#374f6e;line-height:1.7;">Automatic proprietary signal alerts (Squeeze Setup, Hidden Mover, Sentiment Flip, Smart Money Signal, etc.) are part of the Premium plan.</div>
            </div>""", unsafe_allow_html=True)
            if gold_btn("Upgrade to Receive Auto-Signals","prop_upgrade"): nav("pricing")

        st.markdown('<div class="div-line"></div>',unsafe_allow_html=True)

        # ── Section 2: Custom Alerts (user-configured for specific tickers) ──
        alerts=st.session_state.get("alerts",[])
        st.markdown(f'<div style="font-size:15px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">🎯 Custom Alerts</div>',unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:12px;color:#374f6e;margin-bottom:14px;">Set up alerts for specific tickers and conditions (price, volume, RSI, etc.). These run alongside the automatic proprietary signals above.</div>',unsafe_allow_html=True)

        with st.form("af",clear_on_submit=True):
            fc1,fc2,fc3=st.columns(3)
            with fc1: at=st.text_input("Ticker",placeholder="AAPL",label_visibility="visible").upper().strip()
            with fc2:
                atype_lbl=st.selectbox("Alert Type",["Price Above","Price Below","% Change Up",
                    "Volume Spike (×avg)","RSI Oversold (<30)","RSI Overbought (>70)","Sentiment Bullish %"],label_visibility="visible")
            with fc3: ap=st.number_input("Threshold",value=100.0,min_value=0.0,step=0.5,label_visibility="visible")
            ch_col1,ch_col2,ch_col3=st.columns(3)
            with ch_col1: ch_email=st.checkbox("📧 Email",value=True)
            with ch_col2: ch_tg=st.checkbox("✈️ Telegram",value=False,disabled=not is_premium(),help="Premium only")
            with ch_col3: ch_push=st.checkbox("🔔 Browser Push",value=False,disabled=not is_premium(),help="Premium only")
            if st.form_submit_button("➕ Add Custom Alert",type="primary",use_container_width=True) and at:
                type_map={"Price Above":"price_above","Price Below":"price_below","% Change Up":"pct_change",
                          "Volume Spike (×avg)":"volume_spike","RSI Oversold (<30)":"rsi_oversold",
                          "RSI Overbought (>70)":"rsi_overbought","Sentiment Bullish %":"sentiment_flip"}
                channels=[]
                if ch_email: channels.append("email")
                if ch_tg and is_premium(): channels.append("telegram")
                if ch_push and is_premium(): channels.append("browser")
                new_a={"id":f"{at}_{time.time():.0f}","ticker":at,"type":type_map.get(atype_lbl,"price_above"),
                       "threshold":ap,"label":f"{at} {atype_lbl} {ap}","channels":channels or ["email"],
                       "active":True,"created":datetime.now().strftime("%Y-%m-%d %H:%M")}
                alerts.append(new_a); st.session_state.alerts=alerts
                if is_authed(): save_alerts_to_file(st.session_state.user["email"], alerts)
                st.toast(f"🔔 Alert set: {at} {atype_lbl} {ap}", icon="✅")
                st.success(f"✅ Alert active: {at} will notify you via {', '.join(channels or ['email'])}")

        if alerts:
            st.caption(f"{len(alerts)} active custom alert{'s' if len(alerts)!=1 else ''}")
            for i,a in enumerate(alerts):
                ac1,ac2,ac3=st.columns([5,1,1])
                with ac1:
                    ticker=a.get("ticker",""); lbl=a.get("label",ticker)
                    chs=", ".join(["📧" if c=="email" else "✈️" if c=="telegram" else "🔔" for c in a.get("channels",["email"])])
                    dot=f'<span style="color:{"#4ade80" if a.get("active",True) else "#4a5e7a"};">●</span>'
                    st.markdown(f'<div class="card" style="padding:9px 14px;margin-bottom:4px;">{dot} <span style="font-family:\'JetBrains Mono\',monospace;color:#60a5fa;font-weight:700;">{ticker}</span> <span style="font-size:12px;color:#374f6e;margin-left:8px;">{lbl}</span><span style="font-size:11px;color:#2a3a52;float:right;">{chs}</span></div>',unsafe_allow_html=True)
                with ac2:
                    tog="Pause" if a.get("active",True) else "Resume"
                    if st.button(tog,key=f"tg_{i}",use_container_width=True):
                        alerts[i]["active"]=not a.get("active",True); st.session_state.alerts=alerts
                        if is_authed(): save_alerts_to_file(st.session_state.user["email"], alerts)
                        st.rerun()
                with ac3:
                    if st.button("🗑",key=f"da_{i}",use_container_width=True):
                        alerts.pop(i); st.session_state.alerts=alerts
                        if is_authed(): save_alerts_to_file(st.session_state.user["email"], alerts)
                        st.rerun()
        else:
            st.caption("No custom alerts yet. Use the form above to add one.")

        st.markdown('<div class="div-line"></div>',unsafe_allow_html=True)

        # Telegram setup for premium
        if is_premium():
            st.markdown('<div style="font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:8px;">✈️ Telegram Setup</div>',unsafe_allow_html=True)
            try: tg_token_set = bool(st.secrets.get("TELEGRAM_BOT_TOKEN",""))
            except: tg_token_set = False
            db_user2=st.session_state.users_db.get(st.session_state.user["email"],{}) if is_authed() else {}
            current_tg=db_user2.get("telegram_chat_id","")
            if not tg_token_set:
                st.markdown(f'<div class="card" style="font-size:12px;color:#374f6e;">Add <code>TELEGRAM_BOT_TOKEN</code> to Streamlit Secrets to enable Telegram alerts.</div>',unsafe_allow_html=True)
            else:
                if current_tg:
                    st.markdown(f'<div style="font-size:12px;color:#4ade80;margin-bottom:8px;">✅ Telegram connected (Chat ID: {current_tg})</div>',unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="font-size:12px;color:#374f6e;line-height:1.8;margin-bottom:8px;">1. Open Telegram → search <strong style="color:#e2e8f0;">@StockWinsAlertsBot</strong><br>2. Send /start to get your Chat ID<br>3. Paste it below</div>',unsafe_allow_html=True)
                with st.form("tg_form"):
                    tg_id=st.text_input("Your Telegram Chat ID",value=current_tg,placeholder="1234567890",label_visibility="visible")
                    if st.form_submit_button("Save Telegram Connection",type="primary"):
                        uemail=st.session_state.user["email"]
                        st.session_state.users_db[uemail]["telegram_chat_id"]=tg_id.strip()
                        save_user_to_file(uemail, st.session_state.users_db[uemail])
                        st.success("✅ Telegram connected!")

        if not is_premium():
            st.markdown(f'<div class="card card-gold" style="margin-top:12px;"><div style="font-size:12px;font-weight:700;color:{GOLD};margin-bottom:4px;">👑 Premium Alert Channels</div><div style="font-size:12px;color:#374f6e;">Upgrade to Premium for instant Telegram alerts and real-time browser push notifications on composite category signals.</div></div>',unsafe_allow_html=True)

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
        role = st.session_state.get("role","free")
        rl   = {"free":"Free","premium":"Premium Monthly","admin":"Admin","owner":"Owner"}.get(role,"Free")
        rc_  = {"free":"#6b7fa0","premium":"#a78bfa","admin":"#93b4fd","owner":GOLD}.get(role,"#6b7fa0")
        plan_detail = db_user.get("plan","Free")

        st.markdown(f"""<div class="card card-blue" style="margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <div style="font-size:15px;font-weight:800;color:#e2e8f0;">
                        Current Plan: <span style="color:{rc_};">{rl}</span>
                    </div>
                    <div style="font-size:12px;color:#374f6e;margin-top:4px;">Member since {db_user.get('joined','N/A')}</div>
                    <div style="font-size:12px;color:#374f6e;">Billing: {plan_detail}</div>
                </div>
                {'<span style="background:rgba(34,197,94,0.12);color:#4ade80;font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;border:1px solid rgba(34,197,94,0.3);">ACTIVE</span>' if is_premium() else '<span style="background:rgba(100,116,139,0.12);color:#64748b;font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;border:1px solid rgba(100,116,139,0.3);">FREE PLAN</span>'}
            </div>
        </div>""", unsafe_allow_html=True)

        if not is_premium():
            st.markdown('<div style="font-size:12px;color:#374f6e;margin-bottom:10px;">Upgrade to unlock all 17 composite categories, advanced screener, BI analytics, and more.</div>',unsafe_allow_html=True)
            uc1,uc2=st.columns(2,gap="small")
            with uc1:
                if gold_btn("👑 Upgrade to Premium — $29/mo","set_prem_mo"):
                    if stripe_configured():
                        url,err=create_checkout_session("premium",st.session_state.user["email"])
                        if url: st.session_state["_redirect_url"]=url; st.rerun()
                        else: st.error(err)
                    else: nav("pricing")
            with uc2:
                if st.button("👑 Get Annual — $199/yr (Save 43%)",key="set_prem_yr",use_container_width=True):
                    if stripe_configured():
                        url,err=create_checkout_session("annual",st.session_state.user["email"])
                        if url: st.session_state["_redirect_url"]=url; st.rerun()
                        else: st.error(err)
                    else: nav("pricing")
        else:
            st.markdown(f'<div style="font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:10px;">Manage Your Subscription</div>',unsafe_allow_html=True)
            if stripe_configured():
                if st.button("🔗 Open Billing Portal →", key="set_portal", type="primary", use_container_width=False):
                    url, err = create_portal_session(st.session_state.user["email"])
                    if url:
                        import streamlit.components.v1 as _c
                        _c.html(f'<script>window.top.open("{url}","_blank");</script>',height=0)
                        st.info("Billing portal opened in a new tab.")
                    else:
                        st.error(err)
                st.markdown(f'<div style="font-size:12px;color:#374f6e;margin-top:8px;line-height:1.7;">The billing portal lets you: update payment method · view invoices · cancel subscription · download receipts</div>',unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="background:#0e1421;border:1px solid {BORDER};border-radius:7px;padding:12px 14px;font-size:12px;color:#374f6e;">To manage your subscription, email <a href="mailto:support@stockwins.com" style="color:#93b4fd;">support@stockwins.com</a></div>',unsafe_allow_html=True)

        if is_premium():
            st.markdown('<div class="div-line"></div>',unsafe_allow_html=True)
            st.markdown('<div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:8px;">Subscription Details</div>',unsafe_allow_html=True)
            sc1,sc2,sc3=st.columns(3)
            sc1.markdown(f'<div class="stat"><div class="stat-v" style="font-size:14px;color:#a78bfa;">{rl}</div><div class="stat-l">Current Plan</div></div>',unsafe_allow_html=True)
            sc2.markdown(f'<div class="stat"><div class="stat-v" style="font-size:14px;color:{GREEN};">Active</div><div class="stat-l">Status</div></div>',unsafe_allow_html=True)
            sc3.markdown(f'<div class="stat"><div class="stat-v" style="font-size:14px;color:#e2e8f0;">{plan_detail}</div><div class="stat-l">Billing Cycle</div></div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE: ADMIN
# ─────────────────────────────────────────────────────────────
def page_admin():
    if not is_admin(): st.error("Access denied."); return
    render_topbar("admin")
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">🛠️ Admin Panel</div>',unsafe_allow_html=True)

    # Admin role badge
    cur_role = st.session_state.get("role","admin")
    role_colors = {"owner":GOLD,"admin":"#93b4fd"}
    st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <div style="font-size:22px;font-weight:800;color:#e2e8f0;">🛠️ Admin Panel</div>
        <div style="background:rgba(37,99,235,0.1);border:1px solid rgba(37,99,235,0.3);border-radius:8px;
                    padding:6px 14px;font-size:12px;font-weight:700;color:{role_colors.get(cur_role,'#93b4fd')};">
            {cur_role.title()} Access
        </div>
    </div>""", unsafe_allow_html=True)
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
        st.markdown('<div class="sec-hd" style="font-size:13px;margin-top:16px;">💳 Stripe Billing Configuration</div>',unsafe_allow_html=True)

        # Live status
        stripe_ok = stripe_configured()
        scolor = GREEN if stripe_ok else GOLD
        sstatus = "✅ Stripe Connected" if stripe_ok else "⚠️ Stripe Not Configured"
        st.markdown(f'<div style="background:{"#04200d" if stripe_ok else "#1a1000"};border:1px solid {"rgba(34,197,94,0.3)" if stripe_ok else "rgba(245,158,11,0.3)"};border-radius:8px;padding:10px 14px;font-size:13px;font-weight:700;color:{scolor};margin-bottom:16px;">{sstatus}</div>',unsafe_allow_html=True)

        st.markdown(f"""<div class="card">
            <div style="font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:10px;">Step-by-Step Stripe Setup</div>
            <div style="font-size:12px;color:#374f6e;line-height:2.0;">
            <strong style="color:#e2e8f0;">1. Create a Stripe account</strong> at <a href="https://stripe.com" target="_blank" style="color:#93b4fd;">stripe.com</a><br>
            <strong style="color:#e2e8f0;">2. Create Products & Prices</strong> in Stripe Dashboard → Products:<br>
            &nbsp;&nbsp;&nbsp;&nbsp;• StockWins Premium Monthly → Recurring $29/mo → copy Price ID<br>
            &nbsp;&nbsp;&nbsp;&nbsp;• StockWins Annual Plan → Recurring $199/yr → copy Price ID<br>
            <strong style="color:#e2e8f0;">3. Get your Secret Key</strong> from Stripe Dashboard → Developers → API Keys<br>
            <strong style="color:#e2e8f0;">4. Add to Streamlit Secrets</strong> (Settings → Secrets in your app dashboard):<br>
            </div>
            <pre style="background:#060a12;border:1px solid rgba(255,255,255,0.08);border-radius:8px;padding:14px;font-size:11px;color:#4ade80;margin:10px 0;overflow-x:auto;">STRIPE_SECRET_KEY = "sk_live_..."
STRIPE_PRICE_MONTHLY = "price_xxx"
STRIPE_PRICE_ANNUAL  = "price_yyy"
APP_URL = "https://your-app.streamlit.app"</pre>
            <div style="font-size:12px;color:#374f6e;line-height:2.0;">
            <strong style="color:#e2e8f0;">5. Customer Portal</strong> — Enable in Stripe Dashboard → Billing → Customer Portal<br>
            <strong style="color:#e2e8f0;">6. Test Mode</strong> — Use <code style="background:#0e1421;color:#93b4fd;padding:1px 5px;border-radius:3px;">sk_test_...</code> keys first, then switch to live<br>
            <strong style="color:#e2e8f0;">7. Test card</strong>: <code style="background:#0e1421;color:#93b4fd;padding:1px 5px;border-radius:3px;">4242 4242 4242 4242</code> · any future exp · any CVC<br>
            </div>
        </div>""",unsafe_allow_html=True)

        st.markdown(f"""<div class="card card-blue" style="margin-top:8px;">
            <div style="font-size:12px;font-weight:700;color:#93b4fd;margin-bottom:6px;">⚠️ Webhook Note for Streamlit</div>
            <div style="font-size:12px;color:#374f6e;line-height:1.8;">
            Streamlit Community Cloud can't receive webhooks directly. StockWins uses <strong style="color:#e2e8f0;">Checkout Session verification</strong> on the success redirect URL instead. This handles new subscriptions reliably.<br>
            For subscription renewals, cancellations, and failed payments in production, you have two options:<br>
            • <strong style="color:#e2e8f0;">Option A</strong>: Add a lightweight webhook endpoint (Flask/FastAPI on Render.com, free tier) that updates a shared DB<br>
            • <strong style="color:#e2e8f0;">Option B</strong>: Use Stripe's <code style="background:#0e1421;color:#93b4fd;">payment_behavior: allow_incomplete</code> + manual user verification via the Users tab<br>
            For MVP/early-stage, Option B is fine. Upgrade to Option A when you have 50+ paying subscribers.
            </div>
        </div>""",unsafe_allow_html=True)

        if stripe_ok and is_owner():
            st.markdown('<div class="sec-hd" style="font-size:12px;margin-top:16px;">Quick Actions</div>',unsafe_allow_html=True)
            qa1,qa2=st.columns(2,gap="small")
            with qa1:
                manual_email=st.text_input("User email to upgrade",placeholder="user@email.com",key="admin_upgrade_email",label_visibility="visible")
                manual_plan=st.selectbox("Plan",["premium","annual"],key="admin_upgrade_plan",label_visibility="visible")
                if st.button("↑ Manually Upgrade User",key="admin_do_upgrade",type="primary",use_container_width=True):
                    if manual_email and manual_email in st.session_state.users_db:
                        st.session_state.users_db[manual_email]["role"]="premium"
                        st.session_state.users_db[manual_email]["plan"]="Monthly" if manual_plan=="premium" else "Annual"
                        st.success(f"✅ {manual_email} upgraded to {manual_plan}")
                    elif manual_email: st.error("User not found")
            with qa2:
                downgrade_email=st.text_input("User email to downgrade",placeholder="user@email.com",key="admin_downgrade_email",label_visibility="visible")
                if st.button("↓ Downgrade to Free",key="admin_do_downgrade",use_container_width=True):
                    if downgrade_email and downgrade_email in st.session_state.users_db:
                        st.session_state.users_db[downgrade_email]["role"]="free"
                        st.session_state.users_db[downgrade_email]["plan"]="Free"
                        st.success(f"✅ {downgrade_email} downgraded")
                    elif downgrade_email: st.error("User not found")

    st.markdown('</div>',unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# EMAIL VERIFICATION
# ─────────────────────────────────────────────────────────────
def _send_verification_email(email, code):
    """
    Send verification email. Requires RESEND_API_KEY or SENDGRID_API_KEY in Secrets.
    Falls back to simulated mode (shows code in UI) if not configured.
    Returns (True, None) or (False, error_msg).
    """
    # Try Resend
    try:
        resend_key = st.secrets.get("RESEND_API_KEY","")
        if resend_key:
            import requests as _r
            resp = _r.post("https://api.resend.com/emails",
                headers={"Authorization":f"Bearer {resend_key}","Content-Type":"application/json"},
                json={"from":"StockWins <noreply@stockwins.com>",
                      "to":[email],
                      "subject":"Your StockWins verification code",
                      "html":f"""<div style="font-family:Inter,sans-serif;background:#07090f;color:#e2e8f0;padding:40px;">
                        <h2 style="color:#2563eb;">Stock<span style="color:#f59e0b;">W</span>ins</h2>
                        <h3>Verify your email</h3>
                        <p style="color:#6b7fa0;">Your verification code is:</p>
                        <div style="font-size:36px;font-weight:800;letter-spacing:8px;color:#2563eb;padding:20px;background:#0d1525;border-radius:12px;text-align:center;">{code}</div>
                        <p style="color:#6b7fa0;margin-top:20px;">This code expires in 10 minutes. If you didn't request this, ignore this email.</p>
                      </div>"""})
            if resp.status_code in (200,201): return True,None
            return False, f"Email send failed: {resp.text}"
    except: pass
    # Simulated — show code in UI
    return False, f"DEMO_CODE:{code}"

def page_verify_email():
    render_topbar()
    _,cc,_=st.columns([1,2,1])
    with cc:
        email = st.session_state.get("_verify_email","")
        st.markdown(f"""<div style="text-align:center;padding:40px 0 24px;">
            <div style="font-size:32px;margin-bottom:12px;">📧</div>
            <div style="font-size:24px;font-weight:800;color:#e2e8f0;margin-bottom:8px;">Check Your Email</div>
            <div style="font-size:13px;color:#374f6e;">We sent a 6-digit verification code to<br>
            <strong style="color:#93b4fd;">{email}</strong></div>
        </div>""",unsafe_allow_html=True)

        # Show demo code if email not configured
        demo = st.session_state.get("_demo_code","")
        if demo:
            st.markdown(f'''<div style="background:#0d1525;border:1px solid rgba(37,99,235,0.3);border-radius:10px;padding:16px;margin-bottom:12px;">
                <div style="font-size:12px;font-weight:700;color:#60a5fa;margin-bottom:6px;">📋 Demo Mode — Email Sending Not Configured</div>
                <div style="font-size:11px;color:#374f6e;margin-bottom:8px;">Add <code style="background:#060a12;color:#4ade80;padding:1px 5px;border-radius:3px;">RESEND_API_KEY</code> to Streamlit Secrets to enable real email verification.</div>
                <div style="font-size:14px;font-weight:700;color:#e2e8f0;">Your code: <span style="font-family:'JetBrains Mono',monospace;font-size:22px;color:#2563eb;letter-spacing:4px;">{demo}</span></div>
            </div>''', unsafe_allow_html=True)

        with st.form("vf"):
            code_in = st.text_input("Enter 6-digit code", placeholder="123456", max_chars=6)
            if st.form_submit_button("Verify Email →", type="primary", use_container_width=True):
                stored = st.session_state.get("_verify_code","")
                if code_in.strip() == stored:
                    uemail = st.session_state.get("_verify_email","")
                    if uemail in st.session_state.users_db:
                        st.session_state.users_db[uemail]["verified"] = True
                        _save_global_db(st.session_state.users_db)
                        save_user_to_file(uemail, st.session_state.users_db[uemail])
                    # Complete login
                    udata = st.session_state.get("_verify_user",{})
                    st.session_state.user = {"email":uemail,"name":udata.get("name","")}
                    st.session_state.role = "free"
                    for k in ["_verify_code","_verify_email","_verify_user","_demo_code"]:
                        st.session_state.pop(k,None)
                    st.session_state["_signup_success"] = udata.get("name","")
                    st.success("✅ Email verified! Welcome to StockWins.")
                    time.sleep(0.3)
                    nav("dashboard")
                else:
                    st.error("❌ Incorrect code. Please try again.")

        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("Resend code", key="resend_v"):
            code = str(random.randint(100000,999999))
            st.session_state["_verify_code"] = code
            ok,info = _send_verification_email(email, code)
            if not ok and info and info.startswith("DEMO_CODE:"):
                st.session_state["_demo_code"] = info.split(":",1)[1]
                st.success("Code regenerated (demo mode — shown above)")
            elif ok: st.success("✅ New code sent!")
            else: st.error(f"Send failed: {info}")
        if st.button("← Back to Sign Up", key="v_back"):
            for k in ["_verify_code","_verify_email","_verify_user","_demo_code"]:
                st.session_state.pop(k,None)
            nav("signup")

# ─────────────────────────────────────────────────────────────
# PAGE: CONTACT
# ─────────────────────────────────────────────────────────────
def page_contact():
    render_topbar()
    st.markdown('<div class="pg">',unsafe_allow_html=True)
    st.markdown(f"""<div style="text-align:center;padding:32px 0 24px;">
        <div style="font-size:11px;font-weight:700;color:{BLUE};letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">We're Here to Help</div>
        <div style="font-size:34px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;margin-bottom:8px;">Contact & Support</div>
        <div style="font-size:14px;color:#374f6e;">Reach us by email or chat with our AI support assistant below.</div>
    </div>""",unsafe_allow_html=True)

    top1,top2,top3 = st.columns(3,gap="small")
    with top1:
        st.markdown(f'''<div class="card card-blue" style="text-align:center;padding:24px;">
            <div style="font-size:28px;margin-bottom:10px;">📧</div>
            <div style="font-size:14px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">Email Support</div>
            <div style="font-size:12px;color:#374f6e;margin-bottom:12px;">For account, billing, and general questions</div>
            <a href="mailto:support@stockwins.com" style="font-size:13px;font-weight:700;color:#93b4fd;text-decoration:none;">support@stockwins.com</a>
            <div style="font-size:11px;color:#2a3a52;margin-top:6px;">Response within 24 hours</div>
        </div>''',unsafe_allow_html=True)
    with top2:
        st.markdown(f'''<div class="card" style="text-align:center;padding:24px;">
            <div style="font-size:28px;margin-bottom:10px;">💬</div>
            <div style="font-size:14px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">AI Support Chat</div>
            <div style="font-size:12px;color:#374f6e;margin-bottom:12px;">Instant answers to platform questions</div>
            <div style="font-size:13px;font-weight:700;color:#4ade80;">● Available Now</div>
            <div style="font-size:11px;color:#2a3a52;margin-top:6px;">Scroll down to chat</div>
        </div>''',unsafe_allow_html=True)
    with top3:
        st.markdown(f'''<div class="card card-gold" style="text-align:center;padding:24px;">
            <div style="font-size:28px;margin-bottom:10px;">👑</div>
            <div style="font-size:14px;font-weight:700;color:#e2e8f0;margin-bottom:6px;">Priority Support</div>
            <div style="font-size:12px;color:#374f6e;margin-bottom:12px;">For Annual plan subscribers</div>
            <div style="font-size:13px;font-weight:700;color:{GOLD};">4-hour response time</div>
            <div style="font-size:11px;color:#2a3a52;margin-top:6px;">Annual plan feature</div>
        </div>''',unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">💬 AI Support Assistant</div>',unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px;color:#374f6e;margin-bottom:14px;">Ask anything about StockWins — features, categories, signals, billing, or how to use the platform.</div>',unsafe_allow_html=True)

    # Chat history
    if "support_chat" not in st.session_state:
        st.session_state.support_chat = [
            {"role":"assistant","content":"Hi! I'm the StockWins support assistant. I can help with questions about the platform, our composite signal categories, billing, features, or anything else. What can I help you with today?"}
        ]

    # Display chat
    for msg in st.session_state.support_chat:
        if msg["role"]=="assistant":
            st.markdown(f'''<div style="display:flex;gap:10px;margin-bottom:12px;align-items:flex-start;">
                <div style="background:{BLUE};border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;">SW</div>
                <div style="background:{CARD};border:1px solid {BORDER};border-radius:0 10px 10px 10px;padding:10px 14px;font-size:13px;color:#d1d9e6;max-width:80%;line-height:1.6;">{msg["content"]}</div>
            </div>''',unsafe_allow_html=True)
        else:
            st.markdown(f'''<div style="display:flex;gap:10px;margin-bottom:12px;align-items:flex-start;flex-direction:row-reverse;">
                <div style="background:#2a3a52;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:11px;flex-shrink:0;">You</div>
                <div style="background:#0a1628;border:1px solid rgba(37,99,235,0.2);border-radius:10px 0 10px 10px;padding:10px 14px;font-size:13px;color:#d1d9e6;max-width:80%;line-height:1.6;">{msg["content"]}</div>
            </div>''',unsafe_allow_html=True)

    # Input
    with st.form("support_form", clear_on_submit=True):
        uc1,uc2=st.columns([5,1],gap="small")
        with uc1: user_q=st.text_input("",placeholder="Ask a question...",label_visibility="collapsed")
        with uc2: send=st.form_submit_button("Send →",type="primary",use_container_width=True)
        if send and user_q.strip():
            st.session_state.support_chat.append({"role":"user","content":user_q.strip()})
            # Call Anthropic API for support response
            with st.spinner(""):
                try:
                    import requests as _r
                    sys_prompt = """You are the StockWins customer support assistant. StockWins is a premium stock intelligence platform.

Key facts:
- StockWins has 17 proprietary composite signal categories combining RSI, MACD, volume, social sentiment, short interest
- Free plan: 7 composite categories, market overview, watchlist (10 stocks), BUY/AVOID signals
- Premium ($29/mo): All 17 categories, squeeze scanner, advanced screener, BI analytics, score breakdowns, unlimited watchlist
- Annual ($199/yr): Everything in Premium + priority support, early access, export, API access
- Data sources: Yahoo Finance (free), Twelve Data (optional), StockTwits (social sentiment)
- Signals are educational/algorithmic only — NOT financial advice
- Back button works to go to previous page
- For billing: support@stockwins.com

Be helpful, concise, and friendly. If asked about a specific stock or investment advice, remind them signals are educational only."""
                    msgs = [{"role":m["role"],"content":m["content"]} for m in st.session_state.support_chat]
                    # Get Anthropic API key from secrets
                    try: anth_key = st.secrets.get("ANTHROPIC_API_KEY","")
                    except: anth_key = ""
                    if not anth_key:
                        answer = "Support chat requires ANTHROPIC_API_KEY in Streamlit Secrets. In the meantime, email support@stockwins.com — we respond within 24 hours!"
                    else:
                        resp = _r.post("https://api.anthropic.com/v1/messages",
                            headers={"Content-Type":"application/json",
                                     "x-api-key":anth_key,
                                     "anthropic-version":"2023-06-01"},
                            json={"model":"claude-haiku-4-5-20251001","max_tokens":400,
                                  "system":sys_prompt,"messages":msgs},
                            timeout=20)
                        if resp.status_code==200:
                            answer = resp.json()["content"][0]["text"]
                        else:
                            answer = f"I'm having trouble right now (status {resp.status_code}). Please email support@stockwins.com for immediate help."
                except Exception as e:
                    answer = f"Connection issue. Please email support@stockwins.com — we typically respond within 24 hours."
            st.session_state.support_chat.append({"role":"assistant","content":answer})
            st.rerun()

    st.markdown("<br>",unsafe_allow_html=True)
    if st.button("🗑 Clear Chat",key="clear_support"):
        st.session_state.support_chat=[{"role":"assistant","content":"Chat cleared. How can I help you?"}]
        st.rerun()

    # FAQ quick links
    st.markdown("<br>",unsafe_allow_html=True)
    st.markdown('<div class="sec-hd">Common Questions</div>',unsafe_allow_html=True)
    faqs=[
        ("How do I upgrade to Premium?","Go to Pricing in the top nav, select Premium Monthly or Annual, and click the subscribe button. Payment is processed securely via Stripe."),
        ("What are the composite signal categories?","StockWins has 17 proprietary categories combining multiple signals simultaneously — like RSI + short float + social sentiment — to surface setups not visible through standard TA."),
        ("Is this financial advice?","No. StockWins provides algorithmic, educational signals only. Nothing constitutes financial advice. Always consult a licensed financial advisor."),
        ("How do I cancel my subscription?","Go to Settings → Subscription → Open Billing Portal. You can cancel anytime with no questions asked."),
        ("Can I get a refund?","Yes — contact support@stockwins.com within 30 days of your subscription start date."),
    ]
    for q,a in faqs:
        with st.expander(q):
            st.markdown(f'<div style="font-size:13px;color:#374f6e;line-height:1.75;">{a}</div>',unsafe_allow_html=True)

    st.markdown('</div>',unsafe_allow_html=True)
    render_footer()

# ─────────────────────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────────────────────
render_sidebar()

# ── 1. Handle Stripe payment returns (URL params) ──
handle_payment_return()

# ── 2. Execute Stripe redirect if checkout session was just created ──
if st.session_state.get("_redirect_url"):
    url = st.session_state.get("_redirect_url")
    sel_plan = st.session_state.get("sel_plan","premium")
    plan_display = {"premium":"Premium Monthly — $29/mo","annual":"Annual Plan — $199/yr","free":"Free"}.get(sel_plan,"Premium Monthly")
    render_topbar("pricing")
    st.markdown(f'<div style="font-size:12px;color:#374f6e;padding:0 0 16px;"><span style="color:#4a5e7a;">Pricing</span> <span style="color:#2a3a52;"> › </span> <span style="color:#e2e8f0;font-weight:600;">Secure Checkout</span></div>',unsafe_allow_html=True)
    lc,rc = st.columns([3,2],gap="large")
    with lc:
        st.markdown(f"""
        <div style="background:#0d1525;border:1px solid rgba(37,99,235,0.3);border-radius:14px;padding:24px;margin-bottom:14px;">
            <div style="font-size:10px;font-weight:700;color:{BLUE};letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;">Your Selected Plan</div>
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div style="font-size:18px;font-weight:800;color:#e2e8f0;">{plan_display}</div>
                <div style="font-size:11px;color:#4ade80;font-weight:700;">● Cancel anytime</div>
            </div>
        </div>
        <div style="background:#080b14;border:1px solid {BORDER};border-radius:10px;padding:16px 18px;margin-bottom:16px;">
            <div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:8px;">What you get immediately:</div>
            <div style="font-size:13px;color:#374f6e;line-height:2.2;">✅&nbsp; All 17 composite signal categories<br>✅&nbsp; Short squeeze scanner + advanced screener<br>✅&nbsp; Full BI analytics &amp; opportunity matrix<br>✅&nbsp; Score breakdowns &amp; plain-English insights<br>✅&nbsp; Unlimited watchlist &amp; price alerts</div>
        </div>
        <style>
        .sw-ck-btn{{display:block;width:100%;text-align:center;padding:17px;
            background:linear-gradient(135deg,#1d4ed8,#2563eb);
            color:#fff!important;font-size:15px;font-weight:700;
            border-radius:10px;text-decoration:none;
            box-shadow:0 6px 24px rgba(37,99,235,0.5);
            transition:all 0.2s ease;letter-spacing:0.3px;}}
        .sw-ck-btn:hover{{background:linear-gradient(135deg,#1e40af,#1d4ed8);box-shadow:0 10px 40px rgba(37,99,235,0.7);}}
        </style>
        <a class="sw-ck-btn" href="{url}" target="_top">🔒&nbsp; Complete Secure Checkout on Stripe →</a>
        <div style="text-align:center;margin-top:10px;font-size:11px;color:#2a3a52;">Powered by <strong style="color:#6775ba;">Stripe</strong> · 256-bit SSL · PCI compliant · Card details never touch our servers</div>
        """, unsafe_allow_html=True)
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("← Change Plan",key="cancel_ck",use_container_width=True):
            st.session_state.pop("_redirect_url",None); nav("pricing")
    with rc:
        st.markdown(f"""
        <div style="background:#080b14;border:1px solid {BORDER};border-radius:14px;padding:22px;">
            <div style="font-size:13px;font-weight:700;color:#e2e8f0;margin-bottom:12px;">🔒 Payment Security</div>
            <div style="font-size:12px;color:#374f6e;line-height:2.2;">
            🛡️&nbsp; 256-bit SSL encryption<br>💳&nbsp; Zero card data on our servers<br>🔄&nbsp; Cancel anytime, no questions<br>📧&nbsp; Instant access after payment<br>💰&nbsp; 30-day refund policy<br>🏦&nbsp; Powered by Stripe
            </div>
        </div>
        <div style="background:#0d1525;border:1px solid rgba(34,197,94,0.2);border-radius:10px;padding:18px;margin-top:12px;">
            <div style="font-size:12px;font-weight:700;color:{GREEN};margin-bottom:8px;">After Payment ✓</div>
            <div style="font-size:12px;color:#374f6e;line-height:2.2;">1. Account upgrades instantly<br>2. All premium categories unlock<br>3. Set up watchlist &amp; alerts<br>4. Explore BI Analytics<br>5. Configure email digests</div>
        </div>
        <div style="margin-top:12px;text-align:center;font-size:12px;color:#2a3a52;">Questions? <a href="mailto:support@stockwins.com" style="color:#93b4fd;">support@stockwins.com</a></div>
        """, unsafe_allow_html=True)
    st.stop()

# ── 3. Payment notifications ──
if st.session_state.get("_pay_success"):
    plan = st.session_state.pop("_pay_success")
    plan_name = "Annual Plan" if plan=="annual" else "Premium"
    # Rich success banner
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#04200d,#0d1525);
                border:1px solid rgba(34,197,94,0.4);border-radius:14px;
                padding:28px 32px;margin-bottom:20px;text-align:center;">
        <div style="font-size:48px;margin-bottom:12px;">🎉</div>
        <div style="font-size:24px;font-weight:800;color:#4ade80;margin-bottom:8px;">
            Welcome to StockWins {plan_name}!
        </div>
        <div style="font-size:14px;color:#374f6e;margin-bottom:20px;line-height:1.7;">
            Your account has been upgraded. You now have access to all {plan_name} features.<br>
            Start exploring all 17 composite categories, the short squeeze scanner, and full BI analytics.
        </div>
        <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;">
            <span style="background:rgba(34,197,94,0.1);color:#4ade80;font-size:12px;font-weight:700;
                         padding:6px 16px;border-radius:20px;border:1px solid rgba(34,197,94,0.3);">
                ✅ All 17 categories unlocked
            </span>
            <span style="background:rgba(34,197,94,0.1);color:#4ade80;font-size:12px;font-weight:700;
                         padding:6px 16px;border-radius:20px;border:1px solid rgba(34,197,94,0.3);">
                ✅ Squeeze Scanner active
            </span>
            <span style="background:rgba(34,197,94,0.1);color:#4ade80;font-size:12px;font-weight:700;
                         padding:6px 16px;border-radius:20px;border:1px solid rgba(34,197,94,0.3);">
                ✅ BI Analytics enabled
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    # Quick action buttons
    _qa1, _qa2, _qa3 = st.columns(3, gap="small")
    with _qa1:
        if st.button("🎯 Explore Premium Categories", key="ps_disc", type="primary", use_container_width=True):
            nav("discover")
    with _qa2:
        if st.button("📊 Open BI Analytics", key="ps_bi", use_container_width=True):
            nav("bi_dashboard")
    with _qa3:
        if st.button("🔔 Set Up Alerts", key="ps_alerts", use_container_width=True):
            nav("settings")

if st.session_state.get("_pay_error"):
    err = st.session_state.pop("_pay_error")
    st.markdown(f"""
    <div style="background:#200404;border:1px solid rgba(239,68,68,0.3);border-radius:10px;
                padding:16px 20px;margin-bottom:16px;">
        <div style="font-size:14px;font-weight:700;color:#f87171;margin-bottom:6px;">
            ❌ Payment Error
        </div>
        <div style="font-size:13px;color:#374f6e;margin-bottom:8px;">{err}</div>
        <div style="font-size:12px;color:#2a3a52;">
            Need help? Email <a href="mailto:support@stockwins.com" style="color:#93b4fd;">support@stockwins.com</a>
            and we'll sort it out within 24 hours.
        </div>
    </div>
    """, unsafe_allow_html=True)

if st.session_state.get("_pay_cancelled"):
    st.session_state.pop("_pay_cancelled")
    st.markdown("""
    <div style="background:#0d1525;border:1px solid rgba(245,158,11,0.3);border-radius:10px;
                padding:16px 20px;margin-bottom:16px;">
        <div style="font-size:14px;font-weight:700;color:#f59e0b;margin-bottom:4px;">
            ⚠️ Checkout Cancelled
        </div>
        <div style="font-size:13px;color:#374f6e;">
            No charge was made. Your account remains on the free plan.
            Ready to upgrade? Choose a plan below — it only takes 2 minutes.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── 3b. Welcome notifications ──
if st.session_state.get("_logged_out"):
    st.session_state.pop("_logged_out")
    st.toast("👋 You've been logged out. See you next time!", icon="✅")
if st.session_state.get("_signup_success"):
    name = st.session_state.pop("_signup_success")
    st.toast(f"🎉 Account created! Welcome to StockWins, {name}!", icon="🚀")
if st.session_state.get("_login_welcome"):
    name = st.session_state.pop("_login_welcome")
    st.toast(f"👋 Welcome back, {name}!", icon="✅")

# ── 4. Complete pending checkout after login ──
if is_authed() and st.session_state.get("_pending_checkout"):
    plan = st.session_state.pop("_pending_checkout")
    url, err = create_checkout_session(plan, st.session_state.user["email"])
    if url: st.session_state["_redirect_url"] = url; st.rerun()
    else:   st.error(f"Checkout error: {err}")

page=st.session_state.get("page","landing")
guard={"dashboard","discover","watchlist","screener","bi_dashboard","stock_detail","settings","admin"}

if page in guard and not is_authed():
    page_login()
elif page=="landing":      page_landing()
elif page=="features":     page_features()
elif page=="login":        page_login()
elif page=="signup":       page_signup()
elif page=="verify_email": page_verify_email()
elif page=="forgot_pw":    page_forgot()
elif page=="pricing":      page_pricing()
elif page=="contact":      page_contact()
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
