#!/usr/bin/env python3
"""
MarketSignalPro Alerts Worker v3
Runs every 15 min via Render cron (optional — the Streamlit app delivers composite
signals inline; this worker covers user price/RSI/volume alerts + signal outcomes).
Uses the SHARED storage layer (msp_store) so it reads the SAME users/alerts the
Streamlit app writes (Postgres via DATABASE_URL, or shared .msp_data files).

DATA SOURCE: Polygon (via polygon_adapter). Quotes + technicals are computed from
~120 daily bars per alerted ticker — the SAME licensed feed the app uses. The legacy
yfinance/Yahoo path was removed (Yahoo's ToS is a gray area for a paid product).
"""
import os, json, time, hashlib, logging, traceback
from datetime import datetime, timedelta
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("msp.alerts")

# ── Shared storage (same backend the app uses) ──
try:
    import msp_store as _store
    ALERTS_DB = _store.ALERTS_DB_PATH
    USERS_DB  = _store.USERS_DB_PATH
    FIRED_DB  = _store.FIRED_DB_PATH
    PREV_SENT = _store.PREV_SENT_PATH
    _HAS_STORE = True
    log.info(f"storage backend: {_store.storage_backend()}")
except Exception as _e:
    # Fallback to env/legacy paths if the shared module isn't importable
    ALERTS_DB = os.environ.get("ALERTS_DB_PATH", "/tmp/msp_alerts.json")
    USERS_DB  = os.environ.get("USERS_DB_PATH",  "/tmp/msp_users.json")
    FIRED_DB  = os.environ.get("FIRED_DB_PATH",  "/tmp/msp_fired.json")
    PREV_SENT = os.environ.get("PREV_SENT_PATH", "/tmp/msp_prev_sentiment.json")
    _HAS_STORE = False
    log.warning(f"msp_store unavailable ({_e}); using file paths")

TG_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
RESEND_KEY= os.environ.get("RESEND_API_KEY", "")
APP_URL   = os.environ.get("APP_URL", "https://marketsignalpro.streamlit.app")
EMAIL_FROM= os.environ.get("EMAIL_FROM", "MarketSignalPro <alerts@marketsignalpro.com>")
POLYGON_KEY = os.environ.get("POLYGON_API_KEY", "")
try:
    import polygon_adapter as _poly
except Exception as _pe:
    _poly = None
    log.warning(f"polygon_adapter unavailable ({_pe}); price/technical alerts will no-op")

def load_json(path, default=None):
    if _HAS_STORE:
        try:
            return _store.read_json(path, {} if default is None else default)
        except Exception:
            return {} if default is None else default
    try:
        with open(path) as f: return json.load(f)
    except: return {} if default is None else default

def save_json(path, data):
    if _HAS_STORE:
        try:
            _store.write_json(path, data); return
        except Exception as e:
            log.error(f"save_json {path}: {e}"); return
    try:
        with open(path,"w") as f: json.dump(data,f,indent=2,default=str)
    except Exception as e: log.error(f"save_json {path}: {e}")

def fire_key(email, aid):
    hour=datetime.now().strftime("%Y-%m-%d-%H")
    return hashlib.md5(f"{email}:{aid}:{hour}".encode()).hexdigest()

def already_fired(key):
    fired=load_json(FIRED_DB,{})
    cutoff=(datetime.now()-timedelta(hours=2)).timestamp()
    return key in {k:v for k,v in fired.items() if v>cutoff}

def mark_fired(key):
    fired=load_json(FIRED_DB,{})
    fired[key]=datetime.now().timestamp()
    cutoff=(datetime.now()-timedelta(hours=4)).timestamp()
    fired={k:v for k,v in fired.items() if v>cutoff}
    save_json(FIRED_DB,fired)

# ── Quotes + technicals from Polygon (one ~120-bar pull per ticker, cached per run) ──
_BARS_CACHE = {}
def _bars(t):
    """~120 daily bars for a ticker via Polygon; cached for this worker run. [] on failure."""
    t = (t or "").upper()
    if not t or not POLYGON_KEY or _poly is None:
        return []
    if t not in _BARS_CACHE:
        try: _BARS_CACHE[t] = _poly.daily_bars(POLYGON_KEY, t, days=120)
        except Exception: _BARS_CACHE[t] = []
    return _BARS_CACHE[t]

