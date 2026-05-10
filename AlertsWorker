#!/usr/bin/env python3
"""
StockWins Alerts Worker v2
Runs every 15 min via Render cron. Checks standard + composite signals.
"""
import os, json, time, hashlib, logging, traceback
from datetime import datetime, timedelta
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sw.alerts")

ALERTS_DB = os.environ.get("ALERTS_DB_PATH", "/tmp/sw_alerts.json")
USERS_DB  = os.environ.get("USERS_DB_PATH",  "/tmp/sw_users.json")
FIRED_DB  = os.environ.get("FIRED_DB_PATH",  "/tmp/sw_fired.json")
TG_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
RESEND_KEY= os.environ.get("RESEND_API_KEY", "")
SCAN_UNIVERSE = ["NVDA","TSLA","AMD","AAPL","MSTR","GME","AMC","PLTR","META","MSFT",
    "RIVN","LCID","SOUN","BBAI","ASTS","IONQ","SMCI","ARM","MULN","SPCE","BBIG",
    "FFIE","ATER","HOOD","NIO","LI","XPEV","MRNA","BNTX","CRWD"]

def load_json(path, default=None):
    try:
        with open(path) as f: return json.load(f)
    except: return {} if default is None else default

def save_json(path, data):
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

def get_quote(t):
    try:
        import yfinance as yf
        h=yf.Ticker(t).history(period="2d")
        if len(h)<1: return None
        p=float(h["Close"].iloc[-1]); pv=float(h["Close"].iloc[-2]) if len(h)>=2 else p
        v=int(h["Volume"].iloc[-1]); av=float(h["Volume"].mean())
        return {"price":round(p,2),"prev":round(pv,2),"pct":round(((p-pv)/pv)*100,2) if pv else 0,
                "volume":v,"vol_ratio":round(v/av,2) if av>0 else 1,"change":round(p-pv,2)}
    except: return None

def get_technicals(t):
    try:
        import yfinance as yf
        import ta.momentum, ta.trend, ta.volatility
        h=yf.Ticker(t).history(period="90d")
        if len(h)<20: return {}
        c=h["Close"]
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
    except: return {}

def get_fundamentals(t):
    try:
        import yfinance as yf
        i=yf.Ticker(t).info
        return {"sf":(i.get("shortPercentOfFloat") or 0),"dtc":(i.get("shortRatio") or 0),"mc":(i.get("marketCap") or 0)}
    except: return {}

def get_sentiment(t):
    try:
        import requests
        d=requests.get(f"https://api.stocktwits.com/api/2/streams/symbol/{t}.json",timeout=8).json()
        msgs=d.get("messages",[])
        bull=sum(1 for m in msgs if m.get("entities",{}).get("sentiment",{}) and m["entities"]["sentiment"].get("basic")=="Bullish")
        bear=sum(1 for m in msgs if m.get("entities",{}).get("sentiment",{}) and m["entities"]["sentiment"].get("basic")=="Bearish")
        tot=bull+bear
        return {"bull":round((bull/tot)*100) if tot else 50,"msgs":len(msgs)}
    except: return {"bull":50,"msgs":0}

def get_hot_list():
    try:
        import requests
        d=requests.get("https://api.stocktwits.com/api/2/trending/symbols.json",timeout=8).json()
        return [s["symbol"] for s in d.get("symbols",[])]
    except: return []

# ── 7 Composite Detectors ──────────────────────────────────────

def detect_squeeze(t,q,tech,fund,sent):
    sf=fund.get("sf",0)*100; dtc=fund.get("dtc",0)
    vr=q.get("vol_ratio",1); rsi=tech.get("rsi",50); pct=q.get("pct",0); bull=sent.get("bull",50)
    if sf>=15 and vr>=1.8 and rsi>=40 and pct>0:
        conf="🔥 High" if (sf>=20 and vr>=2.5) else "Medium"
        return True,(f"💥 *SQUEEZE SETUP — {t}*\n\n"
            f"Short float: *{sf:.1f}%* · DTC: {dtc:.1f}d\n"
            f"Volume: *{vr:.1f}× average* · RSI: {rsi}\n"
            f"Price: *${q['price']:,.2f}* ({pct:+.2f}% today)\n"
            f"Social: {bull}% bullish\nConfidence: {conf}\n\n"
            f"High short interest + rising volume = squeeze fuel.")
    return False,""

def detect_hidden_mover(t,q,tech,sent,hot):
    rsi=tech.get("rsi",50); ma20=tech.get("ma20",0); macd=tech.get("macd",0); macd_s=tech.get("macd_s",0)
    price=q.get("price",0); pct=q.get("pct",0); vr=q.get("vol_ratio",1); msgs=sent.get("msgs",0)
    if rsi>50 and price>ma20 and macd>macd_s and vr>=1.3 and t not in hot and msgs<10:
        return True,(f"💡 *HIDDEN MOVER — {t}*\n\n"
            f"Price: *${price:,.2f}* ({pct:+.2f}% today)\n"
            f"RSI: {rsi} · Above MA20 ✅ · MACD bullish ✅\n"
            f"Volume: {vr:.1f}× avg · Social posts: only {msgs}\n\n"
            f"Low noise + strong technicals = early discovery.")
    return False,""

