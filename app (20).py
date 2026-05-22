
import os
import re
import json
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(
    page_title="MarketSignalPro | Coming Soon",
    page_icon="favicon.ico",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# CONFIG
# ============================================================
ADMIN_EMAIL = st.secrets.get("ADMIN_EMAIL", "support@marketsignalpro.com")
RESEND_API_KEY = st.secrets.get("RESEND_API_KEY", "")
FROM_EMAIL = st.secrets.get("FROM_EMAIL", "MarketSignalPro <support@marketsignalpro.com>")
GOOGLE_SHEETS_WEBHOOK_URL = st.secrets.get("GOOGLE_SHEETS_WEBHOOK_URL", "")
SIGNUPS_FILE = "marketsignalpro_signups.csv"

# Anti-spam settings
MIN_SUBMIT_SECONDS = 2.0          # bots typically fire instantly
MAX_SIGNUPS_PER_IP_PER_HOUR = 3   # prevents list-bombing abuse

# In-memory rate-limit store. Resets on container restart (fine for waitlist).
# Key: client IP. Value: list of recent submit timestamps.
if "_msp_signup_attempts" not in st.session_state:
    st.session_state._msp_signup_attempts = {}


# ============================================================
# ANTI-SPAM / BACKUP HELPERS
# ============================================================
def get_client_ip() -> str:
    """Best-effort client IP detection through Streamlit Cloud's proxy."""
    try:
        headers = st.context.headers
    except Exception:
        return "unknown"

    if not headers:
        return "unknown"

    # X-Forwarded-For: client, proxy1, proxy2 — the leftmost is the original client
    forwarded = headers.get("X-Forwarded-For", "") or headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"

    real_ip = headers.get("X-Real-IP", "") or headers.get("x-real-ip", "")
    return real_ip.strip() or "unknown"


def is_mobile_request() -> bool:
    """Detect mobile devices from the User-Agent header.
    Used to render the live-preview iframe in the right position
    (inline above the form on mobile, in the right column on desktop)
    without duplicating the iframe in the DOM.
    """
    try:
        headers = st.context.headers
    except Exception:
        return False
    if not headers:
        return False

    ua = headers.get("User-Agent", "") or headers.get("user-agent", "")
    if not ua:
        return False

    mobile_signals = ("Mobile", "Android", "iPhone", "iPod", "BlackBerry",
                      "Windows Phone", "Opera Mini", "IEMobile")
    return any(signal in ua for signal in mobile_signals)


def is_rate_limited(ip: str) -> bool:
    """Return True if this IP has hit the per-hour signup cap."""
    if ip == "unknown":
        return False  # don't penalize users we can't identify

    now = time.time()
    store = st.session_state._msp_signup_attempts
    recent = [ts for ts in store.get(ip, []) if now - ts < 3600]
    store[ip] = recent
    return len(recent) >= MAX_SIGNUPS_PER_IP_PER_HOUR


def record_signup_attempt(ip: str) -> None:
    if ip == "unknown":
        return
    store = st.session_state._msp_signup_attempts
    store.setdefault(ip, []).append(time.time())


def backup_to_google_sheets(row: dict) -> None:
    """Fire-and-forget POST to a Google Apps Script webhook. Silent on failure."""
    if not GOOGLE_SHEETS_WEBHOOK_URL:
        return
    try:
        requests.post(
            GOOGLE_SHEETS_WEBHOOK_URL,
            json={
                "timestamp": row.get("timestamp", ""),
                "email": row.get("email", ""),
                "name": row.get("name", ""),
                "source": row.get("source", ""),
            },
            timeout=6,
        )
    except Exception:
        # Backup failure must never block a successful signup.
        pass


# ============================================================
# SIGNUP STORAGE + EMAIL
# ============================================================
def load_signups() -> pd.DataFrame:
    columns = ["timestamp", "first_name", "last_name", "name", "email", "source"]
    if not os.path.exists(SIGNUPS_FILE):
        return pd.DataFrame(columns=columns)

    try:
        df = pd.read_csv(SIGNUPS_FILE)
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        return df[columns]
    except Exception:
        return pd.DataFrame(columns=columns)


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def save_signup(first_name: str, last_name: str, email: str, source: str = "coming_soon"):
    df = load_signups()
    clean_first = " ".join((first_name or "").strip().split())
    clean_last = " ".join((last_name or "").strip().split())
    clean_name = f"{clean_first} {clean_last}".strip()
    clean_email = email.strip().lower()

    if not is_valid_email(clean_email):
        return False, "Please enter a valid email address."

    if not df.empty and clean_email in df["email"].astype(str).str.lower().values:
        return False, "You are already on the early-access list."

    row = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "first_name": clean_first,
        "last_name": clean_last,
        "name": clean_name,
        "email": clean_email,
        "source": source,
    }

    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(SIGNUPS_FILE, index=False)
    return True, row