def get_quote(t):
    bars = _bars(t)
    if not bars: return None
    closes=[b["c"] for b in bars]; vols=[b["v"] for b in bars]
    p=closes[-1]; pv=closes[-2] if len(closes)>=2 else p
    v=vols[-1]; av=(sum(vols)/len(vols)) if vols else 0
    return {"price":round(p,2),"prev":round(pv,2),"pct":round(((p-pv)/pv)*100,2) if pv else 0,
            "volume":int(v),"vol_ratio":round(v/av,2) if av>0 else 1,"change":round(p-pv,2)}

def get_technicals(t):
    bars=_bars(t)
    if len(bars)<20: return {}
    try:
        import pandas as pd, ta.momentum, ta.trend, ta.volatility
        c=pd.Series([b["c"] for b in bars])
        rsi=ta.momentum.RSIIndicator(c,14).rsi().iloc[-1]
        ma20=c.rolling(20).mean().iloc[-1]; ma50=c.rolling(min(50,len(c))).mean().iloc[-1]
        macd_ind=ta.trend.MACD(c); macd=macd_ind.macd().iloc[-1]; macd_s=macd_ind.macd_signal().iloc[-1]
        bb=ta.volatility.BollingerBands(c); bb_w=bb.bollinger_wband().iloc[-1]
        bb_avg=bb.bollinger_wband().rolling(90).mean().iloc[-1]
        month_ret=((c.iloc[-1]-c.iloc[-20])/c.iloc[-20])*100 if len(c)>=20 else 0
        return {"rsi":round(float(rsi),1),"ma20":round(float(ma20),2),"ma50":round(float(ma50),2),
                "macd":round(float(macd),4),"macd_s":round(float(macd_s),4),
                "bb_w":round(float(bb_w),4),"bb_avg":round(float(bb_avg),4),
                "month_ret":round(float(month_ret),2),"price":round(float(c.iloc[-1]),2)}
    except Exception:
        return {}

# ── Delivery ───────────────────────────────────────────────────

def send_telegram(chat_id, msg):
    if not TG_TOKEN or not chat_id: return False
    try:
        import requests
        r=requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id":chat_id,"text":msg,"parse_mode":"Markdown","disable_web_page_preview":True},timeout=10)
        if r.status_code==200: log.info(f"  ✅ Telegram → {chat_id}"); return True
        log.error(f"  ❌ Telegram {r.status_code}: {r.text[:100]}"); return False
    except Exception as e: log.error(f"  ❌ TG: {e}"); return False

def send_email(to, subject, msg):
    if not RESEND_KEY: return False
    try:
        import requests
        html=f"""<div style="font-family:Inter,sans-serif;background:#07090f;padding:40px;max-width:560px;margin:0 auto;">
        <div style="font-size:20px;font-weight:700;margin-bottom:20px;color:#e2e8f0;">Market<span style="color:#f59e0b;">Signal</span>Pro</div>
        <div style="background:#0d1525;border:1px solid rgba(37,99,235,0.3);border-radius:12px;padding:24px;margin-bottom:16px;">
        <div style="font-size:11px;color:#2563eb;font-weight:700;letter-spacing:2px;margin-bottom:10px;">ALERT TRIGGERED</div>
        <div style="font-size:13px;color:#d1d9e6;white-space:pre-wrap;line-height:1.8;">{msg.replace("*","").replace("_","")}</div></div>
        <a href="{APP_URL}" style="display:block;text-align:center;padding:12px;background:#2563eb;color:#fff;text-decoration:none;border-radius:8px;font-weight:700;">View Dashboard →</a>
        <p style="font-size:11px;color:#2a3a52;text-align:center;margin-top:16px;">Educational signals only. Not financial advice.</p></div>"""
        r=requests.post("https://api.resend.com/emails",
            headers={"Authorization":f"Bearer {RESEND_KEY}","Content-Type":"application/json"},
            json={"from":EMAIL_FROM,"to":[to],"subject":subject,"html":html},timeout=12)
        if r.status_code in (200,201): log.info(f"  ✅ Email → {to}"); return True
        log.error(f"  ❌ Email {r.status_code}: {r.text[:100]}"); return False
    except Exception as e: log.error(f"  ❌ Email: {e}"); return False