def detect_sentiment_flip(t,q,tech,sent,prev_db):
    bull_now=sent.get("bull",50); bull_prev=prev_db.get(t,{}).get("bull",bull_now)
    jump=bull_now-bull_prev; price=q.get("price",0); pct=q.get("pct",0)
    if jump>=15 and bull_now>=60:
        return True,(f"🌡️ *SENTIMENT FLIP — {t}*\n\n"
            f"Bullish: *{bull_now}%* (was {bull_prev}% — jumped +{jump}pts)\n"
            f"Price: *${price:,.2f}* ({pct:+.2f}% today)\n\n"
            f"Trader mood sharply reversed upward.")
    return False,""

def detect_breakout(t,q,tech):
    price=q.get("price",0); prev=q.get("prev",0); ma20=tech.get("ma20",0)
    vr=q.get("vol_ratio",1); pct=q.get("pct",0); rsi=tech.get("rsi",50)
    crossed=(prev<ma20<=price); strong=(price>ma20*1.02 and vr>=2.0 and pct>2)
    if (crossed or strong) and vr>=1.5 and rsi>45:
        trig="crossed above 20-day MA" if crossed else "breaking above 20-day MA"
        return True,(f"⚡ *BREAKOUT — {t}*\n\n"
            f"Price *{trig}*\nPrice: *${price:,.2f}* ({pct:+.2f}%)\n"
            f"MA20: ${ma20:,.2f} · Volume: *{vr:.1f}× average* · RSI: {rsi}\n\n"
            f"High-volume breakouts above MAs often continue.")
    return False,""

def detect_fallen_angel(t,q,tech,fund):
    rsi=tech.get("rsi",50); mret=tech.get("month_ret",0); price=q.get("price",0); pct=q.get("pct",0); sf=fund.get("sf",0)*100
    if rsi<32 and mret<-18:
        s="🔴 Extreme" if rsi<25 else "⚠️ Significant"
        return True,(f"📉→📈 *FALLEN ANGEL — {t}*\n\n"
            f"RSI: *{rsi}* ({s} oversold)\nMonth return: *{mret:.1f}%*\n"
            f"Price: *${price:,.2f}* ({pct:+.2f}%) · Short float: {sf:.1f}%\n\n"
            f"Deeply oversold after sharp drop = recovery candidate. High risk.")
    return False,""

def detect_smart_money(t,q,tech):
    vr=q.get("vol_ratio",1); price=q.get("price",0); pct=q.get("pct",0)
    macd=tech.get("macd",0); macd_s=tech.get("macd_s",0); ma20=tech.get("ma20",0); ma50=tech.get("ma50",0); rsi=tech.get("rsi",50)
    if vr>=3.0 and macd>macd_s and price>ma20 and price>ma50 and pct>0:
        return True,(f"⚡🧲 *SMART MONEY SIGNAL — {t}*\n\n"
            f"Volume: *{vr:.1f}× above average* 🔊\nMACD bullish ✅ · Above MA20 & MA50 ✅\n"
            f"Price: *${price:,.2f}* ({pct:+.2f}%) · RSI: {rsi}\n\n"
            f"3×+ volume + all indicators aligned = institutional accumulation signal.")
    return False,""

