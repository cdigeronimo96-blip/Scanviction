# ═══════════════════════════════════════════════════════════════
# MARKETSIGNALPRO v7.0 — Premium Fintech SaaS
# "I trust this. I understand this. I want more."
# ═══════════════════════════════════════════════════════════════

import streamlit as st
import requests, pandas as pd, ta, yfinance as yf
import hashlib, time, random, math, sys, os
from datetime import datetime, timedelta

# Signal Performance Engine
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from signal_engine import (
        record_signal_event, update_signal_outcomes, get_ticker_signal_history,
        get_recent_signal_events, get_category_performance_stats,
        calculate_pnl, estimate_options_pnl, compute_confidence,
        detect_market_regime, seed_demo_signal_history
    )
    HAS_SIGNAL_ENGINE = True
except Exception as _se:
    HAS_SIGNAL_ENGINE = False
    def record_signal_event(*a, **kw): return {}
    def get_ticker_signal_history(t, **kw): return []
    def get_recent_signal_events(**kw): return []
    def get_category_performance_stats(): return {}
    def calculate_pnl(inv, tp, cp, direction="long"):
        if tp <= 0: return {}
        pct = ((cp - tp) / tp) * 100 * (1 if direction=="long" else -1)
        pnl = inv * (pct/100)
        return {"pnl_usd": round(pnl,2), "pnl_pct": round(pct,2), "current_value": round(inv+pnl,2),
                "shares": round(inv/tp,4), "price_change": round(cp-tp,2), "pct_change": round((cp-tp)/tp*100,2)}
    def estimate_options_pnl(*a, **kw): return {}
    def compute_confidence(*a, **kw): return {"confidence":"N/A","risk":"Unknown","factors":[],"score":50}
    def detect_market_regime(*a, **kw): return {"regime":"mixed","label":"⚖️ Mixed","description":"","best_strategies":[]}
    def seed_demo_signal_history(): pass

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
    page_title="MarketSignalPro | AI-Powered Stock Signals",
    page_icon="📈", layout="wide",
    initial_sidebar_state="auto",
)