def send_push(player_ids, title, msg):
    """Send OneSignal web/mobile push to a list of subscription IDs."""
    app_id  = os.environ.get("ONESIGNAL_APP_ID","")
    api_key = os.environ.get("ONESIGNAL_REST_API_KEY","")
    if not app_id or not api_key or not player_ids: return False
    try:
        import requests
        payload = {
            "app_id": app_id,
            "include_player_ids": player_ids if isinstance(player_ids,list) else [player_ids],
            "headings": {"en": title},
            "contents": {"en": msg},
            "url": APP_URL,
        }
        r = requests.post("https://onesignal.com/api/v1/notifications",
            headers={"Authorization":f"Basic {api_key}","Content-Type":"application/json"},
            json=payload, timeout=10)
        if r.status_code in (200,201):
            log.info(f"  ✅ Push → {len(player_ids) if isinstance(player_ids,list) else 1} device(s)")
            return True
        log.error(f"  ❌ Push {r.status_code}: {r.text[:100]}"); return False
    except Exception as e: log.error(f"  ❌ Push: {e}"); return False

def deliver(email, user, subject, msg, channels):
    tg_id=user.get("telegram_chat_id","")
    push_ids=user.get("push_subscription_ids",[])
    is_prem=user.get("role","free") in ("premium","admin","owner")
    notif_prefs=user.get("notif_prefs",{})

    # Email always allowed (free + premium)
    if "email" in channels and notif_prefs.get("email_enabled", True):
        send_email(email, subject, msg)

    # Telegram (premium only, user-configured)
    if "telegram" in channels and is_prem and tg_id and notif_prefs.get("telegram_enabled", True):
        full=msg+"\n\n─────────────────\n📊 [Open MarketSignalPro]("+APP_URL+")\n⚠️ _Not financial advice._"
        send_telegram(tg_id, full)

    # Push (premium only, user-enabled in browser)
    if "push" in channels and is_prem and push_ids and notif_prefs.get("push_enabled", True):
        # Strip Markdown from msg for push (push doesn't render it)
        plain_msg = msg.replace("*","").replace("_","")[:200]  # 200 char limit
        send_push(push_ids, subject, plain_msg)

# ── Main ───────────────────────────────────────────────────────