def send_signup_email(row: dict):
    if not RESEND_API_KEY:
        return False, "Signup saved, but RESEND_API_KEY is not set in Streamlit secrets."

    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;background:#07090f;color:#e2e8f0;padding:32px;border-radius:14px;">
      <h2 style="margin:0 0 14px;color:#ffffff;">Market<span style="color:#f59e0b;">Signal</span>Pro</h2>
      <h3 style="margin:0 0 20px;color:#60a5fa;">New early-access signup</h3>
      <p><strong>Name:</strong> {row["name"]}</p>
      <p><strong>Email:</strong> {row["email"]}</p>
      <p><strong>Time:</strong> {row["timestamp"]}</p>
      <p style="color:#7c8fae;font-size:12px;margin-top:24px;">This was submitted from the MarketSignalPro coming-soon page.</p>
    </div>
    """

    payload = {
        "from": FROM_EMAIL,
        "to": [ADMIN_EMAIL],
        "subject": "New MarketSignalPro early-access signup",
        "html": html,
        "text": (
            "New MarketSignalPro early-access signup\n\n"
            f"Name: {row['name']}\n"
            f"Email: {row['email']}\n"
            f"Time: {row['timestamp']}\n"
        ),
    }

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=12,
        )

        if response.status_code in (200, 201):
            return True, None

        return False, f"Resend error {response.status_code}: {response.text}"
    except Exception as exc:
        return False, f"Resend request failed: {exc}"


def send_user_confirmation_email(row: dict):
    """Send a branded welcome email to the person who just signed up."""
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not configured."

    first = (row.get("first_name") or row.get("name") or "there").strip().split(" ")[0] or "there"

    html = f"""
    <div style="background:#07090f;padding:40px 20px;font-family:Inter,Arial,sans-serif;">
      <div style="max-width:560px;margin:0 auto;background:linear-gradient(180deg,#0d1424,#080b14);border:1px solid rgba(96,165,250,.18);border-radius:18px;overflow:hidden;">

        <div style="padding:32px 36px 14px;border-bottom:1px solid rgba(255,255,255,.06);">
          <div style="font-size:22px;font-weight:900;letter-spacing:-.5px;color:#ffffff;">
            Market<span style="background:linear-gradient(90deg,#60a5fa,#f59e0b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">Signal</span>Pro
          </div>
          <div style="margin-top:6px;font-size:11px;font-weight:700;letter-spacing:2px;color:#60a5fa;text-transform:uppercase;">
            Welcome to the early-access list
          </div>
        </div>

        <div style="padding:30px 36px 12px;">
          <h2 style="margin:0 0 14px;font-size:24px;font-weight:900;color:#ffffff;letter-spacing:-.6px;">
            You're in, {first}.
          </h2>
          <p style="margin:0 0 18px;font-size:15px;line-height:1.7;color:#cbd5e1;">
            Thanks for joining the MarketSignalPro early-access list. You're officially one of our founding users —
            which means you'll get first look at the platform, beta access opportunities, and an introductory offer
            before the public launch.
          </p>

          <div style="background:rgba(37,99,235,.08);border:1px solid rgba(96,165,250,.22);border-radius:12px;padding:18px 20px;margin:22px 0;">
            <div style="font-size:12px;font-weight:800;color:#fcd34d;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;">
              ⭐ Founding user perks
            </div>
            <ul style="margin:0;padding:0 0 0 18px;color:#cbd5e1;font-size:14px;line-height:1.8;">
              <li>Priority access when beta opens</li>
              <li>Founding-user pricing — locked in before public release</li>
              <li>Direct line to send feedback that actually shapes the product</li>
            </ul>
          </div>

          <p style="margin:18px 0 6px;font-size:14px;line-height:1.7;color:#7c8fae;">
            What's coming: composite signal categories (squeeze setups, hidden movers, sentiment flips, volume breakouts),
            score breakdowns with full BI analytics, and plain-English AI insights — built for traders who want clarity, not noise.
          </p>

          <p style="margin:22px 0 0;font-size:14px;line-height:1.7;color:#7c8fae;">
            We'll be in touch soon with launch updates. In the meantime, if you have questions or want to share what you'd like to see,
            just reply to this email or write to
            <a href="mailto:support@marketsignalpro.com" style="color:#60a5fa;text-decoration:none;">support@marketsignalpro.com</a>.
          </p>
        </div>

        <div style="padding:20px 36px 28px;border-top:1px solid rgba(255,255,255,.05);margin-top:14px;">
          <div style="font-size:12px;color:#475569;line-height:1.6;">
            — The MarketSignalPro Team<br>
            <a href="https://marketsignalpro.com" style="color:#60a5fa;text-decoration:none;">marketsignalpro.com</a>
          </div>
        </div>

      </div>

      <div style="max-width:560px;margin:14px auto 0;text-align:center;font-size:11px;color:#475569;line-height:1.6;">
        You're receiving this because you signed up for early access at marketsignalpro.com.<br>
        MarketSignalPro · AI-powered market intelligence<br>
        <a href="mailto:support@marketsignalpro.com?subject=Unsubscribe&body=Please%20remove%20me%20from%20the%20MarketSignalPro%20early-access%20list."
           style="color:#7c8fae;text-decoration:underline;">Unsubscribe</a>
      </div>
    </div>
    """

    text = (
        f"You're in, {first}.\n\n"
        "Thanks for joining the MarketSignalPro early-access list. You're officially one of our founding users.\n\n"
        "FOUNDING USER PERKS:\n"
        "  • Priority access when beta opens\n"
        "  • Founding-user pricing — locked in before public release\n"
        "  • Direct line to send feedback that shapes the product\n\n"
        "We'll be in touch with launch updates. Questions? Reply to this email or write to "
        "support@marketsignalpro.com.\n\n"
        "— The MarketSignalPro Team\n"
        "marketsignalpro.com\n\n"
        "---\n"
        "To unsubscribe, reply with 'Unsubscribe' or email support@marketsignalpro.com.\n"
    )

    payload = {
        "from": FROM_EMAIL,
        "to": [row["email"]],
        "reply_to": ADMIN_EMAIL,
        "subject": "You're on the MarketSignalPro early-access list 🎉",
        "html": html,
        "text": text,
        "headers": {
            "List-Unsubscribe": "<mailto:support@marketsignalpro.com?subject=Unsubscribe>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    }

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
            timeout=12,
        )
        if response.status_code in (200, 201):
            return True, None
        return False, f"Resend error {response.status_code}: {response.text}"
    except Exception as exc:
        return False, f"Resend request failed: {exc}"


# ============================================================
# GLOBAL CSS
# ============================================================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;700;800&display=swap');

:root {
    --bg: #05070d;
    --panel: rgba(11,18,32,.78);
    --line: rgba(255,255,255,.10);
    --text: #edf4ff;
    --muted: #7c8fae;
    --blue: #2563eb;
    --blue2: #60a5fa;
    --gold: #f59e0b;
    --green: #22c55e;
}

* { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 16% 16%, rgba(37,99,235,.18), transparent 30%),
        radial-gradient(circle at 88% 12%, rgba(245,158,11,.16), transparent 25%),
        radial-gradient(circle at 70% 86%, rgba(34,197,94,.13), transparent 28%),
        linear-gradient(180deg, #04060b 0%, #070a12 48%, #05070d 100%) !important;
    color: var(--text) !important;
    font-family: Inter, sans-serif !important;
}

[data-testid="stHeader"], #MainMenu, footer, [data-testid="stDecoration"] {
    display: none !important;
}

.block-container {
    max-width: 100% !important;
    padding: 0 !important;
}

.main .block-container {
    padding-top: 0 !important;
}

.msp-bg-grid {
    position: fixed;
    inset: 0;
    pointer-events: none;
    background-image:
        linear-gradient(rgba(255,255,255,.032) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.032) 1px, transparent 1px);
    background-size: 48px 48px;
    mask-image: radial-gradient(circle at center, black, transparent 80%);
    opacity: .42;
    z-index: 0;
}

.msp-shell {
    position: relative;
    z-index: 1;
    width: min(1120px, calc(100% - 36px));
    margin: 0 auto;
}

.msp-topbar {
    padding: 22px 0 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
}

.msp-brand {
    display: inline-flex;
    align-items: center;
    gap: 12px;
}

.msp-brand-mark {
    width: 44px;
    height: 44px;
    display: block;
    object-fit: contain;
    filter: drop-shadow(0 8px 22px rgba(37,99,235,.32));
}

/* Fallback brand mark if the PNG file is missing in the repo */
.msp-brand-mark-fallback {
    width: 44px;
    height: 44px;
    display: grid;
    place-items: center;
    border-radius: 14px;
    background: linear-gradient(135deg, rgba(37,99,235,.95), rgba(96,165,250,.35));
    box-shadow: 0 12px 38px rgba(37,99,235,.35);
    border: 1px solid rgba(255,255,255,.16);
    font-weight: 900;
    color: #fff;
    letter-spacing: -1px;
}

.msp-brand-text {
    font-weight: 900;
    letter-spacing: -.8px;
    font-size: clamp(21px, 2vw, 28px);
    white-space: nowrap;
}

.msp-brand-text span { color: var(--gold); }

.msp-top-pill {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    border: 1px solid var(--line);
    background: rgba(255,255,255,.045);
    color: #b8c8e6;
    padding: 11px 15px;
    border-radius: 999px;
    font-size: 13px;
    backdrop-filter: blur(18px);
}

.msp-pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: var(--green);
    animation: pulse 1.7s infinite;
}

@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(34,197,94,.38); }
    70% { box-shadow: 0 0 0 12px rgba(34,197,94,0); }
    100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}

.msp-hero-wrap {
    position: relative;
    z-index: 1;
    padding: 8px 0 20px;
    min-height: auto;
    display: flex;
    align-items: center;
}

.msp-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--blue2);
    font-size: 12px;
    font-weight: 900;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-bottom: 22px;
}

.msp-eyebrow-row {
    display: flex;
    justify-content: center;
    width: 100%;
    margin-bottom: 6px;
    margin-top: 8px;
}
.msp-eyebrow-row .msp-eyebrow {
    margin: 0 !important;
    max-width: none !important;
}

.msp-eyebrow::before {
    content: "";
    width: 34px;
    height: 2px;
    background: linear-gradient(90deg, var(--blue), var(--gold));
    border-radius: 999px;
}

.msp-h1 {
    margin: 0;
    font-size: clamp(44px, 5.6vw, 78px);
    line-height: .95;
    letter-spacing: -4px;
    max-width: 590px;
    font-weight: 900;
}

.msp-gradient-text {
    display: inline-block;
    background: linear-gradient(90deg, #ffffff 0%, #8db9ff 34%, #2563eb 56%, #f59e0b 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.msp-subhead {
    margin: 22px 0 0;
    max-width: 560px;
    font-size: clamp(17px, 1.65vw, 22px);
    line-height: 1.75;
    color: var(--muted);
}

.msp-benefits {
    list-style: none;
    padding: 0;
    margin: 14px 0 0;
    display: flex;
    flex-direction: column;
    gap: 9px;
}

.msp-benefits li {
    display: flex;
    align-items: baseline;
    gap: 10px;
    color: #8da3c2;
    font-size: 13.5px;
    line-height: 1.55;
}

.msp-benefits li strong {
    color: #dbeafe;
    font-weight: 700;
}

.msp-benefit-icon {
    flex: 0 0 auto;
    color: var(--blue2);
    font-size: 12px;
    font-weight: 900;
    line-height: 1;
    opacity: .85;
    transform: translateY(1px);
}

.msp-benefits-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.08), transparent);
    margin: 18px 0 16px;
}

.msp-launch-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    margin-bottom: 14px;
    color: #dbeafe;
    font-weight: 900;
    font-size: 15px;
}

.msp-early-badge {
    color: #071018;
    background: linear-gradient(90deg, var(--gold), #fde68a);
    padding: 7px 11px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 900;
    white-space: nowrap;
}

.msp-form-note {
    margin: 14px 0 4px;
    color: #536781;
    font-size: 12px;
    line-height: 1.7;
    padding-bottom: 2px;
}

.msp-proof {
    margin-top: 22px;
    display: flex;
    flex-wrap: wrap;
    gap: 13px;
}

.msp-proof span {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border: 1px solid rgba(255,255,255,.09);
    background: rgba(255,255,255,.035);
    border-radius: 999px;
    color: #a2b2ca;
    font-size: 13px;
}

.msp-ticker-tape {
    position: relative;
    z-index: 1;
    width: 100%;
    overflow: hidden;
    border-block: 1px solid rgba(255,255,255,.08);
    background: rgba(255,255,255,.025);
    margin-top: 12px;
    padding: 18px 0;
}

.msp-ticker-track {
    display: flex;
    gap: 16px;
    width: max-content;
    animation: marquee 28s linear infinite;
}

.msp-ticker-track:hover { animation-play-state: paused; }

@keyframes marquee {
    from { transform: translateX(0); }
    to { transform: translateX(-50%); }
}

.msp-ticker-chip {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-width: 170px;
    padding: 12px 14px;
    border: 1px solid rgba(255,255,255,.09);
    background: rgba(11,18,32,.8);
    border-radius: 16px;
    box-shadow: 0 12px 38px rgba(0,0,0,.25);
}

.msp-ticker-chip b {
    font-family: "JetBrains Mono", monospace;
    color: var(--text);
}

.msp-ticker-chip span {
    color: #4ade80;
    font-weight: 800;
    font-size: 13px;
}

.msp-section {
    position: relative;
    z-index: 1;
    width: min(1180px, calc(100% - 36px));
    margin: 80px auto;
}

.msp-section-feature {
    margin-top: 70px;
    margin-bottom: 70px;
}

.msp-section-head {
    max-width: 720px;
    margin: 0 auto 44px;
    text-align: center;
}

.msp-section-kicker {
    color: var(--gold);
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 3.5px;
    text-transform: uppercase;
    margin-bottom: 14px;
    opacity: .9;
}

.msp-section h3 {
    margin: 0;
    font-size: clamp(32px, 4vw, 52px);
    line-height: 1.05;
    letter-spacing: -2px;
    font-weight: 900;
}

.msp-section p {
    color: var(--muted);
    font-size: 16px;
    line-height: 1.7;
    margin: 18px auto 0;
    max-width: 620px;
}

.msp-gallery-wrap {
    margin-top: 36px;
    opacity: .92;
}

.msp-footer {
    position: relative;
    z-index: 1;
    width: min(1180px, calc(100% - 36px));
    margin: 70px auto 0;
    padding: 38px 0 44px;
    border-top: 1px solid rgba(255,255,255,.06);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 18px;
    text-align: center;
}

.msp-footer-brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: #cbd5e1;
    font-weight: 900;
    font-size: 15px;
    letter-spacing: -.3px;
}

.msp-footer-mark {
    width: 28px;
    height: 28px;
    display: grid;
    place-items: center;
    border-radius: 9px;
    background: linear-gradient(135deg, var(--blue), #1e40af);
    color: #fff;
    font-size: 13px;
    font-weight: 900;
    box-shadow: 0 4px 14px rgba(37,99,235,.35);
}

.msp-disclaimer {
    max-width: 720px;
    margin: 0 auto;
    color: #5f7491;
    font-size: 11.5px;
    line-height: 1.7;
    letter-spacing: .1px;
}

.msp-footer-meta {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: #475569;
    font-size: 11.5px;
    flex-wrap: wrap;
    justify-content: center;
}

.msp-footer-dot {
    color: #334155;
}

.msp-footer a {
    color: #7c8fae;
    text-decoration: none;
    transition: color .2s ease;
}

.msp-footer a:hover {
    color: var(--blue2);
}

/* Narrative story flow — three steps that read as one connected idea */
.msp-story {
    display: grid;
    grid-template-columns: 1fr auto 1fr auto 1fr;
    align-items: start;
    gap: 14px;
    margin: 0 auto;
    max-width: 980px;
    padding: 12px 0 4px;
}

.msp-story-step {
    position: relative;
    padding: 8px 12px 0;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 320px;
    margin: 0 auto;
}

.msp-story-num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 16px;
    font-weight: 800;
    color: #5f7491;
    letter-spacing: 5px;
    /* letter-spacing adds an equal gap AFTER the last glyph too, which the
       centering algorithm counts — pushing the visible digits ~2.5px left of
       true center. A matching text-indent re-centers the visible glyphs. */
    text-indent: 5px;
    margin: 0 auto 18px;
    opacity: .95;
    text-align: center;
}

.msp-story-icon {
    font-size: 48px;
    margin: 0 auto 18px;
    line-height: 1;
    filter: drop-shadow(0 4px 20px rgba(96,165,250,.28));
    text-align: center;
    width: 60px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.msp-story-step h4 {
    margin: 0 auto 14px;
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 0;
    color: #edf4ff;
    text-align: center;
    width: 100%;
}

.msp-story-step p {
    margin: 0;
    color: #7c8fae;
    font-size: 15px;
    line-height: 1.7;
    max-width: 340px;
}

.msp-story-step p em {
    color: #93b4fd;
    font-style: italic;
    font-weight: 600;
}

.msp-story-arrow {
    display: grid;
    place-items: center;
    color: #334155;
    font-size: 32px;
    font-weight: 200;
    padding-top: 76px;
    user-select: none;
}

@media (max-width: 880px) {
    .msp-story {
        grid-template-columns: 1fr;
        gap: 14px;
        max-width: 520px;
    }
    /* Hide arrows on mobile — vertically stacked cards already read as a sequence */
    .msp-story-arrow {
        display: none;
    }
}

/* Streamlit form card styling */
[data-testid="stForm"] {
    border: 1px solid var(--line) !important;
    padding: 22px 22px 26px !important;
    background: linear-gradient(180deg, rgba(13,21,37,.78), rgba(8,12,22,.65)) !important;
    border-radius: 22px !important;
    box-shadow: 0 30px 100px rgba(0,0,0,.55) !important;
    backdrop-filter: blur(18px) !important;
    max-width: 520px !important;
    margin-top: 22px !important;
}

[data-testid="stTextInput"] label {
    display: none !important;
}

/* ============================================================
   HONEYPOT FIELD — invisible to humans, irresistible to bots.
   We position offscreen rather than display:none because some
   smart bots skip display:none fields. Real users can't focus,
   tab to, or see it. Bots that auto-fill every input will fill it
   and get silently filtered out in the submit handler.
   ============================================================ */
[data-testid="stTextInput"]:has(input[aria-label="Company website"]) {
    position: absolute !important;
    left: -10000px !important;
    top: auto !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
    margin: 0 !important;
}

/* Hide Streamlit's "Press Enter to submit form" hint under inputs */
[data-testid="InputInstructions"],
[data-testid="stWidgetInstructions"],
[data-testid="stFormSubmitButton"] ~ [data-testid="InputInstructions"],
.stTextInput div[data-baseweb="form-control-caption"],
div[data-testid="stForm"] small {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
}

[data-testid="stTextInput"] {
    margin-bottom: 10px !important;
    width: 100% !important;
}

[data-testid="stTextInput"] > div,
[data-testid="stTextInput"] > div > div {
    width: 100% !important;
    min-height: 52px !important;
}

[data-testid="stTextInput"] [data-baseweb="input"] {
    min-height: 52px !important;
    background: transparent !important;
    border-radius: 13px !important;
}

[data-testid="stTextInput"] [data-baseweb="base-input"] {
    background: transparent !important;
    border-radius: 13px !important;
    overflow: visible !important;
}

[data-testid="stTextInput"] input {
    height: 52px !important;
    min-height: 52px !important;
    width: 100% !important;
    max-width: 100% !important;
    border: 1px solid rgba(255,255,255,.18) !important;
    background: rgba(255,255,255,.075) !important;
    color: #edf4ff !important;
    border-radius: 13px !important;
    font-size: 14px !important;
    line-height: 1.4 !important;
    padding: 14px 16px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.08) !important;
    box-sizing: border-box !important;
}

[data-testid="stTextInput"] input::placeholder {
    color: rgba(237,244,255,.42) !important;
    opacity: 1 !important;
}

[data-testid="stTextInput"] input:focus {
    border-color: rgba(96,165,250,.9) !important;
    box-shadow: 0 0 0 4px rgba(37,99,235,.16) !important;
}

[data-testid="stFormSubmitButton"] {
    margin-top: 8px !important;
}

[data-testid="stFormSubmitButton"] button,
.stButton button {
    height: 48px !important;
    min-height: 48px !important;
    border: 0 !important;
    border-radius: 14px !important;
    padding: 0 18px !important;
    font-weight: 900 !important;
    color: #fff !important;
    cursor: pointer !important;
    background: linear-gradient(135deg, #2563eb, #1d4ed8 55%, #f59e0b 160%) !important;
    box-shadow: 0 18px 40px rgba(37,99,235,.32) !important;
    transition: transform .18s ease, box-shadow .18s ease, filter .18s ease !important;
    white-space: nowrap !important;
    width: 100% !important;
}

[data-testid="stFormSubmitButton"] button:hover,
.stButton button:hover {
    transform: translateY(-2px) !important;
    filter: brightness(1.08) !important;
    box-shadow: 0 24px 56px rgba(37,99,235,.43) !important;
}

/* ============================================================
   LOADING STATE — visual feedback during signup submission.
   The button shows a "submitted" look while Streamlit runs the
   script (Resend calls + Google Sheets webhook take 2-4 seconds).
   ============================================================ */
[data-testid="stFormSubmitButton"] button:active,
[data-testid="stFormSubmitButton"] button:disabled {
    transform: scale(0.98) !important;
    filter: brightness(0.85) !important;
    cursor: wait !important;
    box-shadow: 0 8px 24px rgba(37,99,235,.18) !important;
}

/* Theme Streamlit's inline spinner to match the dark fintech palette */
[data-testid="stSpinner"] {
    background: linear-gradient(180deg, rgba(37,99,235,.10), rgba(13,21,37,.65)) !important;
    border: 1px solid rgba(96,165,250,.28) !important;
    border-radius: 14px !important;
    padding: 14px 18px !important;
    margin-top: 12px !important;
    box-shadow: 0 8px 24px rgba(0,0,0,.25) !important;
    color: #dbeafe !important;
    font-weight: 700 !important;
}

[data-testid="stSpinner"] > div {
    color: #dbeafe !important;
    font-size: 14px !important;
    letter-spacing: .2px !important;
}

/* The actual spinning ring — recolor from Streamlit's default red to brand blue */
[data-testid="stSpinner"] i,
[data-testid="stSpinner"] svg,
[data-testid="stSpinner"] [role="img"] {
    color: var(--blue2) !important;
    fill: var(--blue2) !important;
    border-top-color: var(--blue2) !important;
}

[data-testid="stSpinner"] [role="progressbar"],
[data-testid="stSpinner"] div[class*="StyledSpinner"] {
    border-top-color: var(--blue2) !important;
    border-right-color: rgba(96,165,250,.18) !important;
    border-bottom-color: rgba(96,165,250,.18) !important;
    border-left-color: rgba(96,165,250,.18) !important;
}

@media (max-width: 980px) {
    .msp-hero-wrap {
        min-height: auto;
        padding-bottom: 40px;
    }

    /* Keep the early-access pill on mobile but shrink it */
    .msp-top-pill {
        padding: 7px 11px !important;
        font-size: 11px !important;
        gap: 6px !important;
    }
    .msp-top-pill .msp-pulse-dot {
        width: 6px !important;
        height: 6px !important;
    }

    /* Tighter topbar padding so it doesn't take so much vertical room */
    .msp-topbar {
        padding: 16px 0 8px !important;
        gap: 12px !important;
    }
}

@media (max-width: 820px) {
    .msp-shell,
    .msp-section,
    .msp-footer {
        width: calc(100% - 44px) !important;
    }
}

@media (max-width: 620px) {
    /* ── Container widths — more breathing room from edges ── */
    .msp-shell,
    .msp-section,
    .msp-footer {
        width: calc(100% - 40px) !important;
    }

    /* ── Hero typography ────────────────────────────────── */
    .msp-h1 {
        font-size: clamp(32px, 8.5vw, 42px) !important;
        letter-spacing: -1.4px !important;
        line-height: 1.04 !important;
        text-align: center !important;
    }

    .msp-subhead {
        font-size: 15px !important;
        line-height: 1.6 !important;
        margin-top: 14px !important;
        text-align: center !important;
    }

    /* CENTER everything on mobile — override the desktop right-align rule.
       Use higher specificity (section.main) to win against any desktop
       rules with :has() or chained selectors. */
    section.main .msp-eyebrow,
    section.main .msp-h1,
    section.main .msp-subhead,
    section.main .msp-proof,
    .msp-eyebrow,
    .msp-h1,
    .msp-subhead,
    .msp-proof {
        max-width: 100% !important;
        width: 100% !important;
        margin-left: auto !important;
        margin-right: auto !important;
        text-align: center !important;
    }

    .msp-eyebrow {
        font-size: 11px !important;
        letter-spacing: 2.5px !important;
        margin-bottom: 14px !important;
        justify-content: center !important;
    }

    .msp-eyebrow-row {
        justify-content: center !important;
    }

    .msp-proof {
        justify-content: center !important;
    }

    /* Collapse the right column on mobile — its preview iframe is
       no longer rendered for mobile users (server-side detection), so
       the column has no content and shouldn't take space. */
    [data-testid="stHorizontalBlock"]:has(.msp-eyebrow) > [data-testid="column"]:last-of-type {
        display: none !important;
    }

    /* Hero columns stack vertically (natural Streamlit behavior on mobile).
       Left column already contains [headline, subhead, mobile preview, form,
       proof] in DOM order — exactly what we want. */
    [data-testid="stHorizontalBlock"]:has(.msp-eyebrow) {
        gap: 4px !important;
    }

    /* Center the live-preview iframe within the left column on mobile.
       Streamlit's iframe container doesn't auto-center its child iframe —
       we have to do it explicitly. */
    [data-testid="stHorizontalBlock"]:has(.msp-eyebrow) iframe {
        display: block !important;
        margin-left: auto !important;
        margin-right: auto !important;
        max-width: 100% !important;
    }
    [data-testid="stHorizontalBlock"]:has(.msp-eyebrow) [data-testid="stIFrame"],
    [data-testid="stHorizontalBlock"]:has(.msp-eyebrow) [data-testid="element-container"]:has(iframe) {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    /* Also override the desktop "preview iframe sits left of gutter" rule */
    section.main iframe[title="streamlit_app"],
    section.main iframe[srcdoc*="dashboard"] {
        margin-left: auto !important;
        margin-right: auto !important;
    }

    /* Kill bottom dead space before the ticker tape */
    .msp-ticker-tape {
        margin-top: 4px !important;
        padding: 12px 0 !important;
    }

    /* ── Form card — centered on mobile (specificity bumped to override
       desktop `:has(.msp-launch-title)` rule that pulls form right-aligned) ── */
    [data-testid="stForm"]:has(.msp-launch-title),
    [data-testid="stForm"] {
        padding: 18px 16px 22px !important;
        border-radius: 18px !important;
        max-width: 100% !important;
        width: 100% !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    .msp-launch-title {
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 10px !important;
        font-size: 13px !important;
        flex-wrap: wrap;
    }

    .msp-early-badge {
        font-size: 10px !important;
        padding: 4px 9px !important;
    }

    .msp-benefits {
        margin-top: 12px !important;
    }

    .msp-benefits li {
        font-size: 13px !important;
        line-height: 1.5 !important;
    }

    /* iOS Safari zoom prevention — input font must be ≥16px */
    [data-testid="stTextInput"] input {
        font-size: 16px !important;
        height: 48px !important;
        min-height: 48px !important;
    }

    [data-testid="stFormSubmitButton"] button {
        font-size: 15px !important;
        height: 50px !important;
        min-height: 50px !important;
    }

    .msp-form-note {
        font-size: 11.5px !important;
        text-align: center;
    }

    /* ── Section spacing — much tighter, kills dead space ── */
    .msp-section {
        margin: 36px auto !important;
    }

    .msp-section-feature {
        margin-top: 28px !important;
        margin-bottom: 28px !important;
    }

    .msp-section-head {
        margin-bottom: 24px !important;
    }

    .msp-section h3 {
        font-size: clamp(24px, 6.5vw, 30px) !important;
        letter-spacing: -1px !important;
    }

    .msp-section p {
        font-size: 14px !important;
        line-height: 1.6 !important;
    }

    .msp-section-kicker {
        font-size: 10px !important;
        letter-spacing: 2.5px !important;
        margin-bottom: 8px !important;
    }

    /* ── Hero wrap — kill bottom dead space ────────────── */
    .msp-hero-wrap {
        padding-bottom: 16px !important;
        min-height: auto !important;
    }

    /* ── Ticker tape ────────────────────────────────────── */
    .msp-ticker-chip {
        min-width: 134px;
        padding: 8px 10px;
        font-size: 11.5px;
    }

    /* ── Footer ─────────────────────────────────────────── */
    .msp-footer {
        margin-top: 36px !important;
        padding: 26px 0 32px !important;
        gap: 12px !important;
    }

    .msp-disclaimer {
        font-size: 11px !important;
        line-height: 1.6 !important;
    }

    .msp-footer-meta {
        font-size: 11px !important;
        flex-direction: column;
        gap: 4px !important;
    }

    .msp-footer-dot {
        display: none;
    }

    /* ── Story section: vertical cards, centered ───────── */
    .msp-story {
        gap: 12px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        width: 100% !important;
    }

    .msp-story-step {
        padding: 22px 24px !important;
        background: rgba(13,21,37,.4);
        border: 1px solid rgba(255,255,255,.06);
        border-radius: 16px;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
    }

    /* Numbers + icons fill full card width so text-align actually does
       its job (otherwise content-width blocks center via margin:auto,
       which gets thrown off by negative letter-spacing) */
    .msp-story-num,
    .msp-story-icon,
    .msp-story-step h4 {
        text-align: center !important;
        width: 100% !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
        display: block !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }

    .msp-story-num {
        font-size: 11px !important;
        letter-spacing: 3px !important;
        text-indent: 3px !important;
        margin-bottom: 6px !important;
    }

    .msp-story-icon {
        font-size: 30px !important;
        margin-bottom: 8px !important;
    }

    .msp-story-step h4 {
        font-size: 20px !important;
        margin-bottom: 8px !important;
        /* Zero letter-spacing on mobile — any non-zero value adds a trailing
           gap that nudges the centered glyphs off the column center. */
        letter-spacing: 0 !important;
    }

    /* Description: constrained width with auto margins for breathing room */
    .msp-story-step p {
        text-align: center !important;
        font-size: 13.5px !important;
        max-width: 320px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        line-height: 1.55 !important;
    }

    /* ── Top pill — even smaller ────────────────────────── */
    .msp-top-pill {
        padding: 5px 9px !important;
        font-size: 10px !important;
        gap: 5px !important;
        letter-spacing: .1px !important;
    }
    .msp-top-pill .msp-pulse-dot {
        width: 5px !important;
        height: 5px !important;
    }
}

/* ── Extra-narrow phones (iPhone SE, older Android) ───── */
@media (max-width: 380px) {
    .msp-shell,
    .msp-section,
    .msp-footer {
        width: calc(100% - 24px) !important;
    }

    .msp-h1 {
        font-size: 32px !important;
        letter-spacing: -1.4px !important;
    }

    .msp-section h3 {
        font-size: 24px !important;
    }

    [data-testid="stForm"] {
        padding: 16px 14px 20px !important;
    }

    .msp-brand-text {
        font-size: 18px !important;
    }

    /* Hide the pill on the tiniest screens — it crowds the topbar */
    .msp-top-pill {
        display: none !important;
    }
}

/* ============================================================
   HERO LAYOUT — center the form & preview without relying on :has()
   or Streamlit's internal column DOM structure. Each hero element
   is targeted by its OWN class (.msp-eyebrow, .msp-h1, .msp-subhead,
   etc.) so the rule cannot be invalidated by Streamlit version
   changes. Forces max-width on the wrapping horizontal block too.
   ============================================================ */

/* The first horizontal block on the page IS the hero (after topbar) */
section.main div.stHorizontalBlock,
section.main [data-testid="stHorizontalBlock"] {
    align-items: center;
}

/* Constrain the hero block specifically (it contains .msp-eyebrow) */
section.main [data-testid="stHorizontalBlock"]:has(.msp-eyebrow),
section.main div.stHorizontalBlock:has(.msp-eyebrow) {
    max-width: 980px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    gap: 1rem !important;
}

/* PRIMARY FIX: target hero elements directly by their class.
   These rules work no matter what DOM Streamlit wraps them in. */
.msp-eyebrow,
.msp-h1,
.msp-subhead,
.msp-proof {
    max-width: 520px !important;
    margin-left: auto !important;
    margin-right: 0 !important;
}

/* Right-align the form to the column gutter */
[data-testid="stForm"]:has(.msp-launch-title) {
    max-width: 520px !important;
    margin-left: auto !important;
    margin-right: 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}

/* Fallback for browsers without :has() — target the first form */
section.main > div > div > div > [data-testid="stForm"]:first-of-type {
    max-width: 520px !important;
    margin-left: auto !important;
    margin-right: 0 !important;
}

/* Reset the First/Last name columns inside the form */
[data-testid="stForm"] [data-testid="stHorizontalBlock"] {
    max-width: none !important;
    margin: 0 !important;
}
[data-testid="stForm"] [data-testid="stHorizontalBlock"] [data-testid="column"] {
    padding: 0 !important;
}
[data-testid="stForm"] [data-testid="stVerticalBlock"] {
    max-width: none !important;
    margin: 0 !important;
}

/* Left-align the preview iframe to the gutter on its side (DESKTOP ONLY) */
@media (min-width: 621px) {
    section.main iframe[title="streamlit_app"],
    section.main iframe[srcdoc*="dashboard"] {
        margin-left: 0 !important;
    }
}

@media (max-width: 980px) {
    section.main [data-testid="stHorizontalBlock"]:has(.msp-eyebrow),
    section.main div.stHorizontalBlock:has(.msp-eyebrow) {
        max-width: 100% !important;
        gap: 1rem !important;
    }
    /* On mobile, reset max-width so elements can fill the column, but
       leave margin-left/right to be controlled by the more-specific
       mobile centering rules in the 620px breakpoint above. */
    .msp-eyebrow,
    .msp-h1,
    .msp-subhead,
    .msp-proof,
    [data-testid="stForm"]:has(.msp-launch-title),
    section.main > div > div > div > [data-testid="stForm"]:first-of-type {
        max-width: 100% !important;
    }
}

</style>
<div class="msp-bg-grid"></div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# TOPBAR
# ============================================================
def _load_logo_data_uri() -> str:
    """Read favicon-128.png from the repo and return a data URI, or empty on failure."""
    try:
        import base64 as _b64
        for candidate in ("favicon-128.png", "favicon-64.png", "favicon-32.png"):
            if os.path.exists(candidate):
                with open(candidate, "rb") as fh:
                    return "data:image/png;base64," + _b64.b64encode(fh.read()).decode("ascii")
    except Exception:
        pass
    return ""

_logo_uri = _load_logo_data_uri()
_brand_mark_html = (
    f'<img src="{_logo_uri}" alt="MarketSignalPro" class="msp-brand-mark">'
    if _logo_uri
    else '<span class="msp-brand-mark-fallback">M</span>'
)

st.markdown(
    f"""