def detect_vol_squeeze(t,q,tech):
    bb_w=tech.get("bb_w",1); bb_avg=tech.get("bb_avg",1); vr=q.get("vol_ratio",1)
    price=q.get("price",0); rsi=tech.get("rsi",50)
    if bb_avg>0 and bb_w<bb_avg*0.65 and vr>=1.4:
        bias="upward" if rsi>50 else "unclear"
        return True,(f"🌪️ *VOLATILITY SQUEEZE — {t}*\n\n"
            f"Bollinger Bands near 90-day compression low\n"
            f"Volume building: *{vr:.1f}×* · RSI: {rsi} · Bias: {bias}\n"
            f"Price: *${price:,.2f}*\n\nCompressed volatility + rising volume = coiled spring. Big move coming.")
    return False,""

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
        <div style="font-size:20px;font-weight:700;margin-bottom:20px;color:#e2e8f0;">Stock<span style="color:#f59e0b;">W</span>ins</div>
        <div style="background:#0d1525;border:1px solid rgba(37,99,235,0.3);border-radius:12px;padding:24px;margin-bottom:16px;">
        <div style="font-size:11px;color:#2563eb;font-weight:700;letter-spacing:2px;margin-bottom:10px;">ALERT TRIGGERED</div>
        <div style="font-size:13px;color:#d1d9e6;white-space:pre-wrap;line-height:1.8;">{msg.replace("*","").replace("_","")}</div></div>
        <a href="https://stockwins.streamlit.app" style="display:block;text-align:center;padding:12px;background:#2563eb;color:#fff;text-decoration:none;border-radius:8px;font-weight:700;">View Dashboard →</a>
        <p style="font-size:11px;color:#2a3a52;text-align:center;margin-top:16px;">Educational signals only. Not financial advice.</p></div>"""
        r=requests.post("https://api.resend.com/emails",
            headers={"Authorization":f"Bearer {RESEND_KEY}","Content-Type":"application/json"},
            json={"from":"StockWins <alerts@stockwins.com>","to":[to],"subject":subject,"html":html},timeout=12)
        if r.status_code in (200,201): log.info(f"  ✅ Email → {to}"); return True
        log.error(f"  ❌ Email {r.status_code}: {r.text[:100]}"); return False
    except Exception as e: log.error(f"  ❌ Email: {e}"); return False

def deliver(email, user, subject, msg, channels):
    tg_id=user.get("telegram_chat_id",""); is_prem=user.get("role","free") in ("premium","admin","owner")
    if "email" in channels: send_email(email, subject, msg)
    if "telegram" in channels and is_prem and tg_id:
        full=msg+"\n\n─────────────────\n📊 [Open StockWins](https://stockwins.streamlit.app)\n⚠️ _Not financial advice._"
        send_telegram(tg_id, full)

# ── Main ───────────────────────────────────────────────────────

def process_all_alerts():
    log.info("="*60)
    log.info(f"StockWins Alert Worker — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("="*60)

    alerts_db=load_json(ALERTS_DB,{}); users_db=load_json(USERS_DB,{})
    prev_sent=load_json("/tmp/sw_prev_sentiment.json",{}); new_sent={}

    # ── Standard user alerts ──
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
                full=(f"🔔 *StockWins Alert*\n\n{msg}\n\nPrice: *${q['price']:,.2f}* ({q['pct']:+.2f}%)\nVolume: {q['vol_ratio']:.1f}× avg")
                deliver(email,user,f"⚡ Alert: {ticker}",full,alert.get("channels",["email"]))
                mark_fired(fkey)

    # ── Composite category signals ──
    log.info(f"\n── Composite Scan ({len(SCAN_UNIVERSE)} tickers) ──")
    hot_list=get_hot_list()

    # Build subscriber list: premium users with Telegram = auto-subscribed
    subscribers={}
    for email,user in users_db.items():
        cat_alerts=user.get("category_alerts",[])
        has_tg=bool(user.get("telegram_chat_id",""))
        is_prem=user.get("role","free") in ("premium","admin","owner")
        if cat_alerts or (is_prem and has_tg):
            subscribers[email]=(user, cat_alerts if cat_alerts else "all")

    if not subscribers:
        log.info("  No composite subscribers yet (need premium users with Telegram linked)")

    for ticker in SCAN_UNIVERSE:
        log.info(f"  Scanning {ticker}…")
        try:
            q=get_quote(ticker)
            if not q: continue
            tech=get_technicals(ticker); fund=get_fundamentals(ticker); sent=get_sentiment(ticker)
            new_sent[ticker]={"bull":sent.get("bull",50)}

            detectors=[
                ("squeeze",       "💥 Squeeze + Buzz",        detect_squeeze(ticker,q,tech,fund,sent)),
                ("hidden",        "💡 Hidden Mover",           detect_hidden_mover(ticker,q,tech,sent,hot_list)),
                ("sent_flip",     "🌡️ Sentiment Flip",         detect_sentiment_flip(ticker,q,tech,sent,prev_sent)),
                ("breakout",      "⚡ Breakout",               detect_breakout(ticker,q,tech)),
                ("fallen_angel",  "📉→📈 Fallen Angel",       detect_fallen_angel(ticker,q,tech,fund)),
                ("smart_money",   "⚡🧲 Smart Money",          detect_smart_money(ticker,q,tech)),
                ("vol_squeeze",   "🌪️ Volatility Squeeze",    detect_vol_squeeze(ticker,q,tech)),
            ]

            for det_id,cat_name,(triggered,message) in detectors:
                if not triggered: continue
                log.info(f"    ✨ {cat_name}: {ticker}")
                for email,(user,wanted) in subscribers.items():
                    if wanted!="all" and cat_name not in wanted: continue
                    fkey=fire_key(email,f"{ticker}_{det_id}")
                    if already_fired(fkey): continue
                    channels=["telegram"] if user.get("telegram_chat_id") else ["email"]
                    deliver(email,user,f"📊 {cat_name}: {ticker}",message,channels)
                    mark_fired(fkey)

        except Exception as e:
            log.error(f"  Error {ticker}: {traceback.format_exc()}")

    save_json("/tmp/sw_prev_sentiment.json",new_sent)
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