def process_all_alerts():
    log.info("="*60)
    log.info(f"MarketSignalPro Alert Worker — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("="*60)

    alerts_db=load_json(ALERTS_DB,{}); users_db=load_json(USERS_DB,{})

    # ── Standard user alerts (price / % / volume / RSI) ──
    # The Streamlit app now evaluates these INLINE every warm cycle (app._process_price_alerts),
    # so they fire on Cloud without this cron. Skip here by default to avoid DOUBLE-sending
    # (the app + worker use separate dedup stores). Set WORKER_DELIVERS_PRICE_ALERTS=1 to run
    # them from the cron instead (e.g. if you deploy the worker standalone without the app).
    if os.environ.get("WORKER_DELIVERS_PRICE_ALERTS", "0").lower() not in ("1", "true", "yes"):
        log.info("\n── Standard Alerts — handled inline by the app; worker skipping ──")
        alerts_db = {}
    log.info(f"\n── Standard Alerts ──")
    for email,user_alerts in alerts_db.items():
        user=users_db.get(email,{"role":"free"})
        for alert in user_alerts:
            if not alert.get("active",True): continue
            ticker=alert.get("ticker","").upper(); a_id=alert.get("id",ticker)
            fkey=fire_key(email,a_id)
            if already_fired(fkey): continue
            q=get_quote(ticker); tech=get_technicals(ticker) if q else {}
            if not q: continue
            atype=alert.get("type",""); threshold=float(alert.get("threshold",0))
            triggered=False; msg=""
            if atype=="price_above" and q["price"]>=threshold: triggered=True; msg=f"🎯 {ticker} hit ${q['price']:,.2f} — above your ${threshold:,.2f} target"
            elif atype=="price_below" and q["price"]<=threshold: triggered=True; msg=f"⚠️ {ticker} dropped to ${q['price']:,.2f} — below ${threshold:,.2f}"
            elif atype=="pct_change" and abs(q["pct"])>=threshold:
                triggered=True; d="▲ up" if q["pct"]>0 else "▼ down"; msg=f"📈 {ticker} moved {d} {abs(q['pct']):.1f}% today"
            elif atype=="volume_spike" and q["vol_ratio"]>=threshold: triggered=True; msg=f"🔊 {ticker} volume is {q['vol_ratio']:.1f}× average"
            elif atype=="rsi_oversold" and tech.get("rsi",50)<=threshold: triggered=True; msg=f"📉 {ticker} RSI hit {tech['rsi']} — oversold"
            elif atype=="rsi_overbought" and tech.get("rsi",50)>=threshold: triggered=True; msg=f"📈 {ticker} RSI hit {tech['rsi']} — overbought"
            if triggered:
                log.info(f"  🔔 {email}/{ticker}: {msg}")
                full=(f"🔔 *MarketSignalPro Alert*\n\n{msg}\n\nPrice: *${q['price']:,.2f}* ({q['pct']:+.2f}%)\nVolume: {q['vol_ratio']:.1f}× avg")
                deliver(email,user,f"⚡ Alert: {ticker}",full,alert.get("channels",["email"]))
                mark_fired(fkey)

    # ── Composite category signals (DELIVERY of app-recorded entries) ────────
    # The Streamlit app's universe warm now detects + records NEW category entries
    # using the SHARED scoring engine (scoring.py), so the categories here match
    # Discover EXACTLY — no more divergent worker-only detectors. The worker's only
    # job is delivery: read the recently-recorded entry events and notify subscribed
    # users, deduped so each user gets each entry at most once.
    log.info("\n── Composite Category Signals (delivery) ──")
    subscribers = {}
    for email, user in users_db.items():
        cat_alerts = user.get("category_alerts", [])
        has_tg = bool(user.get("telegram_chat_id", ""))
        has_push = bool(user.get("push_subscription_ids"))
        is_prem = user.get("role", "free") in ("premium", "admin", "owner")
        if cat_alerts or (is_prem and (has_tg or has_push)):
            subscribers[email] = (user, cat_alerts if cat_alerts else "all")

    recent_events = []
    try:
        import sys, os as _os
        sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        from signal_engine import get_recent_signal_events
        recent_events = get_recent_signal_events(limit=150)
    except Exception as e:
        log.warning(f"  Could not read signal events: {e}")

    # Only deliver entries from the last ENTRY_MAX_AGE_H hours; already_fired() also
    # stops the same entry reaching the same user twice. ALERT_MIN_SCORE is an
    # optional extra conviction gate on top of the app's CATEGORY_ENTRY_FIT.
    ENTRY_MAX_AGE_H = float(os.environ.get("ENTRY_MAX_AGE_H", "24"))
    MIN_SCORE = int(os.environ.get("ALERT_MIN_SCORE", "0"))
    cutoff = datetime.now() - timedelta(hours=ENTRY_MAX_AGE_H)

    EVENT_CATS = ("🏛️ Insider Buy", "📰 8-K Filing", "📊 Short Interest")

    if not subscribers:
        log.info("  No composite subscribers yet")
    elif os.environ.get("WORKER_DELIVERS_SIGNALS", "0").lower() not in ("1", "true", "yes"):
        # The Streamlit app now delivers composite signals INLINE the moment it records them
        # (app._deliver_new_signals: events immediately, category entries as one digest), which
        # is instant and avoids this cron double-sending. Set WORKER_DELIVERS_SIGNALS=1 to move
        # delivery back to the cron instead.
        log.info("  Composite-signal delivery handled inline by the app; worker skipping "
                 "(set WORKER_DELIVERS_SIGNALS=1 to deliver from the cron)")
    else:
        # Cron-delivery fallback. Mirror the app's two lanes: EVENT filings immediately (one each);
        # category ENTRIES batched into a single per-user digest so a new-bar re-score doesn't flood.
        delivered = 0
        fresh = []
        for ev in recent_events:
            try:
                trig = datetime.fromisoformat(ev.get("triggered_at", ""))
            except Exception:
                continue
            if trig < cutoff:
                continue
            if not ev.get("category") or not ev.get("ticker"):
                continue
            if (ev.get("score_at_trigger", 0) or 0) < MIN_SCORE:
                continue
            fresh.append(ev)

        DIGEST_MAX = int(os.environ.get("DIGEST_MAX", "12"))
        for email, (user, wanted) in subscribers.items():
            channels = []
            if user.get("push_subscription_ids"): channels.append("push")
            if user.get("telegram_chat_id"):       channels.append("telegram")
            channels.append("email")

            mine_events = [e for e in fresh if e["category"] in EVENT_CATS
                           and (wanted == "all" or e["category"] in wanted)]
            mine_entries = [e for e in fresh if e["category"] not in EVENT_CATS
                            and (wanted == "all" or e["category"] in wanted)]

            # Lane 1 — event filings, one message each
            for ev in mine_events:
                eid = ev.get("id", f"{ev['ticker']}_{ev['category']}")
                fkey = fire_key(email, f"sig_{eid}")
                if already_fired(fkey):
                    continue
                price = ev.get("trigger_price", 0) or 0
                rec = ev.get("recommendation", "") or "WATCH"
                msg = (f"📊 *{ev['ticker']}* — *{ev['category']}*\n\n{rec}\n"
                       f"Price: *${price:,.2f}*\nOpen MarketSignalPro for the full breakdown.")
                deliver(email, user, f"📊 {ev['category']}: {ev['ticker']}", msg, channels)
                mark_fired(fkey); delivered += 1

            # Lane 2 — category entries, one ranked digest
            undelivered = [e for e in mine_entries
                           if not already_fired(fire_key(email, f"sig_{e.get('id', e['ticker'])}"))]
            if undelivered:
                undelivered.sort(key=lambda e: float(e.get("score_at_trigger", 0) or 0), reverse=True)
                shown = undelivered[:DIGEST_MAX]
                lines = [f"• {e['ticker']} · {e['category']} · {e.get('score_at_trigger','?')}/100"
                         + (f" · {e.get('recommendation','')}" if e.get("recommendation") else "")
                         for e in shown]
                more = len(undelivered) - len(shown)
                digest = (f"📊 *{len(undelivered)} new setup(s)* — MarketSignalPro\n\n"
                          + "\n".join(lines)
                          + (f"\n…and {more} more in the app." if more > 0 else "")
                          + "\n\nOpen MarketSignalPro for the full breakdowns.")
                deliver(email, user, f"📊 {len(undelivered)} new setups", digest, channels)
                for e in undelivered:
                    mark_fired(fire_key(email, f"sig_{e.get('id', e['ticker'])}"))
                delivered += 1
        log.info(f"  Delivered {delivered} category/event notification(s)")

    # ── Update signal outcomes for tracked signal events ──
    try:
        import sys, os as _os
        sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        from signal_engine import update_signal_outcomes
        def _price_fetch(ticker, days):
            try:
                if _poly is None or not POLYGON_KEY:
                    return None
                import pandas as pd
                bars = _poly.daily_bars(POLYGON_KEY, ticker, days=max(days, 30))
                if not bars:
                    return None
                df = pd.DataFrame(bars).rename(
                    columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
                return df
            except Exception:
                return None
        outcomes_updated = update_signal_outcomes(_price_fetch)
        log.info(f"📈 Signal outcomes updated for {len(outcomes_updated)} events")
    except Exception as e:
        log.warning(f"Signal outcomes update failed: {e}")

    log.info("\n✅ Done.")

if __name__=="__main__":
    mode=os.environ.get("WORKER_MODE","once")
    if mode=="loop":
        log.info("Loop mode — every 15 min")
        while True:
            try: process_all_alerts()
            except: log.error(traceback.format_exc())
            time.sleep(900)
    else:
        process_all_alerts()