# ─────────────────────────────────────────────────────────────
# PROGRESSIVE WEB APP (PWA) — Native app experience
# ─────────────────────────────────────────────────────────────
# Embedded SVG icon (no external hosting needed) — MarketSignalPro logo as SVG → base64
_SW_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#1d4ed8"/><stop offset="1" stop-color="#2563eb"/>
</linearGradient></defs>
<rect width="512" height="512" rx="96" fill="url(#g)"/>
<path d="M120 340 L120 380 L392 380 L392 340 L120 340 Z" fill="#fff" opacity=".3"/>
<path d="M140 320 L200 240 L240 280 L320 160 L380 220 L380 240 L320 200 L240 320 L200 280 L160 340 Z" fill="#fff"/>
<circle cx="380" cy="220" r="14" fill="#f59e0b"/>
<text x="256" y="450" text-anchor="middle" fill="#fff" font-family="Inter,sans-serif" font-size="56" font-weight="900">MSP</text>
</svg>'''

import base64 as _b64
_icon_b64 = _b64.b64encode(_SW_ICON_SVG.encode()).decode()
_icon_data_uri = f"data:image/svg+xml;base64,{_icon_b64}"

PWA_MANIFEST_JSON = (
    '{"name":"MarketSignalPro — AI-Powered Stock Signals",'
    '"short_name":"MarketSignalPro",'
    '"description":"AI-powered stock signals, smart watchlists, alerts, and plain-English market insights.",'
    '"start_url":"/",'
    '"display":"standalone",'
    '"orientation":"portrait",'
    '"background_color":"#07090f",'
    '"theme_color":"#2563eb",'
    '"categories":["finance","business","productivity"],'
    '"icons":[{"src":"' + _icon_data_uri + '","sizes":"512x512","type":"image/svg+xml","purpose":"any maskable"}]'
    '}'
)
_manifest_data_uri = "data:application/json;base64," + _b64.b64encode(PWA_MANIFEST_JSON.encode()).decode()

# ── Inject PWA head tags + native-feeling polish ──
st.markdown(f"""
<link rel="manifest" href="{_manifest_data_uri}">
<link rel="icon" type="image/svg+xml" href="{_icon_data_uri}">
<link rel="apple-touch-icon" href="{_icon_data_uri}">
<meta name="theme-color" content="#2563eb">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="MarketSignalPro">
<meta name="msapplication-TileColor" content="#2563eb">
<meta name="msapplication-navbutton-color" content="#2563eb">
<meta name="format-detection" content="telephone=no">

<style>
/* ════════════════════════════════════════════════════════════
   NATIVE-APP POLISH — animations, safe areas, momentum scroll
════════════════════════════════════════════════════════════ */

/* Respect iOS notch / Android nav bar */
html, body {{
    padding-top: env(safe-area-inset-top, 0px) !important;
    padding-left: env(safe-area-inset-left, 0px);
    padding-right: env(safe-area-inset-right, 0px);
}}

/* Smooth iOS-style momentum scrolling everywhere */
* {{
    -webkit-overflow-scrolling: touch;
}}

/* Hide tap-highlight + selection styling for app feel */
* {{
    -webkit-tap-highlight-color: transparent;
    -webkit-touch-callout: none;
}}
input, textarea, [contenteditable], .sw-allow-select {{
    -webkit-user-select: text;
    user-select: text;
    -webkit-touch-callout: default;
}}

/* Disable pull-to-refresh on standalone PWAs (annoying on charts) */
@media (display-mode: standalone) {{
    body {{ overscroll-behavior-y: contain; }}
}}

/* Native-style button press animation */
button, [role="button"], .stButton button {{
    transition: transform 0.08s ease-out, opacity 0.15s ease-out !important;
}}
button:active, [role="button"]:active, .stButton button:active {{
    transform: scale(0.97) !important;
    opacity: 0.85 !important;
}}

/* Smooth page enter animation */
.main .block-container {{
    animation: pageFadeIn 0.28s cubic-bezier(0.16, 1, 0.3, 1);
}}
@keyframes pageFadeIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

/* Card hover/press = native feel */
.card, .sr, .stat {{
    transition: transform 0.15s cubic-bezier(0.16, 1, 0.3, 1),
                box-shadow 0.15s ease-out,
                border-color 0.15s ease-out !important;
}}
.card:active, .sr:active {{
    transform: scale(0.99) !important;
}}

/* Smooth modal/dialog entry */
[data-testid="stModal"], [data-testid="stDialog"] {{
    animation: modalSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}}
@keyframes modalSlideUp {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}

/* Custom install banner */
#sw-install-banner {{
    position: fixed;
    bottom: 18px;
    left: 50%;
    transform: translateX(-50%) translateY(120%);
    background: linear-gradient(135deg, #1d4ed8, #2563eb);
    color: #fff;
    padding: 14px 18px;
    border-radius: 14px;
    box-shadow: 0 12px 40px rgba(37,99,235,0.45);
    font-family: 'Inter', sans-serif;
    z-index: 999999;
    display: flex;
    align-items: center;
    gap: 12px;
    max-width: 92vw;
    width: 360px;
    transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    border: 1px solid rgba(255,255,255,0.15);
}}
#sw-install-banner.visible {{
    transform: translateX(-50%) translateY(0);
}}
#sw-install-banner-icon {{
    width: 40px; height: 40px;
    background: rgba(255,255,255,0.2);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    flex-shrink: 0;
}}
#sw-install-banner-text {{
    flex: 1;
    line-height: 1.4;
}}
#sw-install-banner-text strong {{
    display: block;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 2px;
}}
#sw-install-banner-text span {{
    font-size: 11px;
    opacity: 0.85;
}}
#sw-install-banner button {{
    background: #fff;
    color: #1d4ed8;
    border: none;
    padding: 7px 14px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 12px;
    cursor: pointer;
    flex-shrink: 0;
}}
#sw-install-banner-close {{
    background: transparent !important;
    color: rgba(255,255,255,0.7) !important;
    font-size: 18px !important;
    padding: 0 6px !important;
    margin-left: -8px;
}}

/* Offline banner */
#sw-offline-banner {{
    position: fixed;
    top: 0; left: 0; right: 0;
    background: linear-gradient(135deg, #b45309, #f59e0b);
    color: #fff;
    padding: 8px 16px;
    text-align: center;
    font-size: 12px;
    font-weight: 700;
    font-family: 'Inter', sans-serif;
    z-index: 999998;
    transform: translateY(-100%);
    transition: transform 0.3s ease-out;
}}
#sw-offline-banner.visible {{
    transform: translateY(0);
}}

/* iOS standalone: hide install banner, add safe area top */
@media (display-mode: standalone) {{
    #sw-install-banner {{ display: none !important; }}
}}

/* PWA splash-style loading on first paint */
#sw-pwa-splash {{
    position: fixed;
    inset: 0;
    background: linear-gradient(180deg, #07090f 0%, #0d1525 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 1000000;
    opacity: 1;
    transition: opacity 0.5s ease-out;
    pointer-events: none;
}}
#sw-pwa-splash.hidden {{ opacity: 0; }}
#sw-pwa-splash-logo {{
    width: 84px; height: 84px;
    background: linear-gradient(135deg, #1d4ed8, #2563eb);
    border-radius: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Courier New', monospace;
    font-size: 32px;
    font-weight: 900;
    color: #fff;
    box-shadow: 0 10px 40px rgba(37,99,235,0.4);
    animation: splashPulse 1.4s ease-in-out infinite;
}}
@keyframes splashPulse {{
    0%, 100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.05); }}
}}
#sw-pwa-splash-title {{
    color: #e2e8f0;
    font-family: 'Inter', sans-serif;
    font-size: 16px;
    font-weight: 700;
    margin-top: 18px;
    letter-spacing: 0.5px;
}}
#sw-pwa-splash-tagline {{
    color: #4a5e7a;
    font-size: 11px;
    margin-top: 4px;
    font-family: 'Inter', sans-serif;
}}

/* Only show splash when app launched in standalone mode (installed) */
@media not (display-mode: standalone) {{
    #sw-pwa-splash {{ display: none; }}
}}
</style>

<!-- Splash screen (visible only when launched as installed app) -->
<div id="sw-pwa-splash">
    <div id="sw-pwa-splash-logo">MSP</div>
    <div id="sw-pwa-splash-title">MarketSignalPro</div>
    <div id="sw-pwa-splash-tagline">Loading market intelligence…</div>
</div>

<!-- Offline indicator -->
<div id="sw-offline-banner">⚠️ You're offline — some features may not work</div>

<!-- Custom install banner (Android/Chrome) -->
<div id="sw-install-banner">
    <div id="sw-install-banner-icon">📲</div>
    <div id="sw-install-banner-text">
        <strong>Install MarketSignalPro</strong>
        <span>Add to your home screen for instant access</span>
    </div>
    <button id="sw-install-banner-btn">Install</button>
    <button id="sw-install-banner-close" aria-label="Dismiss">×</button>
</div>

<script>
(function() {{
    // ── Hide splash after page loads ──
    setTimeout(() => {{
        const splash = document.getElementById('sw-pwa-splash');
        if (splash) {{
            splash.classList.add('hidden');
            setTimeout(() => splash.remove(), 600);
        }}
    }}, 800);

    // ── Online/Offline detection ──
    const offlineBanner = document.getElementById('sw-offline-banner');
    function updateOnlineStatus() {{
        if (!navigator.onLine) {{
            offlineBanner.classList.add('visible');
        }} else {{
            offlineBanner.classList.remove('visible');
        }}
    }}
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus();

    // ── Install Prompt Handling (Android/Chrome desktop) ──
    let deferredPrompt = null;
    const installBanner = document.getElementById('sw-install-banner');
    const installBtn = document.getElementById('sw-install-banner-btn');
    const installClose = document.getElementById('sw-install-banner-close');

    // Don't show again for 14 days if dismissed
    const dismissedAt = localStorage.getItem('sw_install_dismissed');
    const SHOULD_SUPPRESS = dismissedAt && (Date.now() - parseInt(dismissedAt) < 14 * 24 * 60 * 60 * 1000);

    window.addEventListener('beforeinstallprompt', (e) => {{
        e.preventDefault();
        deferredPrompt = e;
        if (!SHOULD_SUPPRESS) {{
            // Wait a few seconds before showing (don't jump-scare on load)
            setTimeout(() => {{
                installBanner.classList.add('visible');
            }}, 4500);
        }}
    }});

    installBtn.addEventListener('click', async () => {{
        if (!deferredPrompt) return;
        installBanner.classList.remove('visible');
        deferredPrompt.prompt();
        const {{ outcome }} = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {{
            console.log('MarketSignalPro installed!');
        }} else {{
            localStorage.setItem('sw_install_dismissed', Date.now().toString());
        }}
        deferredPrompt = null;
    }});

    installClose.addEventListener('click', () => {{
        installBanner.classList.remove('visible');
        localStorage.setItem('sw_install_dismissed', Date.now().toString());
    }});

    // Hide install banner if app gets installed
    window.addEventListener('appinstalled', () => {{
        installBanner.classList.remove('visible');
        localStorage.removeItem('sw_install_dismissed');
    }});

    // ── iOS Safari install hint (no beforeinstallprompt support) ──
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isInStandaloneMode = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
    if (isIOS && !isInStandaloneMode && !SHOULD_SUPPRESS) {{
        setTimeout(() => {{
            const banner = document.getElementById('sw-install-banner');
            const text = document.getElementById('sw-install-banner-text');
            text.innerHTML = '<strong>Install MarketSignalPro</strong><span>Tap Share → Add to Home Screen</span>';
            installBtn.textContent = 'Got it';
            installBtn.addEventListener('click', () => {{
                banner.classList.remove('visible');
                localStorage.setItem('sw_install_dismissed', Date.now().toString());
            }});
            banner.classList.add('visible');
        }}, 5000);
    }}

    // ── Service Worker registration for offline support ──
    // Uses a tiny inline SW served as data: URI (since Streamlit has no static root)
    if ('serviceWorker' in navigator) {{
        const swCode = `
            const CACHE_NAME = 'marketsignalpro-v1';
            self.addEventListener('install', e => self.skipWaiting());
            self.addEventListener('activate', e => e.waitUntil(clients.claim()));
            self.addEventListener('fetch', e => {{
                // Network-first strategy (Streamlit content is dynamic)
                if (e.request.method !== 'GET') return;
                e.respondWith(
                    fetch(e.request).catch(() => caches.match(e.request))
                );
            }});
        `;
        const blob = new Blob([swCode], {{ type: 'application/javascript' }});
        const swUrl = URL.createObjectURL(blob);
        navigator.serviceWorker.register(swUrl).catch(() => {{}});
    }}

    // ── SIDEBAR COLLAPSE BUTTON WATCHDOG ──
    // Streamlit aggressively hides the collapse control via inline styles after state changes.
    // We mutation-observe and force it visible. This runs continuously.
    function ensureSidebarToggleVisible() {{
        const selectors = [
            '[data-testid="collapsedControl"]',
            '[data-testid="stSidebarCollapseButton"]',
            '[data-testid="stSidebarCollapsedControl"]'
        ];
        selectors.forEach(sel => {{
            document.querySelectorAll(sel).forEach(el => {{
                // Strip inline display:none / visibility:hidden that Streamlit injects
                if (el.style.display === 'none')        el.style.display = '';
                if (el.style.visibility === 'hidden')   el.style.visibility = '';
                if (el.style.opacity === '0')           el.style.opacity = '';
                el.removeAttribute('hidden');
            }});
        }});
    }}
    // Run immediately, then every 400ms (cheap, catches Streamlit reruns)
    setInterval(ensureSidebarToggleVisible, 400);
    ensureSidebarToggleVisible();

    // Also observe DOM mutations to catch fresh insertions instantly
    const sidebarObserver = new MutationObserver(ensureSidebarToggleVisible);
    sidebarObserver.observe(document.body, {{ childList: true, subtree: true, attributes: true, attributeFilter: ['style','class','aria-expanded'] }});

    // ── MOBILE: Close sidebar when user taps outside it ──
    document.addEventListener('click', (e) => {{
        if (window.innerWidth > 992) return; // only mobile
        const sidebar = document.querySelector('[data-testid="stSidebar"]');
        if (!sidebar || sidebar.getAttribute('aria-expanded') !== 'true') return;
        const isInside = sidebar.contains(e.target);
        const isToggle = e.target.closest('[data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"]');
        if (!isInside && !isToggle) {{
            const btn = document.querySelector('[data-testid="stSidebarCollapseButton"]');
            if (btn) btn.click();
        }}
    }}, true);
}})();
</script>
""", unsafe_allow_html=True)

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
                "demo@marketsignalpro.com":    {"pw":_hp("demo123"), "name":"Demo User",  "role":"free",   "verified":True,"joined":today,"plan":"Free"},
                "premium@marketsignalpro.com": {"pw":_hp("premium1"),"name":"Alex Rivera","role":"premium","verified":True,"joined":today,"plan":"Monthly"},
            }
            if ae and ah: r[ae]={"pw":ah,"name":"Admin","role":"admin","verified":True,"joined":today,"plan":"Annual"}
            return r
    except: pass
    return {
        "demo@marketsignalpro.com":    {"pw":_hp("demo123"), "name":"Demo User",  "role":"free",   "verified":True,"joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Free"},
        "premium@marketsignalpro.com": {"pw":_hp("premium1"),"name":"Alex Rivera","role":"premium","verified":True,"joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Monthly"},
        "admin@marketsignalpro.com":   {"pw":_hp("admin_change_me"),"name":"Admin","role":"admin","verified":True,"joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Annual"},
        "owner@marketsignalpro.com":   {"pw":_hp("owner_change_me"),"name":"Owner","role":"owner","verified":True,"joined":datetime.now().strftime("%Y-%m-%d"),"plan":"Annual"},
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
    try: return st.secrets.get("APP_URL","https://marketsignalpro.streamlit.app")
    except: return "https://marketsignalpro.streamlit.app"

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
    """Check URL params for Stripe redirect or push subscription. Returns True if handled."""
    try: params = st.query_params.to_dict()
    except: return False

    # ── Topbar HTML-link navigation ──
    if params.get("topbar_nav"):
        target = params.get("topbar_nav","").strip()
        st.query_params.clear()
        if target == "__logout__":
            logout()
            return True
        valid_pages = {"landing","features","login","signup","verify_email","forgot_pw","pricing",
                       "contact","dashboard","discover","watchlist","screener","bi_dashboard",
                       "stock_detail","settings","admin","signal_track"}
        if target in valid_pages:
            nav(target)
            return True
        return True

    # ── Push subscription registration (from OneSignal JS callback) ──
    if params.get("push_sub_id") and is_authed():
        sub_id = params.get("push_sub_id","").strip()
        if sub_id:
            try:
                e = st.session_state.user["email"]
                existing = st.session_state.users_db.get(e,{}).get("push_subscription_ids",[])
                if sub_id not in existing:
                    existing.append(sub_id)
                    # Keep last 5 devices
                    existing = existing[-5:]
                st.session_state.users_db[e]["push_subscription_ids"] = existing
                st.session_state.users_db[e]["push_subscribed"] = True
                _save_global_db(st.session_state.users_db)
                save_user_to_file(e, st.session_state.users_db[e])
                st.session_state["_push_registered"] = True
            except Exception:
                pass
        st.query_params.clear()
        return True

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

/* ── Sidebar (Desktop default) ── */
[data-testid="stSidebar"]{{
    background:#080c18 !important;
    border-right:1px solid {BORDER} !important;
    width:225px !important;min-width:225px !important;max-width:225px !important;
    position:sticky !important;top:0 !important;
    height:100vh !important;
    transition: margin-left 0.3s ease !important;
}}
[data-testid="stSidebar"]>div{{
    padding:0 !important;
    height:100vh !important;
    overflow-y:auto !important;
}}

/* ── Collapse/Expand Button — ALWAYS VISIBLE ── */
/* The little arrow that toggles the sidebar (Streamlit hides this after collapse — we force it back) */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[kind="header"][data-testid="baseButton-header"],
[data-testid="stSidebarCollapsedControl"]{{
    visibility: visible !important;
    opacity: 1 !important;
    display: flex !important;
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 999999 !important;
    background: rgba(13, 21, 37, 0.95) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(96, 165, 250, 0.4) !important;
    border-radius: 8px !important;
    color: #93b4fd !important;
    width: 36px !important;
    height: 36px !important;
    padding: 6px !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.4) !important;
    cursor: pointer !important;
    align-items: center !important;
    justify-content: center !important;
}}
[data-testid="collapsedControl"]:hover,
[data-testid="stSidebarCollapseButton"]:hover{{
    background: rgba(37, 99, 235, 0.25) !important;
    border-color: rgba(96, 165, 250, 0.8) !important;
    transform: scale(1.05) !important;
}}
[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapseButton"] svg{{
    width: 18px !important;
    height: 18px !important;
    color: #93b4fd !important;
    fill: #93b4fd !important;
}}

/* When sidebar is OPEN, move the collapse button to top of sidebar (inside it) */
[data-testid="stSidebar"][aria-expanded="true"] ~ * [data-testid="collapsedControl"],
[data-testid="stSidebar"]:not([aria-expanded="false"]) ~ * [data-testid="collapsedControl"]{{
    left: 188px !important;
}}

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
/* ── Sticky page back button ── */
.sw-back-btn-wrap{{
    position:sticky !important;
    top:8px !important;
    z-index:50 !important;
    margin-bottom:12px !important;
    background:rgba(7,9,15,0.92) !important;
    backdrop-filter:blur(8px) !important;
    -webkit-backdrop-filter:blur(8px) !important;
    padding:6px 0 !important;
}}
.sw-back-btn-wrap .stButton>button{{
    background:rgba(255,255,255,0.04) !important;
    border:1px solid rgba(37,99,235,0.3) !important;
    color:#93b4fd !important;
    font-size:12px !important;
    min-height:34px !important;
    width:auto !important;
    padding:0 16px !important;
    max-width:120px !important;
}}
.sw-back-btn-wrap .stButton>button:hover{{
    background:rgba(37,99,235,0.15) !important;
    border-color:{BLUE} !important;
}}

/* ── Mobile & Tablet Responsive ── */
@media (max-width:900px) {{
    /* Marker divs - hidden, just used as anchors */
    .sw-desktop-nav-anchor, .sw-mobile-nav-anchor {{ display: none; }}

    /* ════════════════════════════════════════════════════════════
       MOBILE: Hide desktop topbar, show mobile topbar
       
       Pure HTML/CSS topbar — guaranteed to work because they're not
       Streamlit widgets but raw HTML inside our wrapper divs.
    ════════════════════════════════════════════════════════════ */
    .sw-desktop-topbar {{ display: none !important; }}
    .sw-mobile-topbar-bar {{ display: flex !important; }}
    .sw-nav {{ display: none !important; }}
}}
@media (min-width: 901px) {{
    .sw-desktop-nav-anchor, .sw-mobile-nav-anchor {{ display: none; }}
    .sw-desktop-topbar {{ display: flex !important; }}
    .sw-mobile-topbar-bar {{ display: none !important; }}
}}

/* ── DESKTOP TOPBAR styling (pure HTML) ── */
.sw-desktop-topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 8px;
    margin-bottom: 18px;
    gap: 24px;
}}
.sw-topbar-logo {{ flex-shrink: 0; }}
.sw-topbar-nav {{
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: nowrap;
}}
.sw-topbar-link {{
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: #a8bdd4 !important;
    text-decoration: none !important;
    padding: 8px 14px;
    border: 1px solid rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.04);
    border-radius: 7px;
    transition: all 0.18s ease;
    white-space: nowrap;
    cursor: pointer;
}}
.sw-topbar-link:hover {{
    border-color: rgba(37,99,235,0.5);
    background: rgba(37,99,235,0.1);
    color: #93b4fd !important;
}}
.sw-topbar-link.active {{
    background: #2563eb !important;
    border-color: #2563eb !important;
    color: #fff !important;
    font-weight: 700 !important;
}}
.sw-topbar-link.primary {{
    background: #2563eb !important;
    border-color: #2563eb !important;
    color: #fff !important;
    font-weight: 700 !important;
}}
.sw-topbar-link.primary:hover {{
    background: #1d4ed8 !important;
    box-shadow: 0 4px 16px rgba(37,99,235,0.4);
}}
.sw-topbar-user {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
}}
.sw-topbar-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: 1px solid rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.04);
    border-radius: 7px;
    color: #a8bdd4 !important;
    text-decoration: none !important;
    font-size: 16px;
    transition: all 0.18s ease;
}}
.sw-topbar-icon:hover {{
    background: rgba(37,99,235,0.1);
    border-color: rgba(37,99,235,0.5);
}}

/* ── MOBILE TOPBAR styling (pure HTML) ── */
.sw-mobile-topbar-bar {{
    display: none;  /* shown only on mobile via media query above */
    align-items: center;
    justify-content: space-between;
    padding: 8px 4px;
    margin-bottom: 12px;
}}
.sw-mobile-logo {{ text-decoration: none !important; }}
.sw-mobile-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border: 1px solid rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.04);
    border-radius: 8px;
    color: #a8bdd4 !important;
    text-decoration: none !important;
    font-size: 18px;
}}

    /* Hero text */
    .hero-h1{{font-size:32px !important;letter-spacing:-1px !important;}}
    .hero-sub{{font-size:14px !important;}}
    /* Feature grids → single column */
    .sw-feat-grid{{grid-template-columns:1fr !important;}}
    /* Page padding */
    .pg{{padding:12px 14px 28px !important;}}
    /* Footer */
    .sw-footer-wrap{{padding:24px 20px 20px !important;}}

    /* ════════════════════════════════════════════════════════════
       MOBILE SIDEBAR — narrower, overlay-style, collapsed by default
    ════════════════════════════════════════════════════════════ */
    [data-testid="stSidebar"]{{
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        height: 100vh !important;
        width: 75vw !important;
        min-width: 75vw !important;
        max-width: 280px !important;
        z-index: 999990 !important;
        box-shadow: 4px 0 30px rgba(0, 0, 0, 0.5) !important;
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }}
    /* Sidebar collapsed = slide off-screen */
    [data-testid="stSidebar"][aria-expanded="false"]{{
        transform: translateX(-100%) !important;
        box-shadow: none !important;
    }}
    /* Make sure main content doesn't get pushed by sidebar on mobile */
    section.main, [data-testid="stMain"]{{
        margin-left: 0 !important;
        width: 100vw !important;
    }}
    /* Backdrop overlay when sidebar open on mobile */
    [data-testid="stSidebar"][aria-expanded="true"]::after{{
        content: '';
        position: fixed;
        top: 0; left: 100%;
        width: 100vw;
        height: 100vh;
        background: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(2px);
        z-index: -1;
        pointer-events: auto;
    }}

    /* Collapse button on mobile - bigger and more visible */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"]{{
        width: 44px !important;
        height: 44px !important;
        top: 16px !important;
        left: 16px !important;
    }}
    [data-testid="collapsedControl"] svg,
    [data-testid="stSidebarCollapseButton"] svg{{
        width: 22px !important;
        height: 22px !important;
    }}
    /* When sidebar OPEN on mobile, move collapse button inside sidebar at top right */
    [data-testid="stSidebar"][aria-expanded="true"] ~ * [data-testid="collapsedControl"]{{
        left: calc(75vw - 56px) !important;
        max-width: 280px !important;
    }}

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
        "ranking_sort":"Signal Score","ranking_filter":"All",
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
        # Don't add duplicates
        if not hist or hist[-1] != cur:
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

def back_button(key="page_back"):
    """Render a sticky back button at the top of any page."""
    st.markdown('<div class="sw-back-btn-wrap">', unsafe_allow_html=True)
    bc1, _ = st.columns([1, 6])
    with bc1:
        if st.button("← Back", key=key, use_container_width=True):
            go_back()
    st.markdown('</div>', unsafe_allow_html=True)
# ─────────────────────────────────────────────────────────────
# EXCEL EXPORT
# ─────────────────────────────────────────────────────────────
def make_excel(rows: list, sheet_name: str = "MarketSignalPro Data") -> bytes:
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
            include=False; comp=sc; why="MarketSignalPro composite signal"
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
                include=True; comp=sc; why="MarketSignalPro scoring engine"
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

    # ── Auto-record signal events for composite categories ──
    if is_comp and HAS_SIGNAL_ENGINE:
        try:
            # Get current market regime for context
            try:
                secs_ctx = get_sectors() or {}
                movers_ctx = get_bi_movers() or []
                avg_pct_ctx = sum(m.get("pct",0) for m in movers_ctx)/max(1,len(movers_ctx))
                squeeze_ct = sum(1 for s in stocks if (s.get("info",{}).get("sf",0) or 0)*100 >= 15)
                regime_info = detect_market_regime(secs_ctx, avg_pct_ctx, squeeze_ct)
                current_regime = regime_info.get("regime", "mixed")
            except Exception:
                current_regime = "mixed"

            # Record each stock as a signal event
            for s in stocks[:5]:  # top 5 only to limit storage
                try:
                    ticker_s = s.get("t","")
                    score_s = s.get("sc",0)
                    if not ticker_s or score_s < 50: continue  # Only record meaningful signals
                    q_s = s.get("q") or {}
                    price_s = q_s.get("price",0)
                    if price_s <= 0: continue
                    bd_s = s.get("bd",{})
                    info_s = s.get("info",{})
                    sent_s = s.get("sent",{})
                    df_s = s.get("df")
                    rec_s = s.get("op","WATCH")
                    conf_data = compute_confidence(bd_s, info_s, sent_s, df_s) if df_s is not None else {}
                    record_signal_event(
                        ticker=ticker_s, category=cat, score=score_s,
                        score_components=bd_s, price=price_s,
                        info=info_s, sent=sent_s, recommendation=rec_s,
                        confidence=conf_data, regime=current_regime
                    )
                except Exception:
                    pass
        except Exception:
            pass

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
<span style="color:#e2e8f0;">Market</span><span style="color:#f59e0b;">Signal</span><span style="color:#e2e8f0;">Pro</span>
</span></div>"""

def render_logo_click(key,dest):
    st.markdown(LOGO_HTML, unsafe_allow_html=True)
    if st.button(" ",key=key): nav(dest)

def _render_bottom_nav(active=""):
    """Native-style bottom tab bar — appears only when app is launched in PWA standalone mode (installed)."""
    # Use a unique URL param to navigate via the bottom bar
    nav_items = [
        ("home", "🏠", "Home", "dashboard"),
        ("disc", "🔍", "Discover", "discover"),
        ("watch", "⭐", "Watchlist", "watchlist"),
        ("signals", "📊", "Signals", "signal_track"),
        ("more", "⚙️", "Settings", "settings"),
    ]

    # Build HTML buttons with form-submit links via streamlit query params
    nav_html = ['<nav class="sw-bottom-nav">']
    for key, icon, label, page in nav_items:
        is_active = (active == page)
        active_cls = " active" if is_active else ""
        nav_html.append(
            f'<a href="?bottom_nav={page}" class="sw-bnav-item{active_cls}">'
            f'<span class="sw-bnav-icon">{icon}</span>'
            f'<span class="sw-bnav-label">{label}</span>'
            f'</a>'
        )
    nav_html.append('</nav>')

    # CSS for bottom nav - only shown in PWA standalone mode
    bottom_nav_css = """
    <style>
    .sw-bottom-nav {
        display: none;  /* Hidden by default - only show in standalone PWA */
        position: fixed;
        bottom: 0; left: 0; right: 0;
        background: rgba(8, 11, 20, 0.96);
        backdrop-filter: saturate(180%) blur(20px);
        -webkit-backdrop-filter: saturate(180%) blur(20px);
        border-top: 1px solid rgba(255,255,255,0.06);
        padding: 6px 0 calc(6px + env(safe-area-inset-bottom, 0px));
        z-index: 999990;
        justify-content: space-around;
        align-items: stretch;
    }
    @media (display-mode: standalone) {
        .sw-bottom-nav { display: flex; }
        /* Push main content up so nothing hides behind bottom nav */
        .main .block-container { padding-bottom: 90px !important; }
        /* On standalone, hide the top navigation row since bottom nav is primary */
        .sw-nav { display: none !important; }
        .sw-divider { display: none !important; }
        /* Hide the entire sidebar in standalone — bottom nav handles everything */
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapseButton"] { display: none !important; }
    }
    .sw-bnav-item {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 8px 4px 4px;
        text-decoration: none !important;
        color: #6b7fa0 !important;
        transition: color 0.15s ease-out, transform 0.1s ease-out;
        min-height: 52px;
    }
    .sw-bnav-item:active {
        transform: scale(0.94);
    }
    .sw-bnav-item.active {
        color: #60a5fa !important;
    }
    .sw-bnav-icon {
        font-size: 22px;
        line-height: 1;
        margin-bottom: 3px;
    }
    .sw-bnav-label {
        font-size: 10px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.2px;
    }
    </style>
    """
    st.markdown(bottom_nav_css + "".join(nav_html), unsafe_allow_html=True)

    # Handle bottom nav clicks via URL param
    try:
        params = st.query_params
        if "bottom_nav" in params:
            target = params.get("bottom_nav", "")
            st.query_params.clear()
            if target in {"dashboard","discover","watchlist","signal_track","settings","screener","bi_dashboard"}:
                nav(target)
    except Exception:
        pass


def render_topbar(active=""):
    st.markdown(NAV_CSS, unsafe_allow_html=True)
    # ── PWA bottom nav (only visible when launched as installed app, hidden on desktop & in browser) ──
    if is_authed():
        _render_bottom_nav(active)

    # ════════════════════════════════════════════════════════════
    # DESKTOP TOPBAR — pure HTML/CSS so we can reliably hide on mobile
    # Uses URL params for navigation (no Streamlit button machinery)
    # ════════════════════════════════════════════════════════════
    if is_authed():
        pages=[("Dashboard","dashboard"),("Discover","discover"),("Watchlist","watchlist"),
               ("Screener","screener"),("BI Analytics","bi_dashboard"),("Pricing","pricing"),("Contact","contact")]
        if is_admin(): pages.append(("🛠 Admin","admin"))

        ri={"owner":"👑","admin":"🛡️","premium":"⭐","free":"👤"}.get(st.session_state.role,"👤")
        user_name = st.session_state.user.get("name","")

        # Build nav links as pure HTML
        nav_links = ""
        for lbl, pg in pages:
            is_active_cls = " active" if active == pg else ""
            nav_links += f'<a href="?topbar_nav={pg}" class="sw-topbar-link{is_active_cls}">{lbl}</a>'

        st.markdown(f"""
        <div class="sw-desktop-topbar">
            <div class="sw-topbar-logo">
                <span style="font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;letter-spacing:-0.5px;">
                    <a href="?topbar_nav=dashboard" style="text-decoration:none;">
                        <span style="color:#e2e8f0;">Market</span><span style="color:#f59e0b;">Signal</span><span style="color:#e2e8f0;">Pro</span>
                    </a>
                </span>
            </div>
            <div class="sw-topbar-nav">{nav_links}</div>
            <div class="sw-topbar-user">
                <span style="font-size:12px;color:#6b7fa0;white-space:nowrap;">{ri} {user_name}</span>
                <a href="?topbar_nav=settings" class="sw-topbar-icon" title="Settings">⚙️</a>
                <a href="?topbar_nav=__logout__" class="sw-topbar-icon" title="Log out">↩️</a>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Mobile-only topbar: logo + tiny settings icon
        st.markdown(f"""
        <div class="sw-mobile-topbar-bar">
            <a href="?topbar_nav=dashboard" class="sw-mobile-logo">
                <span style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;letter-spacing:-0.5px;">
                    <span style="color:#e2e8f0;">Market</span><span style="color:#f59e0b;">Signal</span><span style="color:#e2e8f0;">Pro</span>
                </span>
            </a>
            <a href="?topbar_nav=settings" class="sw-mobile-icon">⚙️</a>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Logged-out: same approach
        st.markdown(f"""
        <div class="sw-desktop-topbar">
            <div class="sw-topbar-logo">
                <span style="font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;letter-spacing:-0.5px;">
                    <a href="?topbar_nav=landing" style="text-decoration:none;">
                        <span style="color:#e2e8f0;">Market</span><span style="color:#f59e0b;">Signal</span><span style="color:#e2e8f0;">Pro</span>
                    </a>
                </span>
            </div>
            <div class="sw-topbar-nav">
                <a href="?topbar_nav=features" class="sw-topbar-link">Features</a>
                <a href="?topbar_nav=pricing" class="sw-topbar-link">Pricing</a>
                <a href="?topbar_nav=contact" class="sw-topbar-link">Contact</a>
                <a href="?topbar_nav=login" class="sw-topbar-link">Login</a>
                <a href="?topbar_nav=signup" class="sw-topbar-link primary">Sign Up →</a>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Mobile-only: just the logo
        st.markdown(f"""
        <div class="sw-mobile-topbar-bar">
            <a href="?topbar_nav=landing" class="sw-mobile-logo">
                <span style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;letter-spacing:-0.5px;">
                    <span style="color:#e2e8f0;">Market</span><span style="color:#f59e0b;">Signal</span><span style="color:#e2e8f0;">Pro</span>
                </span>
            </a>
        </div>
        """, unsafe_allow_html=True)
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
            for icon,label,pg in [("📊","Dashboard","dashboard"),("⭐","Watchlist","watchlist"),("🔍","Screener","screener"),("📈","BI Analytics","bi_dashboard"),("📉","Signal Track Record","signal_track"),("💰","Pricing","pricing"),("🔔","Alerts & Settings","settings"),("💬","Contact & Help","contact")]:
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
            st.markdown('<div style="padding:12px 18px;font-size:12px;color:#374f6e;margin-bottom:8px;">Sign in to access MarketSignalPro.</div>',unsafe_allow_html=True)
            if st.button("🚀 Sign Up Free",key="sb_signup",use_container_width=True,type="primary"): nav("signup")
            if st.button("Login →",key="sb_login",use_container_width=True): nav("login")

            st.markdown("""<div style="margin:14px 10px;background:#080c18;border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:12px 14px;">
                <div style="font-size:10px;font-weight:700;color:rgba(255,255,255,.2);letter-spacing:1px;text-transform:uppercase;margin-bottom:7px;">Free Includes</div>
                <div style="font-size:12px;color:#2a3a52;line-height:2.2;">✅ Live market data<br>✅ 7 composite categories<br>✅ Social sentiment<br>✅ Plain-English insights<br>✅ Watchlist</div>
            </div>""",unsafe_allow_html=True)
        st.markdown('<div style="padding:8px 18px;font-size:10px;color:rgba(255,255,255,.1);">© 2026 MarketSignalPro</div>',unsafe_allow_html=True)

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
                        <span style="color:#e2e8f0;">Market</span><span style="color:{GOLD};">Signal</span><span style="color:#e2e8f0;">Pro</span>
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
            <div class="disc">⚠️ <strong style="color:#4a5e7a;">Risk Disclaimer:</strong> Trading stocks involves substantial risk of financial loss. MarketSignalPro provides algorithmic, educational content only — not financial, investment, legal, or tax advice. All signals may be inaccurate or delayed. Past performance does not guarantee future results. Always consult a licensed financial professional before making investment decisions.</div>
            <div style="font-size:10px;color:rgba(255,255,255,.1);margin-top:10px;text-align:right;">© 2026 MarketSignalPro. All rights reserved.</div>
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

    # Mobile-specific CSS for hero reordering
    st.markdown("""
    <style>
    /* On mobile: hero headline must appear BEFORE the demo widget */
    @media (max-width: 992px) {
        .sw-hero-row [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
        }
        .sw-hero-row [data-testid="column"]:first-child {
            order: 1 !important;
        }
        .sw-hero-row [data-testid="column"]:nth-child(2) {
            order: 2 !important;
        }
        .sw-hero-left-block {
            padding: 24px 0 16px !important;
            text-align: center !important;
        }
        .hero-h1 {
            font-size: 32px !important;
            line-height: 1.15 !important;
        }
        .hero-sub {
            font-size: 14px !important;
            padding: 0 8px !important;
        }
        /* Hide the secondary demo widget on phones — too noisy for first impression */
        .sw-hero-demo-wrap {
            display: none !important;
        }
        /* Hide desktop topbar nav on mobile — use Streamlit's hamburger menu instead */
        .sw-desktop-nav {
            display: none !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    # ── TOPBAR — pure HTML for reliable mobile hiding ──
    st.markdown(f"""
    <div class="sw-desktop-topbar">
        <div class="sw-topbar-logo">
            <span style="font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;letter-spacing:-0.5px;">
                <a href="?topbar_nav=landing" style="text-decoration:none;">
                    <span style="color:#e2e8f0;">Market</span><span style="color:#f59e0b;">Signal</span><span style="color:#e2e8f0;">Pro</span>
                </a>
            </span>
        </div>
        <div class="sw-topbar-nav">
            <a href="?topbar_nav=features" class="sw-topbar-link">Features</a>
            <a href="?topbar_nav=pricing" class="sw-topbar-link">Pricing</a>
            <a href="?topbar_nav=login" class="sw-topbar-link">Login</a>
            <a href="?topbar_nav=signup" class="sw-topbar-link primary">Sign Up →</a>
        </div>
    </div>
    <div class="sw-mobile-topbar-bar">
        <a href="?topbar_nav=landing" class="sw-mobile-logo">
            <span style="font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700;letter-spacing:-0.5px;">
                <span style="color:#e2e8f0;">Market</span><span style="color:#f59e0b;">Signal</span><span style="color:#e2e8f0;">Pro</span>
            </span>
        </a>
    </div>
    <hr class="sw-divider">
    """, unsafe_allow_html=True)

    # ── HERO ──
    p_idx=st.session_state.get("hero_panel",0)
    st.markdown('<div class="sw-hero-row">', unsafe_allow_html=True)
    hl,hr=st.columns([5,5],gap="large")
    with hl:
        st.markdown(f"""
        <div class="sw-hero-left-block" style="padding:48px 0 32px 48px;">
            <div style="font-size:11px;font-weight:700;color:{BLUE};letter-spacing:2.5px;text-transform:uppercase;margin-bottom:16px;">Smart Stock Discovery Platform</div>
            <div class="hero-h1">Spot Market<br>Opportunities<br><span class="hi">Before They</span><br><span class="hg">Get Crowded</span></div>
            <div class="hero-sub">Discover trending stocks, squeeze candidates, and momentum shifts using our proprietary 17-signal composite scoring.</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Single CTA section (works on all screens) ──
        if st.button("🚀 Create Free Account", key="h_su", type="primary", use_container_width=True): nav("signup")
        st.markdown('<div style="text-align:center;font-size:13px;color:#6b7fa0;padding:14px 0 6px;">Already have an account?</div>', unsafe_allow_html=True)
        if st.button("Sign In", key="h_login", use_container_width=True): nav("login")

        # Trust line under CTA
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:center;gap:14px;margin-top:18px;font-size:11px;color:#4a5e7a;flex-wrap:wrap;">
            <span>✓ Free forever plan</span>
            <span>·</span>
            <span>✓ No credit card</span>
            <span>·</span>
            <span>✓ Setup in 30 seconds</span>
        </div>
        """, unsafe_allow_html=True)

    with hr:
        st.markdown('<div class="sw-hero-demo-wrap">', unsafe_allow_html=True)
        # Self-contained auto-advancing slideshow — title above, demo below
        # Uses string concat to avoid f-string brace conflicts with DEMO HTML
        hero_comp = (
            '<style>'
            'body{margin:0;padding:0;background:transparent;font-family:Inter,sans-serif;overflow:hidden;}'
            '.tab-row{display:flex;flex-wrap:wrap;gap:14px 18px;margin-bottom:8px;padding:14px 0 0;}'
            '.tab-item{font-size:13px;font-weight:500;color:#374f6e;cursor:pointer;'
            'padding-bottom:5px;border-bottom:2px solid transparent;transition:all 0.2s;white-space:nowrap;}'
            '.tab-item.active{color:#e2e8f0;font-weight:700;border-bottom-color:#2563eb;}'
            '.tab-item:hover{color:#a8bdd4;}'
            '@media(max-width:768px){.tab-row{gap:10px 14px;}.tab-item{font-size:11px;}}'
            '.dots{display:flex;gap:6px;margin-bottom:10px;}'
            '.dot{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,0.15);cursor:pointer;transition:all 0.3s;}'
            '.dot.active{background:#2563eb;width:18px;border-radius:3px;}'
            '.slide-title{font-size:22px;font-weight:900;color:#f1f5f9;letter-spacing:-0.5px;line-height:1.2;margin-bottom:12px;min-height:52px;}'
            '@media(max-width:768px){.slide-title{font-size:18px;min-height:44px;}}'
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
        st.markdown('</div>', unsafe_allow_html=True)  # close sw-hero-demo-wrap
    st.markdown('</div>', unsafe_allow_html=True)  # close sw-hero-row

    # ── Trust bar ──
    st.markdown(f"""
    <style>
    .sw-trust-bar {{
        background:#080b14;
        border-top:1px solid {BORDER};
        border-bottom:1px solid {BORDER};
        padding:20px 48px;
        display:grid;
        grid-template-columns: repeat(4, 1fr) auto;
        gap:24px;
        align-items:center;
    }}
    .sw-trust-stat {{
        display:flex;
        align-items:center;
        gap:10px;
    }}
    .sw-trust-stat-icon {{ font-size:18px; flex-shrink:0; }}
    .sw-trust-stat-num {{
        font-family:'JetBrains Mono',monospace;
        font-size:20px;
        font-weight:700;
        color:#e2e8f0;
        line-height:1.1;
    }}
    .sw-trust-stat-lbl {{
        font-size:11px;
        color:#2a3a52;
        line-height:1.3;
    }}
    .sw-trust-traders {{
        display:flex;
        align-items:center;
        gap:8px;
        justify-self:end;
    }}
    /* Mobile: 2x2 grid, centered, traders moves below */
    @media (max-width:992px) {{
        .sw-trust-bar {{
            grid-template-columns: 1fr 1fr !important;
            padding:18px 16px !important;
            gap:16px !important;
        }}
        .sw-trust-stat {{
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 14px;
            justify-content: flex-start;
        }}
        .sw-trust-stat-num {{ font-size: 18px !important; }}
        .sw-trust-traders {{
            grid-column: 1 / -1;
            justify-self: center !important;
            background: rgba(245,158,11,0.08);
            border: 1px solid rgba(245,158,11,0.2);
            border-radius: 10px;
            padding: 8px 14px;
            margin-top: 4px;
        }}
    }}
    </style>
    <div class="sw-trust-bar">
        <div class="sw-trust-stat">
            <span class="sw-trust-stat-icon">📊</span>
            <div>
                <div class="sw-trust-stat-num">5,000+</div>
                <div class="sw-trust-stat-lbl">US Stocks Covered</div>
            </div>
        </div>
        <div class="sw-trust-stat">
            <span class="sw-trust-stat-icon">🎯</span>
            <div>
                <div class="sw-trust-stat-num">17</div>
                <div class="sw-trust-stat-lbl">Composite Categories</div>
            </div>
        </div>
        <div class="sw-trust-stat">
            <span class="sw-trust-stat-icon">⚡</span>
            <div>
                <div class="sw-trust-stat-num">Real-Time</div>
                <div class="sw-trust-stat-lbl">Sentiment Data</div>
            </div>
        </div>
        <div class="sw-trust-stat">
            <span class="sw-trust-stat-icon">💰</span>
            <div>
                <div class="sw-trust-stat-num">$0</div>
                <div class="sw-trust-stat-lbl">To Get Started</div>
            </div>
        </div>
        <div class="sw-trust-traders">
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
    @media(max-width:992px){{
        .sw-feat-grid{{grid-template-columns:1fr !important;gap:32px !important;padding:0 16px !important;}}
        .sw-feat-grid h1, .sw-feat-grid .feat-title{{font-size:22px !important;line-height:1.2 !important;}}
        .sw-feat-grid .feat-title-block{{min-height:auto !important;text-align:center;}}
        .sw-feat-grid .sw-demo-wrap{{height:380px !important;}}
        .sw-feat-grid .sw-prem-box{{height:auto !important;min-height:380px !important;}}
    }}
    /* Both content boxes same fixed height on desktop */
    .sw-demo-wrap{{overflow:hidden;height:320px;box-sizing:border-box;flex:none!important;}}
    .sw-demo-wrap>div{{height:100%;}}
    .sw-prem-box{{height:320px;box-sizing:border-box;display:flex;flex-direction:column;flex:none!important;}}
    .feat-title{{font-size:26px;font-weight:900;color:#f1f5f9;letter-spacing:-1px;line-height:1.15;margin-bottom:8px;}}
    .feat-title-block{{min-height:105px;margin-bottom:16px;}}
    </style>
    <div class="sw-feat-grid" style="margin-bottom:28px;">
      <div style="display:flex;flex-direction:column;height:100%;">
        <div class="feat-title-block">
          <div class="feat-title">Find Trending Stocks<br><span style="color:{BLUE};">Before the Crowd</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Discover top stocks making waves across social media and the market.</div>
        </div>
        <div class="sw-demo-wrap">{DEMO[0]}</div>
      </div>
      <div style="display:flex;flex-direction:column;height:100%;">
        <div class="feat-title-block">
          <div class="feat-title">Scan For Short Squeeze<br><span style="color:{BLUE};">Candidates</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Spot stocks with heavy short interest and growing momentum before the move.</div>
        </div>
        <div class="sw-demo-wrap">{DEMO[1]}</div>
      </div>
    </div>
    <div class="sw-feat-grid">
      <div style="display:flex;flex-direction:column;height:100%;">
        <div class="feat-title-block">
          <div class="feat-title">Smart Insights<br>in Simple <span style="color:{BLUE};">Language</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Every technical signal explained in plain English. No finance degree needed.</div>
        </div>
        <div class="sw-demo-wrap">{DEMO[2]}</div>
      </div>
      <div style="display:flex;flex-direction:column;height:100%;">
        <div class="feat-title-block">
          <div class="feat-title">Go Premium For<br><span style="color:{GOLD};">Real-Time Signals &amp;<br>Deeper Analysis</span></div>
          <div style="font-size:13px;color:#374f6e;line-height:1.7;">Upgrade to unlock advanced screening, unlimited alerts, and premium watchlists.</div>
        </div>
        <div class="sw-prem-box" style="background:#0d1525;border:1px solid rgba(245,158,11,.25);border-radius:11px;overflow:hidden;">
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
        <div style="font-size:13px;color:#374f6e;margin-bottom:16px;">Join 1,847+ traders already using MarketSignalPro · Cancel anytime · No credit card required</div>
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
            <span style="background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.35);font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;white-space:nowrap;">✨ Unique to MarketSignalPro</span>
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
    # Wrap signal cards in styled container so we can make them mobile-friendly
    st.markdown("""
    <style>
    .sw-signal-grid [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:10px;}
    .sw-signal-grid .card{padding:12px 14px !important;min-height:78px !important;}
    @media (max-width:900px){
        /* 2-column grid on mobile (instead of 1-column stack from global rule) */
        .sw-signal-grid [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important;gap:8px !important;}
        .sw-signal-grid [data-testid="stHorizontalBlock"] [data-testid="column"]{
            min-width:48% !important;max-width:48% !important;flex:1 1 48% !important;
        }
        .sw-signal-grid .card{
            padding:8px 10px !important;
            min-height:auto !important;
            margin-bottom:6px !important;
        }
        .sw-signal-card-title{font-size:11px !important;line-height:1.3 !important;}
        .sw-signal-card-desc{font-size:10px !important;line-height:1.4 !important;}
        .sw-signal-card-badge{font-size:8px !important;padding:1px 5px !important;}
    }
    </style>
    <div class="sw-signal-grid">
    """, unsafe_allow_html=True)
    cg=st.columns(3,gap="small")
    for i,(cat,(desc,tier)) in enumerate(cg_items):
        with cg[i%3]:
            c=color_map.get(cat,BLUE)
            tier_b=f'<span class="sw-signal-card-badge" style="background:rgba(245,158,11,.12);color:{GOLD};font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(245,158,11,.3);">⭐ PRO</span>' if tier=="premium" else f'<span class="sw-signal-card-badge" style="background:rgba(34,197,94,.1);color:#4ade80;font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;border:1px solid rgba(34,197,94,.3);">FREE</span>'
            st.markdown(f"""<div class="card" style="border-left:3px solid {c};">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:5px;gap:6px;">
                    <div class="sw-signal-card-title" style="font-size:13px;font-weight:700;color:#e2e8f0;">{cat}</div>{tier_b}
                </div>
                <div class="sw-signal-card-desc" style="font-size:11px;color:#374f6e;line-height:1.5;">{desc}</div>
            </div>""",unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

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
        ("Is this financial advice?","No. MarketSignalPro is an educational analysis tool providing algorithmic signals. Nothing on this platform constitutes financial, investment, legal, or tax advice. Always consult a licensed financial advisor before making investment decisions."),
        ("What are the Composite Categories?","MarketSignalPro proprietary composite categories combine multiple independent data signals to surface unique setups. For example, '🔥💥 Squeeze + Buzz' finds stocks with both high short float AND social momentum trending simultaneously — a specific multi-factor signal you won't find on other platforms."),
        ("What markets does MarketSignalPro cover?","US equity markets including NASDAQ, NYSE, S&P 500, Russell, and high-volume small caps. Data includes real-time price, volume, fundamentals, and live social sentiment from StockTwits."),
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
    back_button("ft_back")
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
        <div style="font-size:38px;font-weight:900;color:#f1f5f9;letter-spacing:-1.5px;margin-bottom:10px;">Everything in MarketSignalPro</div>
        <div style="font-size:15px;color:#374f6e;max-width:560px;margin:0 auto;">Built for traders who want data-driven clarity — not noise. Every feature is designed to answer one question: <em>should I pay attention to this stock right now?</em></div>
    </div>
    """, unsafe_allow_html=True)

    features_data = [
        ("🎯","Proprietary Composite Scoring","17 unique composite categories combining RSI, MACD, volume, short interest, social sentiment, and Bollinger Bands into single actionable signals. Categories like '🔥💥 Squeeze + Buzz', '🌪️ Volatility Squeeze', and '🎯📊 Triple Lock' are only available on MarketSignalPro. Each category has a specific multi-factor entry criterion that filters our full universe in real time.","All plans"),
        ("🟢","BUY / WATCH / AVOID Signals","Every stock gets a clear recommendation based on our scoring engine — STRONG BUY, BUY, SQUEEZE BUY, WATCH, HOLD/WAIT, or AVOID — with plain-English reasoning explaining exactly why the signal was triggered. No jargon. No unexplained scores.","All plans"),
        ("💡","Plain-English Technical Analysis","RSI, MACD, moving average crossovers, Bollinger Bands, and volume spikes all translated into conversational sentences. We explain what a Golden Cross means in terms a beginner understands while still giving experts the data they need.","All plans"),
        ("📡","Live Social Sentiment","Real-time StockTwits data showing bullish/bearish % for any stock, watchlist counts, and trending detection. Our composite categories use this data to find early momentum before price moves.","All plans"),
        ("📊","Market Overview Dashboard","Live index data (NASDAQ, S&P 500, DOW, VIX, Russell), sector performance heatmap, market pulse indicator, and top trending tickers in a single clean view.","All plans"),
        ("⭐","Smart Watchlist","Track your stocks with automatic daily scoring. Premium users get watchlist analytics showing average score, % in the green, risk distribution, and sentiment breakdown across holdings.","All plans (Premium: analytics)"),
        ("🔔","Price Alerts","Set price-above or price-below alerts for any ticker. Alerts are managed from your account settings and displayed in your dashboard.","All plans"),
        ("🔍","Advanced Stock Screener","Multi-factor screener with RSI range filters, MACD bullish/bearish filter, above/below MA filter, volume spike detection, minimum MarketSignalPro score, short float threshold, and category filters. Save and name your screener configurations.","Premium"),
        ("📈","BI Analytics Dashboard","Interactive Plotly charts: Top Gainers/Losers bar charts, Sector Performance bar chart, Social Sentiment bubble chart, Volume Surge scatter plot, and the Composite Opportunity Matrix — our exclusive heatmap showing signal strength across 10 tickers × 5 signal types.","Premium"),
        ("💥","Short Squeeze Scanner","Dedicated scanner identifying stocks with high short float (>10%), high days-to-cover, and rising momentum. Filters by social trending and volume to find squeeze setups before they run.","Premium"),
        ("📉→📈","Deep Stock Reports","Full stock detail pages with 60-day price chart + MA20/MA50 overlaid, volume bar chart vs average, complete plain-English analysis, social sentiment bar, score breakdown, why-flagged section, and related stocks.","Premium (charts)"),
        ("🎪","Email Digest (Coming Q3 2026)","Daily or weekly digest of your top-scored watchlist stocks, new BUY signals, and trending composite category alerts delivered to your inbox. Configurable from account settings.","Premium"),
        ("🛠️","Admin Panel","Full user management (promote/demote roles, delete accounts), API configuration with Twelve Data integration, site analytics with simulated growth charts, data source health monitoring, and security checklist with Streamlit Secrets setup guide.","Admin/Owner"),
        ("🔑","Ranking Controls","Sort and filter any category by MarketSignalPro Score, % change today, volume ratio, short float, or social sentiment. Drag-and-drop ranking priority controls for power users.","Premium"),
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
        st.markdown(f'<div style="text-align:center;padding:36px 0 24px;"><div style="font-size:26px;font-weight:800;color:#e2e8f0;margin-bottom:6px;">Welcome Back 👋</div><div style="font-size:13px;color:#374f6e;">Sign in to your MarketSignalPro account</div></div>',unsafe_allow_html=True)
        with st.form("lf",clear_on_submit=False):
            email=st.text_input("Email address",label_visibility="visible")
            pw=st.text_input("Password",type="password",label_visibility="visible")
            if st.form_submit_button("Sign In →",type="primary",use_container_width=True):
                if not email or not pw: st.error("Please enter your email and password.")
                elif login(email,pw):
                    st.session_state["_login_welcome"] = st.session_state.user.get("name","")
                    # Honor intended destination
                    intended = st.session_state.pop("_intended_page", None)
                    nav(intended if intended else "dashboard")
                else: st.error("Invalid email or password.")

        # Show hints based on whether secrets are configured
        has_secrets=False
        try: has_secrets=bool(st.secrets.get("owner_email","") or st.secrets.get("owner_pw_hash",""))
        except: pass

        if not has_secrets:
            st.markdown(f'<div style="background:#080b14;border:1px solid {BORDER};border-radius:8px;padding:12px 14px;margin-top:12px;font-size:12px;color:#374f6e;"><span style="color:#93b4fd;font-weight:600;">Demo accounts:</span><br><span style="font-family:\'JetBrains Mono\',monospace;">demo@marketsignalpro.com</span> / <span style="font-family:\'JetBrains Mono\',monospace;">demo123</span><br><span style="font-family:\'JetBrains Mono\',monospace;">premium@marketsignalpro.com</span> / <span style="font-family:\'JetBrains Mono\',monospace;">premium1</span></div>',unsafe_allow_html=True)
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
            agree=st.checkbox("I agree to the Terms of Service. I understand MarketSignalPro is for educational purposes only and is not financial advice.")
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
                        if not ok2:
                            st.session_state["_email_error"] = info
                            if info and info.startswith("DEMO_CODE:"):
                                st.session_state["_demo_code"]=info.split(":",1)[1]
                        else:
                            st.session_state.pop("_email_error", None)
                            st.session_state.pop("_demo_code", None)
                        nav("verify_email")
                    else: st.error(msg)
        if st.button("Already have an account? Sign In",key="s2l",use_container_width=True): nav("login")

def _send_telegram(chat_id, message):
    """Send a Telegram message via the MarketSignalPro bot. Returns (True, None) or (False, error)."""
    try:
        bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        if not bot_token or not chat_id:
            return False, "TELEGRAM_NOT_CONFIGURED"
        import requests as _r
        resp = _r.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
        if resp.status_code == 200:
            return True, None
        return False, f"Telegram error {resp.status_code}: {resp.text[:120]}"
    except Exception as e:
        return False, str(e)

def _send_push_notification(player_ids, title, message, url=None):
    """Send a OneSignal web/mobile push notification. player_ids: list of OneSignal subscription IDs.
    Returns (True, None) or (False, error)."""
    try:
        app_id  = st.secrets.get("ONESIGNAL_APP_ID", "")
        api_key = st.secrets.get("ONESIGNAL_REST_API_KEY", "")
        if not app_id or not api_key:
            return False, "ONESIGNAL_NOT_CONFIGURED"
        if not player_ids:
            return False, "NO_RECIPIENTS"
        import requests as _r
        payload = {
            "app_id": app_id,
            "include_player_ids": player_ids if isinstance(player_ids, list) else [player_ids],
            "headings": {"en": title},
            "contents": {"en": message},
        }
        if url:
            payload["url"] = url
        resp = _r.post(
            "https://onesignal.com/api/v1/notifications",
            headers={"Authorization": f"Basic {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=10
        )
        if resp.status_code in (200, 201):
            return True, None
        return False, f"OneSignal error {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)

def _send_password_reset(email, reset_token):
    """Send password reset email through Resend. Returns (True, None) or (False, info)."""
    try:
        resend_key = st.secrets.get("RESEND_API_KEY", "")
        app_url = _get_app_url()
        reset_url = f"{app_url}/?reset_token={reset_token}&email={email}"

        if not resend_key:
            return False, "RESEND_API_KEY missing from Streamlit Secrets"

        import requests as _r

        html = f"""
        <div style="margin:0;padding:0;background:#07090f;font-family:Inter,Arial,Helvetica,sans-serif;color:#e2e8f0;">
            <div style="max-width:600px;margin:0 auto;padding:36px 24px;">
                <div style="background:#0d1525;border:1px solid rgba(96,165,250,0.18);border-radius:18px;padding:30px;box-shadow:0 16px 40px rgba(0,0,0,0.25);">
                    <div style="font-size:24px;font-weight:800;letter-spacing:-0.4px;margin-bottom:22px;">
                        <span style="color:#3b82f6;">Market</span><span style="color:#f59e0b;">Signal</span><span style="color:#e2e8f0;">Pro</span>
                    </div>
                    <h1 style="margin:0 0 10px;color:#f8fafc;font-size:24px;line-height:1.25;font-weight:800;">Reset your password</h1>
                    <p style="margin:0 0 24px;color:#93a4bd;font-size:15px;line-height:1.6;">Click the button below to reset your MarketSignalPro password. This link expires in 1 hour.</p>
                    <a href="{reset_url}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;border-radius:10px;padding:13px 22px;font-size:15px;font-weight:800;box-shadow:0 8px 22px rgba(37,99,235,0.35);">Reset password</a>
                    <div style="height:1px;background:rgba(255,255,255,0.08);margin:28px 0 18px;"></div>
                    <p style="margin:0 0 8px;color:#718096;font-size:12px;line-height:1.5;">If the button does not work, copy and paste this link into your browser:</p>
                    <p style="margin:0 0 18px;color:#93b4fd;font-size:12px;line-height:1.5;word-break:break-all;">{reset_url}</p>
                    <p style="margin:0;color:#64748b;font-size:12px;line-height:1.5;">If you did not request this, you can safely ignore this email.</p>
                </div>
                <p style="text-align:center;margin:18px 0 0;color:#475569;font-size:11px;">MarketSignalPro · AI-powered stock signals, simplified.</p>
            </div>
        </div>
        """

        text_body = f"""MarketSignalPro

Reset your password

Click this link to reset your password. This link expires in 1 hour:
{reset_url}

If you did not request this, you can ignore this email."""

        resp = _r.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": "MarketSignalPro <support@marketsignalpro.com>",
                "to": [email],
                "subject": "Reset your MarketSignalPro password",
                "html": html,
                "text": text_body,
                "reply_to": ["support@marketsignalpro.com"],
            },
            timeout=10,
        )

        if resp.status_code in (200, 201):
            return True, None

        return False, f"Resend error {resp.status_code}: {resp.text}"

    except Exception as e:
        return False, f"Email exception: {e}"


def _send_verification_email(email, code):
    """Send 6-digit email verification code through Resend. Returns (True, None) or (False, info)."""
    try:
        resend_key = st.secrets.get("RESEND_API_KEY", "")

        if not resend_key:
            return False, "RESEND_API_KEY missing from Streamlit Secrets"

        import requests as _r

        html = f"""
        <div style="margin:0;padding:0;background:#07090f;font-family:Inter,Arial,Helvetica,sans-serif;color:#e2e8f0;">
            <div style="max-width:600px;margin:0 auto;padding:36px 24px;">
                <div style="background:#0d1525;border:1px solid rgba(96,165,250,0.18);border-radius:18px;padding:30px;box-shadow:0 16px 40px rgba(0,0,0,0.25);">
                    <div style="font-size:24px;font-weight:800;letter-spacing:-0.4px;margin-bottom:22px;">
                        <span style="color:#3b82f6;">Market</span><span style="color:#f59e0b;">Signal</span><span style="color:#e2e8f0;">Pro</span>
                    </div>
                    <h1 style="margin:0 0 10px;color:#f8fafc;font-size:24px;line-height:1.25;font-weight:800;">Verify your email</h1>
                    <p style="margin:0 0 18px;color:#93a4bd;font-size:15px;line-height:1.6;">Use this verification code to finish creating your MarketSignalPro account.</p>
                    <div style="background:#080c18;border:1px solid rgba(37,99,235,0.30);border-radius:14px;padding:22px 18px;text-align:center;margin:20px 0 18px;">
                        <div style="color:#64748b;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px;">Verification code</div>
                        <div style="color:#3b82f6;font-size:42px;font-weight:900;letter-spacing:10px;line-height:1;">{code}</div>
                    </div>
                    <p style="margin:0;color:#93a4bd;font-size:13px;line-height:1.6;">This code expires in 10 minutes.</p>
                    <div style="height:1px;background:rgba(255,255,255,0.08);margin:22px 0 16px;"></div>
                    <p style="margin:0;color:#64748b;font-size:12px;line-height:1.5;">If you did not request this, you can safely ignore this email.</p>
                </div>
                <p style="text-align:center;margin:18px 0 0;color:#475569;font-size:11px;">MarketSignalPro · AI-powered stock signals, simplified.</p>
            </div>
        </div>
        """

        text_body = f"""MarketSignalPro

Verify your email

Your verification code is: {code}

This code expires in 10 minutes.

If you did not request this, you can ignore this email."""

        resp = _r.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {resend_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": "MarketSignalPro <support@marketsignalpro.com>",
                "to": [email],
                "subject": "Your MarketSignalPro verification code",
                "html": html,
                "text": text_body,
                "reply_to": ["support@marketsignalpro.com"],
            },
            timeout=10,
        )

        if resp.status_code in (200, 201):
            return True, None

        return False, f"Resend error {resp.status_code}: {resp.text}"

    except Exception as e:
        return False, f"Email exception: {e}"


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

        if st.session_state.get("_email_error"):
            st.error(st.session_state["_email_error"])

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
                    for k in ["_verify_code","_verify_email","_verify_user","_demo_code","_email_error"]:
                        st.session_state.pop(k,None)
                    st.session_state["_signup_success"] = udata.get("name","")
                    st.success("✅ Email verified! Welcome to MarketSignalPro.")
                    time.sleep(0.3)
                    nav("dashboard")
                else:
                    st.error("❌ Incorrect code. Please try again.")

        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("Resend code", key="resend_v"):
            code = str(random.randint(100000,999999))
            st.session_state["_verify_code"] = code
            ok,info = _send_verification_email(email, code)
            if not ok:
                st.session_state["_email_error"] = info
                if info and info.startswith("DEMO_CODE:"):
                    st.session_state["_demo_code"] = info.split(":",1)[1]
                    st.success("Code regenerated (demo mode — shown above)")
                else:
                    st.error(f"Send failed: {info}")
            else:
                st.session_state.pop("_email_error", None)
                st.session_state.pop("_demo_code", None)
                st.success("✅ New code sent!")
        if st.button("← Back to Sign Up", key="v_back"):
            for k in ["_verify_code","_verify_email","_verify_user","_demo_code","_email_error"]:
                st.session_state.pop(k,None)
            nav("signup")

# ─────────────────────────────────────────────────────────────
# PAGE: CONTACT
# ─────────────────────────────────────────────────────────────
def page_contact():
    render_topbar()
    back_button("ct_back")
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
            <a href="mailto:support@marketsignalpro.com" style="font-size:13px;font-weight:700;color:#93b4fd;text-decoration:none;">support@marketsignalpro.com</a>
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
    st.markdown('<div style="font-size:12px;color:#374f6e;margin-bottom:14px;">Ask anything about MarketSignalPro — features, categories, signals, billing, or how to use the platform.</div>',unsafe_allow_html=True)

    # Chat history
    if "support_chat" not in st.session_state:
        st.session_state.support_chat = [
            {"role":"assistant","content":"Hi! I'm the MarketSignalPro support assistant. I can help with questions about the platform, our composite signal categories, billing, features, or anything else. What can I help you with today?"}
        ]

    # Display chat
    for msg in st.session_state.support_chat:
        if msg["role"]=="assistant":
            st.markdown(f'''<div style="display:flex;gap:10px;margin-bottom:12px;align-items:flex-start;">
                <div style="background:{BLUE};border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;">MSP</div>
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
                    sys_prompt = """You are the MarketSignalPro customer support assistant. MarketSignalPro is a premium stock intelligence platform.

Key facts:
- MarketSignalPro has 17 AI-powered composite signal categories combining RSI, MACD, volume, social sentiment, short interest
- Free plan: 7 composite categories, market overview, watchlist (10 stocks), BUY/AVOID signals
- Premium ($29/mo): All 17 categories, squeeze scanner, advanced screener, BI analytics, score breakdowns, unlimited watchlist
- Annual ($199/yr): Everything in Premium + priority support, early access, export, API access
- Data sources: Yahoo Finance (free), Twelve Data (optional), StockTwits (social sentiment)
- Signals are educational/algorithmic only — NOT financial advice
- Back button works to go to previous page
- For billing: support@marketsignalpro.com

Be helpful, concise, and friendly. If asked about a specific stock or investment advice, remind them signals are educational only."""
                    msgs = [{"role":m["role"],"content":m["content"]} for m in st.session_state.support_chat]
                    # Get Anthropic API key from secrets
                    try: anth_key = st.secrets.get("ANTHROPIC_API_KEY","")
                    except: anth_key = ""
                    if not anth_key:
                        answer = "Support chat requires ANTHROPIC_API_KEY in Streamlit Secrets. In the meantime, email support@marketsignalpro.com — we respond within 24 hours!"
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
                            answer = f"I'm having trouble right now (status {resp.status_code}). Please email support@marketsignalpro.com for immediate help."
                except Exception as e:
                    answer = f"Connection issue. Please email support@marketsignalpro.com — we typically respond within 24 hours."
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
        ("What are the composite signal categories?","MarketSignalPro has 17 proprietary categories combining multiple signals simultaneously — like RSI + short float + social sentiment — to surface setups not visible through standard TA."),
        ("Is this financial advice?","No. MarketSignalPro provides algorithmic, educational signals only. Nothing constitutes financial advice. Always consult a licensed financial advisor."),
        ("How do I cancel my subscription?","Go to Settings → Subscription → Open Billing Portal. You can cancel anytime with no questions asked."),
        ("Can I get a refund?","Yes — contact support@marketsignalpro.com within 30 days of your subscription start date."),
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
        <div style="margin-top:12px;text-align:center;font-size:12px;color:#2a3a52;">Questions? <a href="mailto:support@marketsignalpro.com" style="color:#93b4fd;">support@marketsignalpro.com</a></div>
        """, unsafe_allow_html=True)
    st.stop()

# ── 3. Payment notifications ──
if st.session_state.get("_push_registered"):
    st.session_state.pop("_push_registered", None)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#04200d,#0d1525);
                border:1px solid rgba(34,197,94,0.4);border-radius:14px;
                padding:20px 24px;margin-bottom:18px;">
        <div style="display:flex;align-items:center;gap:14px;">
            <div style="font-size:32px;">🔔</div>
            <div>
                <div style="font-size:16px;font-weight:800;color:#4ade80;margin-bottom:4px;">
                    Push Notifications Enabled!
                </div>
                <div style="font-size:13px;color:#374f6e;line-height:1.6;">
                    You'll receive instant push alerts when MarketSignalPro detects new opportunities on stocks you follow.
                    <br><strong style="color:#e2e8f0;">Pro tip:</strong> On mobile, tap the share icon and "Add to Home Screen" to install MarketSignalPro as an app.
                </div>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

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
            Welcome to MarketSignalPro {plan_name}!
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
            Need help? Email <a href="mailto:support@marketsignalpro.com" style="color:#93b4fd;">support@marketsignalpro.com</a>
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
    st.toast(f"🎉 Account created! Welcome to MarketSignalPro, {name}!", icon="🚀")
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
auth_required={"dashboard","discover","watchlist","screener","bi_dashboard","stock_detail","settings","admin"}
premium_required={"screener","bi_dashboard"}  # These show upgrade gate for free users
admin_required={"admin"}

# Auth check first
if page in auth_required and not is_authed():
    # Save intended destination then show login
    st.session_state["_intended_page"] = page
    page_login()
# Admin check
elif page in admin_required and not is_admin():
    st.markdown("""<div style="background:#200404;border:1px solid rgba(239,68,68,0.3);border-radius:14px;
                padding:32px;text-align:center;margin:60px auto;max-width:520px;">
        <div style="font-size:42px;margin-bottom:14px;">🛡️</div>
        <div style="font-size:20px;font-weight:800;color:#f87171;margin-bottom:8px;">Admin Access Required</div>
        <div style="font-size:13px;color:#374f6e;line-height:1.7;">This page is restricted to admin users only.
        Contact support if you believe you should have access.</div>
    </div>""", unsafe_allow_html=True)
    if st.button("← Return to Dashboard", key="adm_deny_back", use_container_width=True):
        nav("dashboard")
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
elif page=="screener":     page_screener()  # Page handles premium gating internally
elif page=="bi_dashboard":
    if is_premium():
        page_bi()
    else:
        # Show premium upgrade gate (not blank page)
        render_topbar("bi_dashboard")
        st.markdown('<div class="pg">', unsafe_allow_html=True)
        back_button("bi_lock_back")
        st.markdown('<div style="font-size:22px;font-weight:800;color:#e2e8f0;margin-bottom:8px;">📊 BI Analytics Dashboard</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:13px;color:#374f6e;margin-bottom:20px;">Market-wide intelligence across gainers, sectors, sentiment, and composite signals.</div>', unsafe_allow_html=True)
        render_lock("BI Analytics Dashboard")
        st.markdown('</div>', unsafe_allow_html=True)
elif page=="signal_track": page_signal_track() if is_authed() else page_login()
elif page=="stock_detail": page_detail()
elif page=="settings":     page_settings()
elif page=="admin":        page_admin()  # Already guarded above
else: page_landing()