<div class="msp-shell">
<header class="msp-topbar">
<div class="msp-brand">
{_brand_mark_html}
<span class="msp-brand-text">Market<span>Signal</span>Pro</span>
</div>
<div class="msp-top-pill"><span class="msp-pulse-dot"></span> Private early-access list now open</div>
</header>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HERO
# ============================================================
st.markdown('<div class="msp-shell"><div class="msp-hero-wrap">', unsafe_allow_html=True)

# Eyebrow lives above the columns and is centered across the full page width
st.markdown(
    '<div class="msp-eyebrow-row"><div class="msp-eyebrow">AI Market Intelligence</div></div>',
    unsafe_allow_html=True,
)


# Preview HTML is defined here so both desktop (right column)
# and mobile (left column, inline below headline) renders can use it.
preview_html = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;700;800;900&family=JetBrains+Mono:wght@500;700;800&display=swap');
*{box-sizing:border-box}
body{margin:0;background:transparent;color:#edf4ff;font-family:Inter,sans-serif;overflow:hidden}
.visual{position:relative;min-height:755px;display:grid;align-items:center;justify-items:start;perspective:1200px;padding:20px 0 30px 0}
.orbit{position:absolute;width:520px;height:520px;border:1px solid rgba(96,165,250,.15);border-radius:999px;animation:spin 18s linear infinite;opacity:.85}
.orbit.two{width:660px;height:340px;transform:rotateX(67deg) rotateZ(18deg);border-color:rgba(245,158,11,.16);animation-duration:24s;animation-direction:reverse}
@keyframes spin{to{rotate:360deg}}
.dashboard{position:relative;width:min(100%,500px);border:1px solid rgba(255,255,255,.13);background:linear-gradient(180deg,rgba(13,21,37,.92),rgba(6,10,19,.88)),radial-gradient(circle at 80% 10%,rgba(37,99,235,.2),transparent 35%);border-radius:28px;box-shadow:0 40px 120px rgba(0,0,0,.65),0 0 80px rgba(37,99,235,.16);overflow:hidden;transform:rotateY(-5deg) rotateX(3deg)}
.dash-top{height:58px;display:flex;align-items:center;justify-content:space-between;padding:0 18px;background:rgba(255,255,255,.035);border-bottom:1px solid rgba(255,255,255,.08)}
.traffic{display:flex;gap:7px}.traffic i{width:10px;height:10px;border-radius:999px;display:block}.traffic i:nth-child(1){background:#ef4444}.traffic i:nth-child(2){background:#f59e0b}.traffic i:nth-child(3){background:#22c55e}
.label{font-family:JetBrains Mono,monospace;color:#5f7491;font-size:11px;letter-spacing:.3px}.body{padding:20px}
.tabs{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px;color:#7890b4;font-size:11px;font-weight:800}.tabs span{padding:6px 9px;border-radius:999px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07)}.tabs .active{color:#fff;background:rgba(37,99,235,.22);border-color:rgba(96,165,250,.35)}
.title{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:18px}.title h2{margin:0;font-size:28px;line-height:1;letter-spacing:-1px;font-weight:900}.title h2 span{color:#60a5fa}
.score{width:76px;height:76px;display:grid;place-items:center;border-radius:24px;background:linear-gradient(135deg,rgba(34,197,94,.18),rgba(37,99,235,.16));border:1px solid rgba(34,197,94,.25);color:#86efac;font-size:26px;font-weight:900;font-family:JetBrains Mono,monospace}
.stock-row{display:grid;grid-template-columns:68px 1fr auto;gap:12px;align-items:center;padding:14px;border:1px solid rgba(255,255,255,.07);background:rgba(2,6,23,.58);border-radius:16px;margin:10px 0}
.ticker{font-family:JetBrains Mono,monospace;color:#60a5fa;font-weight:900;font-size:17px}.bar{height:9px;border-radius:999px;background:rgba(255,255,255,.07);overflow:hidden}.bar span{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#2563eb,#22c55e);animation:grow 1.8s ease both}
@keyframes grow{from{width:0}}.tag{padding:5px 9px;border-radius:999px;color:#071018;background:#86efac;font-size:10px;font-weight:900;white-space:nowrap}
.mini-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}.mini-grid div{padding:12px;border-radius:14px;background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.08)}.mini-grid b{display:block;color:#f59e0b;font-size:18px}.mini-grid span{display:block;color:#7c8fae;font-size:10px;margin-top:2px}
.insight{margin-top:12px;padding:14px;border-radius:20px;background:linear-gradient(135deg,rgba(37,99,235,.12),rgba(245,158,11,.08));border:1px solid rgba(255,255,255,.1)}.insight strong{color:#fff;display:block;margin-bottom:8px}.insight p{margin:0;color:#91a3be;line-height:1.45;font-size:12px}

/* Auto-cycling panel system */
.tabs span{cursor:default;transition:all .35s ease}
.panel-stack{position:relative;min-height:445px}
.panel{position:absolute;inset:0;opacity:0;visibility:hidden;transform:translateY(8px);transition:opacity .55s ease,transform .55s ease,visibility .55s ease}
.panel.active{opacity:1;visibility:visible;transform:translateY(0)}

/* Signal Categories panel */
.cat-row{padding:10px 12px;border:1px solid rgba(255,255,255,.07);background:rgba(2,6,23,.58);border-radius:14px;margin-bottom:8px;border-left:3px solid}
.cat-row.green{border-left-color:#22c55e}
.cat-row.orange{border-left-color:#f59e0b}
.cat-row.yellow{border-left-color:#fbbf24}
.cat-row.pink{border-left-color:#ec4899}
.cat-row.blue{border-left-color:#60a5fa}
.cat-head{display:flex;align-items:center;gap:8px;margin-bottom:4px}
.cat-icon{font-size:14px}
.cat-title{color:#edf4ff;font-weight:900;font-size:13px;flex:1;letter-spacing:-.2px}
.cat-badge{font-size:9px;font-weight:900;padding:3px 7px;border-radius:6px;letter-spacing:.4px}
.cat-badge.pro{background:rgba(245,158,11,.16);color:#fcd34d;border:1px solid rgba(245,158,11,.35)}
.cat-badge.free{background:rgba(34,197,94,.16);color:#86efac;border:1px solid rgba(34,197,94,.35)}
.cat-desc{font-size:10.5px;color:#7c8fae;line-height:1.4}

/* Smart Insights panel — tickers colored by status */
.si-row{display:grid;grid-template-columns:62px 1fr 70px;gap:10px;align-items:center;padding:11px 12px;border:1px solid rgba(255,255,255,.07);background:rgba(2,6,23,.58);border-radius:14px;margin-bottom:9px;border-left:3px solid}
.si-row.buy{border-left-color:#22c55e}.si-row.watch{border-left-color:#f59e0b}.si-row.avoid{border-left-color:#ef4444}
.si-tk{font-family:JetBrains Mono,monospace;font-weight:900;font-size:14px;letter-spacing:.2px}
.si-tk-buy{color:#86efac}
.si-tk-watch{color:#fcd34d}
.si-tk-avoid{color:#fca5a5}
.si-txt{font-size:11px;color:#91a3be;line-height:1.45}
.si-txt strong{color:#edf4ff;font-weight:800}
.si-txt em{font-style:italic}
.si-tag{padding:4px 0;border-radius:999px;font-size:10px;font-weight:900;text-align:center;letter-spacing:.3px}
.si-tag.buy{background:#86efac;color:#071018}
.si-tag.watch{background:#fcd34d;color:#1a0f00}
.si-tag.avoid{background:#fca5a5;color:#1a0707}
@media(max-width:980px){.dashboard{transform:none;width:min(100%,420px)}.visual{min-height:620px;padding:14px 0 24px 0;justify-items:center}.orbit{width:340px;height:340px}.orbit.two{width:400px;height:220px}}
@media(max-width:520px){.dashboard{width:100%;max-width:360px}.visual{min-height:620px;padding:8px 0 16px;justify-items:center}.orbit{width:280px;height:280px;opacity:.55}.orbit.two{width:320px;height:180px;opacity:.4}.body{padding:14px}.title{margin-bottom:14px}.title h2{font-size:19px;line-height:1.1}.title span{font-size:18px}.score{width:54px;height:54px;font-size:20px;border-radius:16px}.tabs{gap:6px;margin-bottom:8px}.tabs span{padding:6px 10px;font-size:11px}.stock-row{grid-template-columns:50px 1fr auto;padding:9px 10px;gap:8px}.ticker{font-size:13px}.bar{height:7px}.tag{padding:4px 9px;font-size:9px}.mini-grid{gap:7px;margin-top:10px}.mini-grid div{padding:9px 10px}.mini-grid b{font-size:15px}.mini-grid span{font-size:9px}.insight{padding:11px 13px;margin-top:10px;border-radius:14px}.insight strong{font-size:12px;margin-bottom:5px}.insight p{font-size:11px;line-height:1.4}.panel-stack{min-height:460px}.cat-row{padding:9px 11px;margin-bottom:6px}.cat-title{font-size:12px}.cat-desc{font-size:10px}.si-row{grid-template-columns:54px 1fr 58px;padding:9px 10px;gap:8px}.si-tk{font-size:13px}.si-txt{font-size:10.5px}.si-tag{font-size:9px}}
</style>
</head>
<body>
<div class="visual">
  <div class="orbit"></div>
  <div class="orbit two"></div>
  <div class="dashboard">
    <div class="dash-top">
      <div class="traffic"><i></i><i></i><i></i></div>
      <div class="label">MARKETSIGNALPRO / LIVE PREVIEW</div>
    </div>
    <div class="body">
      <div class="tabs">
        <span class="tab active" data-tab="0">📊 Market Overview</span>
        <span class="tab" data-tab="1">⭐ Signal Categories</span>
        <span class="tab" data-tab="2">🧠 Smart Insights</span>
      </div>
      <div class="title">
        <h2>MarketSignalPro<br><span>Discovery Dashboard</span></h2>
        <div class="score">92</div>
      </div>

      <div class="panel-stack">

        <!-- Panel 0: Market Overview -->
        <div class="panel active" data-panel="0">
          <div class="stock-row"><div class="ticker">NVDA</div><div class="bar"><span style="width:92%"></span></div><div class="tag">Strong Buy</div></div>
          <div class="stock-row"><div class="ticker">TSLA</div><div class="bar"><span style="width:78%"></span></div><div class="tag">Squeeze Watch</div></div>
          <div class="stock-row"><div class="ticker">AMD</div><div class="bar"><span style="width:68%"></span></div><div class="tag">Momentum</div></div>
          <div class="mini-grid">
            <div><b>17</b><span>Signal categories</span></div>
            <div><b>5,000+</b><span>US stocks tracked</span></div>
            <div><b>AI</b><span>Plain-English insights</span></div>
          </div>
          <div class="insight"><strong>Example insight</strong><p>NVDA is showing strong trend, momentum, and sentiment confirmation. MarketSignalPro turns the signal stack into simple, readable context.</p></div>
        </div>

        <!-- Panel 1: Proprietary Signal Categories -->
        <div class="panel" data-panel="1">
          <div class="cat-row green">
            <div class="cat-head"><span class="cat-icon">💡</span><span class="cat-title">Hidden Movers</span><span class="cat-badge free">FREE</span></div>
            <div class="cat-desc">Strong technical scores with low social noise — find them before the crowd arrives.</div>
          </div>
          <div class="cat-row orange">
            <div class="cat-head"><span class="cat-icon">🔥</span><span class="cat-title">Squeeze + Buzz</span><span class="cat-badge pro">★ PRO</span></div>
            <div class="cat-desc">High short-float stocks trending on social — squeeze fuel meets momentum.</div>
          </div>
          <div class="cat-row yellow">
            <div class="cat-head"><span class="cat-icon">⚡</span><span class="cat-title">Volume Breakout</span><span class="cat-badge pro">★ PRO</span></div>
            <div class="cat-desc">Breaking above moving averages on unusually high volume — institutional confirmation.</div>
          </div>
          <div class="cat-row pink">
            <div class="cat-head"><span class="cat-icon">🎯</span><span class="cat-title">Triple Lock</span><span class="cat-badge pro">★ PRO</span></div>
            <div class="cat-desc">RSI + MACD + 50d trend + volume all simultaneously bullish — maximum conviction setup.</div>
          </div>
          <div class="insight"><strong>17 proprietary categories</strong><p>Each blends RSI, MACD, volume, short interest & social sentiment so you can scan a curated list instead of the whole market.</p></div>
        </div>

        <!-- Panel 2: Smart Insights — Plain Language -->
        <div class="panel" data-panel="2">
          <div class="si-row buy">
            <div class="si-tk si-tk-buy">TSLA</div>
            <div class="si-txt"><strong>The Moving Average</strong> is breaking out above an important price range, which can sometimes lead to further upside.</div>
            <div class="si-tag buy">● BUY</div>
          </div>
          <div class="si-row watch">
            <div class="si-tk si-tk-watch">PLUG</div>
            <div class="si-txt">There are a lot of <strong>traders</strong> betting against this stock, and <strong>momentum is building</strong>.</div>
            <div class="si-tag watch">● WATCH</div>
          </div>
          <div class="si-row avoid">
            <div class="si-tk si-tk-avoid">AAPL</div>
            <div class="si-txt">The stock <strong>may have risen too quickly</strong> and could be due for <em><strong>a pullback</strong></em>.</div>
            <div class="si-tag avoid">● AVOID</div>
          </div>
          <div class="mini-grid" style="margin-top:14px">
            <div><b>AI</b><span>Plain English</span></div>
            <div><b>17</b><span>Signal types</span></div>
            <div><b>Live</b><span>Updated daily</span></div>
          </div>
          <div class="insight"><strong>Plain-English clarity</strong><p>Every signal gets translated into one clear sentence so you understand what the chart, momentum, and sentiment are actually saying.</p></div>
        </div>

      </div>
    </div>
  </div>
</div>
<script>
(function(){
  var tabs = document.querySelectorAll('.tab');
  var panels = document.querySelectorAll('.panel');
  var i = 0;
  function activate(idx){
    tabs.forEach(function(t){ t.classList.toggle('active', t.dataset.tab == idx); });
    panels.forEach(function(p){
      var on = p.dataset.panel == idx;
      p.classList.toggle('active', on);
      if (on) {
        // Re-trigger bar grow animations when a panel becomes visible
        p.querySelectorAll('.bar span').forEach(function(b){
          var w = b.style.width;
          b.style.animation = 'none';
          b.offsetWidth; // force reflow
          b.style.animation = '';
          b.style.width = w;
        });
      }
    });
  }
  setInterval(function(){
    i = (i + 1) % panels.length;
    activate(i);
  }, 5000);
})();
</script>
</body>
</html>
"""

left, right = st.columns([0.5, 0.5], gap="large", vertical_alignment="center")

with left:
    st.markdown(
        """
<h1 class="msp-h1">AI-powered stock signals <span class="msp-gradient-text">made simple.</span></h1>
<p class="msp-subhead">
MarketSignalPro is building a cleaner way to spot momentum, squeeze candidates,
sentiment shifts, and market opportunities before they get crowded.
</p>
""",
        unsafe_allow_html=True,
    )

    # Render live preview INLINE for mobile users (between headline+subhead and form).
    # Desktop users get it in the right column instead (see `with right:` below).
    _is_mobile = is_mobile_request()
    if _is_mobile:
        components.html(preview_html, height=720, scrolling=False)

    # Record when the form was first rendered (used for bot timing check)
    if "msp_form_loaded_at" not in st.session_state:
        st.session_state.msp_form_loaded_at = time.time()

    with st.form("early_access_form", clear_on_submit=True):
        st.markdown(
            """
<div class="msp-launch-title">
<span>Join the early-access list</span>
<span class="msp-early-badge">Founding users get priority</span>
</div>
<ul class="msp-benefits">
<li><span class="msp-benefit-icon">✓</span><span><strong>Founding-user pricing</strong> — locked in before public launch.</span></li>
<li><span class="msp-benefit-icon">✓</span><span><strong>Priority beta access</strong> — be first in line when the platform opens.</span></li>
<li><span class="msp-benefit-icon">✓</span><span><strong>Direct line to the team</strong> — your feedback shapes the product.</span></li>
</ul>
<div class="msp-benefits-divider"></div>
""",
            unsafe_allow_html=True,
        )

        # Honeypot — invisible to humans (CSS-hidden offscreen), tempting to bots.
        # Real users will never see or fill this; if it has any value, the submitter is a bot.
        honeypot = st.text_input(
            "Company website",
            placeholder="Leave this empty",
            label_visibility="collapsed",
            key="msp_honeypot_company_website",
        )

        email = st.text_input("Email", placeholder="Enter your email address", label_visibility="collapsed")
        submitted = st.form_submit_button("Reserve My Spot →", use_container_width=True)

        st.markdown(
            """
<p class="msp-form-note">
We only use your email to send launch updates and founding-user offers. No spam — unsubscribe anytime.
</p>
""",
            unsafe_allow_html=True,
        )

        if submitted:
            # ── ANTI-SPAM GATES ──
            client_ip = get_client_ip()
            elapsed = time.time() - st.session_state.msp_form_loaded_at

            # 1) Honeypot tripped → silently pretend success so bots don't iterate
            if honeypot and honeypot.strip():
                st.success("You're on the early-access list. Check your inbox for a confirmation.")
                st.session_state.msp_form_loaded_at = time.time()
                st.stop()

            # 2) Submitted suspiciously fast (humans take >2s to read & type)
            if elapsed < MIN_SUBMIT_SECONDS:
                st.success("You're on the early-access list. Check your inbox for a confirmation.")
                st.session_state.msp_form_loaded_at = time.time()
                st.stop()

            # 3) Per-IP rate limit (blocks list-bombing & flood attempts)
            if is_rate_limited(client_ip):
                st.warning("We've received a lot of signups from your location. Please try again in a little while.")
                st.stop()

            # ── ACTUAL SIGNUP ──
            with st.spinner("Reserving your spot…"):
                ok, result = save_signup("", "", email)

                if ok:
                    record_signup_attempt(client_ip)

                    # Backup to Google Sheets (silent if not configured / on failure)
                    backup_to_google_sheets(result)

                    # 1. Notify the admin (support@marketsignalpro.com)
                    sent, info = send_signup_email(result)
                    # 2. Send a welcome/confirmation email to the user
                    user_sent, user_info = send_user_confirmation_email(result)

            if ok:
                if sent and user_sent:
                    st.success("You're on the early-access list. Check your inbox for a confirmation — we'll be in touch soon.")
                elif user_sent:
                    st.success("You're on the early-access list. Check your inbox for a confirmation.")
                elif sent:
                    st.success("You're on the early-access list. We will be in touch soon.")
                    st.caption(f"(Confirmation email could not be delivered: {user_info})")
                else:
                    st.success("You're on the early-access list.")
                    st.info(info)

                # Reset timer so a real user can't re-submit instantly via back button
                st.session_state.msp_form_loaded_at = time.time()
            else:
                st.info(result)

    st.markdown(
        """
<div class="msp-proof">
  <span>✓ AI-focused market discovery</span>
  <span>✓ Built for everyday traders</span>
  <span>✓ Early access before public launch</span>
</div>
""",
        unsafe_allow_html=True,
    )

with right:
    # Only render the live preview in the right column for desktop users.
    # Mobile users see it inline in the left column above the form (see above).
    if not _is_mobile:
        components.html(preview_html, height=775, scrolling=False)

st.markdown("</div></div>", unsafe_allow_html=True)


# ============================================================
# TICKER TAPE
# ============================================================
ticker_items = [
    ("AI Signals", "+ Early"),
    ("Momentum", "+ Radar"),
    ("Sentiment", "+ Shift"),
    ("Squeeze", "+ Watch"),
    ("Volume", "+ Surge"),
    ("Market", "+ Scan"),
] * 2

ticker_html = '<div class="msp-ticker-tape"><div class="msp-ticker-track">'
for label, value in ticker_items:
    ticker_html += f'<div class="msp-ticker-chip"><b>{label}</b><span>{value}</span></div>'
ticker_html += "</div></div>"
st.markdown(ticker_html, unsafe_allow_html=True)


# ============================================================
# FEATURES + GALLERY
# ============================================================
gallery_html = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;700;800;900&display=swap');
*{box-sizing:border-box}body{margin:0;background:transparent;color:#edf4ff;font-family:Inter,sans-serif;overflow:hidden;padding:6px 0 14px}
.gallery-shell{overflow:hidden;border-radius:28px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.025);box-shadow:0 30px 100px rgba(0,0,0,.55);padding:16px}
.gallery-track{display:flex;gap:16px;width:max-content;animation:gallery 35s linear infinite}@keyframes gallery{from{transform:translateX(0)}to{transform:translateX(-50%)}}
/* Preview card frame — 320x220, dark fintech theme */
.ai-card{width:320px;height:220px;flex:0 0 auto;border-radius:22px;border:1px solid rgba(255,255,255,.12);position:relative;overflow:hidden;background:linear-gradient(180deg,#0b1322 0%,#070b14 100%);box-shadow:0 18px 50px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.04)}
.ai-card:before{content:"";position:absolute;inset:0;z-index:3;background:radial-gradient(ellipse at 50% 100%,rgba(0,0,0,.55),transparent 55%);pointer-events:none}
.ai-card:after{content:"";position:absolute;inset:0;z-index:2;background:linear-gradient(115deg,transparent 30%,rgba(255,255,255,.05) 50%,transparent 70%);pointer-events:none}
.mini-frame{position:absolute;inset:0;padding:11px 13px;filter:blur(1.6px) saturate(1.05);opacity:.92;z-index:1}
.mini-bar{display:flex;align-items:center;gap:7px;margin-bottom:9px}
.mini-bar .dots{display:flex;gap:3px}
.mini-bar .dots i{width:6px;height:6px;border-radius:50%;display:block}
.mini-bar .dots i:nth-child(1){background:#ef4444}.mini-bar .dots i:nth-child(2){background:#f59e0b}.mini-bar .dots i:nth-child(3){background:#22c55e}
.mini-bar .ttl{font-family:JetBrains Mono,monospace;font-size:8px;color:#5f7491;letter-spacing:.2px;flex:1;white-space:nowrap;overflow:hidden}
.mini-bar .badge{font-size:7px;font-weight:900;color:#fcd34d;background:rgba(245,158,11,.14);border:1px solid rgba(245,158,11,.3);padding:2px 5px;border-radius:6px;letter-spacing:.3px}
.mini-bar .big{font-size:18px;font-weight:900;color:#86efac;font-family:JetBrains Mono,monospace;line-height:1}
.mini-label{position:absolute;left:14px;bottom:12px;z-index:4;color:#eaf2ff;font-weight:900;font-size:12px;letter-spacing:-.2px;background:rgba(7,17,31,.86);padding:5px 10px;border-radius:8px;border:1px solid rgba(96,165,250,.22);backdrop-filter:blur(6px);text-shadow:0 1px 4px rgba(0,0,0,.8)}

/* Smart Insights mini — removed (now in live preview) */

/* Discovery mini — removed (now in live preview as Signal Categories) */

/* Matrix mini */
.matrix{display:grid;grid-template-columns:30px repeat(5,1fr);gap:2px}
.m-cell{font-size:7px;font-weight:900;text-align:center;padding:3px 1px;border-radius:2px;font-family:JetBrains Mono,monospace}
.m-head{font-size:6.5px;color:#7c8fae;text-align:center;padding:2px 0;font-weight:700}
.m-tk{font-size:7.5px;color:#60a5fa;font-weight:900;font-family:JetBrains Mono,monospace;display:flex;align-items:center;padding-left:2px}
.m-cell.hot{background:rgba(34,197,94,.55);color:#022c1a}
.m-cell.warm{background:rgba(34,197,94,.35);color:#dcfce7}
.m-cell.mid{background:rgba(34,197,94,.2);color:#86efac}
.m-cell.cool{background:rgba(34,197,94,.12);color:#86efac}
.m-cell.cold{background:rgba(11,18,32,.6);color:#475569;border:1px solid rgba(255,255,255,.04)}

/* Score Breakdown mini */
.sb-row{display:grid;grid-template-columns:60px 1fr 28px;gap:5px;align-items:center;margin-bottom:5px}
.sb-lab{font-size:6.5px;color:#7c8fae;line-height:1.2}
.sb-bar{height:5px;background:rgba(255,255,255,.06);border-radius:999px;overflow:hidden}
.sb-fill{height:100%;border-radius:999px}
.sb-fill.green{background:linear-gradient(90deg,#16a34a,#22c55e)}
.sb-fill.orange{background:linear-gradient(90deg,#d97706,#f59e0b)}
.sb-val{font-size:6.5px;font-weight:900;text-align:right;font-family:JetBrains Mono,monospace}
.sb-val.green{color:#86efac}.sb-val.orange{color:#fcd34d}

/* Signal Performance mini */
.perf-head{display:flex;align-items:center;gap:8px;margin-bottom:7px}
.perf-stat{font-family:JetBrains Mono,monospace;font-size:20px;font-weight:900;color:#86efac;line-height:1}
.perf-label{font-size:6.5px;color:#7c8fae;letter-spacing:.3px}
.perf-mini{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-bottom:6px}
.perf-mini div{padding:4px;border-radius:4px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);text-align:center}
.perf-mini b{display:block;font-size:9px;font-weight:900;font-family:JetBrains Mono,monospace}
.perf-mini b.green{color:#86efac}.perf-mini b.red{color:#fca5a5}.perf-mini b.blue{color:#93b4fd}
.perf-mini span{display:block;font-size:5.5px;color:#5f7491;margin-top:1px}
.perf-row{display:grid;grid-template-columns:1fr auto auto;gap:5px;align-items:center;padding:3px 4px;border-bottom:1px solid rgba(255,255,255,.04);font-size:7px}
.perf-row:last-child{border-bottom:0}
.perf-tk{color:#60a5fa;font-weight:900;font-family:JetBrains Mono,monospace}
.perf-pct{font-family:JetBrains Mono,monospace;font-weight:900}
.perf-pct.green{color:#86efac}.perf-pct.red{color:#fca5a5}
.perf-pill{padding:1px 4px;border-radius:3px;font-size:5.5px;font-weight:900}
.perf-pill.win{background:rgba(34,197,94,.2);color:#86efac}
.perf-pill.loss{background:rgba(239,68,68,.18);color:#fca5a5}

/* Smart Watchlist mini */
.wl-row{display:grid;grid-template-columns:34px 1fr auto auto;gap:5px;align-items:center;padding:4px 5px;border-radius:5px;background:rgba(255,255,255,.025);margin-bottom:3px;border-left:2px solid}
.wl-row.alert{border-left-color:#f59e0b}
.wl-row.buy{border-left-color:#22c55e}
.wl-row.hold{border-left-color:#60a5fa}
.wl-tk{font-family:JetBrains Mono,monospace;color:#60a5fa;font-weight:900;font-size:8px}
.wl-name{font-size:6px;color:#7c8fae;line-height:1.1}
.wl-score{font-family:JetBrains Mono,monospace;font-weight:900;font-size:8px}
.wl-score.green{color:#86efac}.wl-score.orange{color:#fcd34d}.wl-score.blue{color:#93b4fd}
.wl-alert{font-size:9px}

@media(max-width:680px){.ai-card{width:240px;height:190px}.gallery-shell{padding:10px;border-radius:20px}.gallery-track{animation-duration:50s}}
@media(max-width:420px){.ai-card{width:220px;height:178px}.gallery-track{animation-duration:55s}}
</style>
</head>
<body>
<div class="gallery-shell">
  <div class="gallery-track">
    <div class="ai-card"><div class="mini-frame"><div class="mini-bar"><div class="dots"><i></i><i></i><i></i></div><div class="ttl">Score Breakdown — NVDA</div><div class="big">88</div></div><div class="sb-row"><div class="sb-lab">Momentum (RSI)</div><div class="sb-bar"><div class="sb-fill green" style="width:80%"></div></div><div class="sb-val green">20/25</div></div><div class="sb-row"><div class="sb-lab">Trend (MA20/50)</div><div class="sb-bar"><div class="sb-fill green" style="width:90%"></div></div><div class="sb-val green">18/20</div></div><div class="sb-row"><div class="sb-lab">MACD Signal</div><div class="sb-bar"><div class="sb-fill green" style="width:86%"></div></div><div class="sb-val green">13/15</div></div><div class="sb-row"><div class="sb-lab">Volume Surge</div><div class="sb-bar"><div class="sb-fill orange" style="width:60%"></div></div><div class="sb-val orange">9/15</div></div><div class="sb-row"><div class="sb-lab">Sentiment</div><div class="sb-bar"><div class="sb-fill green" style="width:80%"></div></div><div class="sb-val green">12/15</div></div></div><div class="mini-label">Score Breakdown</div></div>
    <div class="ai-card"><div class="mini-frame"><div class="mini-bar"><div class="dots"><i></i><i></i><i></i></div><div class="ttl">Opportunity Matrix</div><div class="badge">EXCLUSIVE ✨</div></div><div class="matrix"><div></div><div class="m-head">Mom</div><div class="m-head">Trend</div><div class="m-head">Vol</div><div class="m-head">Sent</div><div class="m-head">Sq</div><div class="m-tk">NVDA</div><div class="m-cell hot">20</div><div class="m-cell hot">18</div><div class="m-cell mid">9</div><div class="m-cell warm">12</div><div class="m-cell cold">0</div><div class="m-tk">TSLA</div><div class="m-cell warm">14</div><div class="m-cell warm">16</div><div class="m-cell warm">13</div><div class="m-cell warm">10</div><div class="m-cell cool">6</div><div class="m-tk">GME</div><div class="m-cell hot">18</div><div class="m-cell cold">4</div><div class="m-cell warm">15</div><div class="m-cell warm">14</div><div class="m-cell warm">10</div></div></div><div class="mini-label">BI Opportunity Matrix</div></div>
    <div class="ai-card"><div class="mini-frame"><div class="mini-bar"><div class="dots"><i></i><i></i><i></i></div><div class="ttl">Signal Performance — 30d</div><div class="perf-stat">68%</div></div><div class="perf-label" style="margin-bottom:6px">Win rate · 47 trades tracked</div><div class="perf-mini"><div><b class="green">32</b><span>WINS</span></div><div><b class="red">15</b><span>LOSSES</span></div><div><b class="blue">+12.4%</b><span>AVG GAIN</span></div></div><div class="perf-row"><div class="perf-tk">NVDA</div><div class="perf-pct green">+18.2%</div><div class="perf-pill win">WIN</div></div><div class="perf-row"><div class="perf-tk">COIN</div><div class="perf-pct green">+9.7%</div><div class="perf-pill win">WIN</div></div><div class="perf-row"><div class="perf-tk">RIVN</div><div class="perf-pct red">-4.2%</div><div class="perf-pill loss">LOSS</div></div></div><div class="mini-label">Signal Performance</div></div>
    <div class="ai-card"><div class="mini-frame"><div class="mini-bar"><div class="dots"><i></i><i></i><i></i></div><div class="ttl">Smart Watchlist — Alerts</div></div><div class="wl-row alert"><div class="wl-tk">NVDA</div><div class="wl-name">Momentum confirmed</div><div class="wl-score green">92</div><div class="wl-alert">🔔</div></div><div class="wl-row buy"><div class="wl-tk">SOFI</div><div class="wl-name">Squeeze setup ready</div><div class="wl-score green">87</div><div class="wl-alert">⚡</div></div><div class="wl-row alert"><div class="wl-tk">PLTR</div><div class="wl-name">Trend break detected</div><div class="wl-score orange">74</div><div class="wl-alert">🔔</div></div><div class="wl-row buy"><div class="wl-tk">AMD</div><div class="wl-name">Volume surge active</div><div class="wl-score green">81</div><div class="wl-alert">⚡</div></div><div class="wl-row hold"><div class="wl-tk">META</div><div class="wl-name">Holding strong base</div><div class="wl-score blue">69</div><div class="wl-alert">👀</div></div></div><div class="mini-label">Smart Watchlist & Alerts</div></div>
    <div class="ai-card"><div class="mini-frame"><div class="mini-bar"><div class="dots"><i></i><i></i><i></i></div><div class="ttl">Score Breakdown — NVDA</div><div class="big">88</div></div><div class="sb-row"><div class="sb-lab">Momentum (RSI)</div><div class="sb-bar"><div class="sb-fill green" style="width:80%"></div></div><div class="sb-val green">20/25</div></div><div class="sb-row"><div class="sb-lab">Trend (MA20/50)</div><div class="sb-bar"><div class="sb-fill green" style="width:90%"></div></div><div class="sb-val green">18/20</div></div><div class="sb-row"><div class="sb-lab">MACD Signal</div><div class="sb-bar"><div class="sb-fill green" style="width:86%"></div></div><div class="sb-val green">13/15</div></div><div class="sb-row"><div class="sb-lab">Volume Surge</div><div class="sb-bar"><div class="sb-fill orange" style="width:60%"></div></div><div class="sb-val orange">9/15</div></div><div class="sb-row"><div class="sb-lab">Sentiment</div><div class="sb-bar"><div class="sb-fill green" style="width:80%"></div></div><div class="sb-val green">12/15</div></div></div><div class="mini-label">Score Breakdown</div></div>
    <div class="ai-card"><div class="mini-frame"><div class="mini-bar"><div class="dots"><i></i><i></i><i></i></div><div class="ttl">Opportunity Matrix</div><div class="badge">EXCLUSIVE ✨</div></div><div class="matrix"><div></div><div class="m-head">Mom</div><div class="m-head">Trend</div><div class="m-head">Vol</div><div class="m-head">Sent</div><div class="m-head">Sq</div><div class="m-tk">NVDA</div><div class="m-cell hot">20</div><div class="m-cell hot">18</div><div class="m-cell mid">9</div><div class="m-cell warm">12</div><div class="m-cell cold">0</div><div class="m-tk">TSLA</div><div class="m-cell warm">14</div><div class="m-cell warm">16</div><div class="m-cell warm">13</div><div class="m-cell warm">10</div><div class="m-cell cool">6</div><div class="m-tk">GME</div><div class="m-cell hot">18</div><div class="m-cell cold">4</div><div class="m-cell warm">15</div><div class="m-cell warm">14</div><div class="m-cell warm">10</div></div></div><div class="mini-label">BI Opportunity Matrix</div></div>
    <div class="ai-card"><div class="mini-frame"><div class="mini-bar"><div class="dots"><i></i><i></i><i></i></div><div class="ttl">Signal Performance — 30d</div><div class="perf-stat">68%</div></div><div class="perf-label" style="margin-bottom:6px">Win rate · 47 trades tracked</div><div class="perf-mini"><div><b class="green">32</b><span>WINS</span></div><div><b class="red">15</b><span>LOSSES</span></div><div><b class="blue">+12.4%</b><span>AVG GAIN</span></div></div><div class="perf-row"><div class="perf-tk">NVDA</div><div class="perf-pct green">+18.2%</div><div class="perf-pill win">WIN</div></div><div class="perf-row"><div class="perf-tk">COIN</div><div class="perf-pct green">+9.7%</div><div class="perf-pill win">WIN</div></div><div class="perf-row"><div class="perf-tk">RIVN</div><div class="perf-pct red">-4.2%</div><div class="perf-pill loss">LOSS</div></div></div><div class="mini-label">Signal Performance</div></div>
    <div class="ai-card"><div class="mini-frame"><div class="mini-bar"><div class="dots"><i></i><i></i><i></i></div><div class="ttl">Smart Watchlist — Alerts</div></div><div class="wl-row alert"><div class="wl-tk">NVDA</div><div class="wl-name">Momentum confirmed</div><div class="wl-score green">92</div><div class="wl-alert">🔔</div></div><div class="wl-row buy"><div class="wl-tk">SOFI</div><div class="wl-name">Squeeze setup ready</div><div class="wl-score green">87</div><div class="wl-alert">⚡</div></div><div class="wl-row alert"><div class="wl-tk">PLTR</div><div class="wl-name">Trend break detected</div><div class="wl-score orange">74</div><div class="wl-alert">🔔</div></div><div class="wl-row buy"><div class="wl-tk">AMD</div><div class="wl-name">Volume surge active</div><div class="wl-score green">81</div><div class="wl-alert">⚡</div></div><div class="wl-row hold"><div class="wl-tk">META</div><div class="wl-name">Holding strong base</div><div class="wl-score blue">69</div><div class="wl-alert">👀</div></div></div><div class="mini-label">Smart Watchlist & Alerts</div></div>
  </div>
</div>
</body>
</html>
"""

st.markdown(
    """
<section class="msp-section msp-section-feature">
<div class="msp-section-head">
<div class="msp-section-kicker">Preview of what is coming</div>
<h3>Built around <span class="msp-gradient-text">real signals.</span></h3>
<p>Three quiet steps from the raw market to a decision you can actually defend — no noise, no jargon, just signal.</p>
</div>

<div class="msp-story">
<div class="msp-story-step">
<div class="msp-story-num">01</div>
<div class="msp-story-icon">🎯</div>
<h4>Discover</h4>
<p>17 composite signal categories — squeeze setups, hidden movers, sentiment flips, volume breakouts — surface the names already showing up across the data instead of the loudest headlines.</p>
</div>
<div class="msp-story-arrow">→</div>
<div class="msp-story-step">
<div class="msp-story-num">02</div>
<div class="msp-story-icon">📊</div>
<h4>Understand</h4>
<p>Each opportunity opens into a clean score breakdown: trend, momentum, volume, sentiment, and the BI matrix — every component visible so you see <em>why</em>, not just <em>what</em>.</p>
</div>
<div class="msp-story-arrow">→</div>
<div class="msp-story-step">
<div class="msp-story-num">03</div>
<div class="msp-story-icon">🧠</div>
<h4>Decide</h4>
<p>Plain-English AI insights translate the full signal stack into one clear sentence, so the next step — watchlist, deeper research, or pass — actually feels obvious.</p>
</div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="msp-gallery-wrap">', unsafe_allow_html=True)
components.html(gallery_html, height=290, scrolling=False)
st.markdown('</div></section>', unsafe_allow_html=True)


# ============================================================
# FOOTER
# ============================================================
st.markdown(
    """
<footer class="msp-footer">
<div class="msp-footer-brand">
<span class="msp-footer-mark">M</span>
<span>Market<span style="color:var(--gold);">Signal</span>Pro</span>
</div>
<p class="msp-disclaimer">
MarketSignalPro is for informational and educational purposes only and is not financial, investment, tax, or legal advice. Nothing on this site constitutes a recommendation to buy, sell, or hold any security. Markets involve risk, including possible loss of principal. Always do your own research and consult a licensed financial professional before making investment decisions.
</p>
<div class="msp-footer-meta">
<span>© 2026 MarketSignalPro. All rights reserved.</span>
<span class="msp-footer-dot">·</span>
<a href="mailto:support@marketsignalpro.com">support@marketsignalpro.com</a>
</div>
</footer>
""",
    unsafe_allow_html=True,
)


# ============================================================
# OPTIONAL ADMIN VIEW: add ?admin=1
# ============================================================
try:
    if st.query_params.get("admin") == "1":
        st.markdown("---")
        st.subheader("Early-access signups")
        signups = load_signups()
        st.dataframe(signups, use_container_width=True)
        st.download_button(
            "Download signups CSV",
            signups.to_csv(index=False),
            file_name="marketsignalpro_signups.csv",
            mime="text/csv",
        )
except Exception:
    pass
