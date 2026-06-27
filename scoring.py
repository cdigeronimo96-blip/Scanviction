"""
MarketSignalPro — shared scoring & categorization engine
========================================================
Pure (no Streamlit) factor / score / category logic, imported by BOTH the
Streamlit app (app.py) and the background alerts worker (alerts_worker.py) so the
two agree EXACTLY on how a stock is scored and which composite category it belongs
to. Previously app.py and alerts_worker.py had divergent category detectors, so
Discover and the notifications could disagree; this module is the single source of
truth. Depends only on pandas + ta — safe to import anywhere.
"""
import os
import pandas as pd
import ta

# ── Social-sentiment scoring knobs (tune these) ──
# SENT_MIN_MSGS  : below this many mentions, the bull/bear split is treated as
#                  noise (small neutral contribution) instead of being trusted.
# SENT_FULL_MSGS : mention volume at which sentiment carries its full weight.
SENT_MIN_MSGS  = int(os.environ.get("SENT_MIN_MSGS", "10"))
SENT_FULL_MSGS = int(os.environ.get("SENT_FULL_MSGS", "100"))

# Composite category metadata: name -> (description, tier). Each category is
# assigned by a UNIQUE multi-factor fit signature (see COMPOSITE_FIT) and every
# stock lands in only its single best-fit category, so these don't overlap. Keys
# here MUST match COMPOSITE_FIT exactly.
# Ordered FREE-first, then PREMIUM, so the Discover grid groups all unlocked
# categories together at the top and the locked (🔒) ones below — instead of the
# lock icons being scattered through the grid. Display order = dict order.
COMPOSITE_CATS = {
    # ── Free (the hook) ──
    "🌊 Momentum Leaders":     ("Up strongly over 20 days, above both moving averages, RSI in the healthy zone — sustained leadership", "free"),
    "⚡ Momentum Surge":        ("Momentum accelerating fast in the last week with a fresh MACD upturn — an inflection, not a grind", "free"),
    "📉→📈 Oversold Reversal":  ("RSI oversold AND MACD turning back up with price stabilizing — a confirmed bounce setup", "free"),
    "🪂 Fallen Angels":         ("Down 28%+ from its highs but basing as volume returns — a recovery watch, not a falling knife", "free"),
    "🎭 Social Catalyst":       ("Social chatter elevated alongside a volume surge — catalyst-driven attention today", "free"),
    "💎 Value Momentum":        ("Low P/E paired with a rising trend — the rare value-meets-momentum convergence", "free"),
    "🩸 Capitulation Bottom":   ("Deeply oversold AND down hard from its highs while a volume-spike flushes out sellers and money flow turns — a climactic bottom, not a slow base", "free"),
    "💡 Hidden Movers":         ("Solid technical score but little social attention and mid-range — find them before the crowd", "free"),
    # ── Premium (the upsell) ──
    "🏅 Quality Momentum":      ("A profitable, sanely-valued company (real P/E) trending strongly with a confirmed ADX trend and money flowing in — quality that's also moving, not a junk runner", "premium"),
    "🍃 VCP Volume Dry-Up":     ("Price coiling near its highs as volume DRIES UP into a tight range — Minervini's volatility-contraction pattern, primed to break out", "premium"),
    "🏛️ Insider Cluster":       ("Two or more company insiders bought on the open market recently (SEC Form 4, code P) — cluster buying is one of the better-documented signals that people who know the business see value", "premium"),
    "🚀 Breakout Watch":        ("Pressing a new 60-day high on heavy volume — a breakout actually in progress", "premium"),
    "🏆 Relative Strength":     ("Top-decile 20-day return versus the entire market, still above its 50-day — the true outperformers", "premium"),
    "🎯 Pullback Buy":          ("Healthy uptrend that has dipped back to its rising 20-day MA with RSI cooled — a buy-the-dip zone", "premium"),
    "🦈 Quiet Accumulation":    ("Volume quietly rising over a calm, low-volatility climb with steady up-days — stealth accumulation", "premium"),
    "🌪️ Volatility Squeeze":    ("Bollinger-band width compressed to a multi-week low — coiled and waiting for an expansion", "premium"),
    "💥 Volatility Expansion":  ("A large move on 2×+ volume with volatility spiking — range expansion, momentum igniting now", "premium"),
    "🔥 Short Squeeze":         ("High days-to-cover from real FINRA short interest, with upward momentum — genuine squeeze fuel (not a technical proxy)", "premium"),
    "⚡🧲 Smart-Money Squeeze":  ("Heavily shorted (high days-to-cover) AND big money quietly accumulating (positive Chaikin money flow) WITH momentum — a squeeze that smart money is already behind. Three independent data sources at once.", "premium"),
    "🎪 Catalyst / Gap":        ("Gapped 3.5%+ on heavy volume — a likely news or event catalyst in play", "premium"),
    # ── Bearish / short setups (direction = bear; for short-sellers & hedgers) ──
    "📉 Breakdown":             ("Breaking to a fresh 60-day LOW on heavy volume, below both moving averages — a bearish breakdown / short setup", "premium"),
    "🐻 Distribution":          ("Volume rising while price falls and money flows OUT (negative Chaikin money flow) — institutional distribution, a short setup", "premium"),
    "🔻 Overbought Fade":       ("Stretched and overbought (high RSI) with momentum rolling over near a high — a short-the-rip / mean-reversion-down setup", "premium"),
}

# Direction of each category: most are LONG/bullish; the three above are SHORT/bearish.
# Lets the UI label short setups and score them with bear_conviction instead of the
# (bullish) conviction_score. Anything not listed defaults to "bull".
COMPOSITE_DIR = {
    "📉 Breakdown": "bear", "🐻 Distribution": "bear", "🔻 Overbought Fade": "bear",
}

def category_dir(cat):
    return COMPOSITE_DIR.get(cat, "bull")


def compute_scores(df, info=None, sent=None):
    if df is None or len(df) < 14: return 0, {}, "N/A", "Unknown", "Low"
    bd = {}; total = 0
    try:
        dfc = df.copy()
        dfc["rsi"] = ta.momentum.RSIIndicator(dfc["close"], 14).rsi()
        dfc["ma20"] = dfc["close"].rolling(20).mean()
        dfc["ma50"] = dfc["close"].rolling(min(50, len(dfc))).mean()
        mac = ta.trend.MACD(dfc["close"]); dfc["macd"] = mac.macd(); dfc["macd_s"] = mac.macd_signal()
        lat = dfc.iloc[-1]; rsi = lat["rsi"]; price = lat["close"]
        if pd.notna(rsi):
            rs = 25 if rsi < 30 else 20 if rsi < 40 else 18 if rsi <= 55 else 12 if rsi <= 70 else 4
            total += rs; bd["Momentum"] = rs
        if pd.notna(lat["ma20"]) and pd.notna(lat["ma50"]):
            ts = 0
            if price > lat["ma20"]: ts += 8
            if price > lat["ma50"]: ts += 8
            if lat["ma20"] > lat["ma50"]: ts += 4
            total += ts; bd["Trend"] = ts
        if pd.notna(lat["macd"]) and pd.notna(lat["macd_s"]):
            ms = 15 if (lat["macd"] > lat["macd_s"] and lat["macd"] > 0) else 9 if lat["macd"] > lat["macd_s"] else 4 if lat["macd"] > 0 else 0
            total += ms; bd["MACD"] = ms
        if "volume" in dfc.columns:
            avg = dfc["volume"].rolling(20).mean().iloc[-1]
            if pd.notna(avg) and avg > 0:
                r = lat["volume"] / avg
                vs = 15 if r >= 3 else 11 if r >= 2 else 7 if r >= 1.5 else 4 if r >= 1 else 1
                total += vs; bd["Volume"] = vs
        if sent:
            bp = sent.get("bull", 50); msgs = sent.get("msgs", 0) or 0
            # Confidence-gated, volume-weighted sentiment. A bull% computed from a
            # handful of mentions is noise — below SENT_MIN_MSGS we don't trust the
            # split and contribute a small neutral amount. Above it, the raw score
            # is scaled by mention volume (ramps 0.5→1.0 over MIN→FULL).
            if msgs < SENT_MIN_MSGS:
                ss = 3
            else:
                base = 15 if bp >= 75 else 10 if bp >= 60 else 6 if bp >= 50 else 2
                vw = min(1.0, 0.5 + 0.5 * (msgs - SENT_MIN_MSGS) / max(1, SENT_FULL_MSGS - SENT_MIN_MSGS))
                ss = round(base * vw)
            total += ss; bd["Sentiment"] = ss
        if info:
            sf = (info.get("sf", 0) or 0) * 100; dt = info.get("dtc", 0) or 0
            # Credit real FINRA days-to-cover (dt) even when short-float % (sf) isn't
            # loaded — dt is the academically stronger squeeze predictor.
            sq = (10 if (sf >= 20 and dt >= 5) else 8 if dt >= 8 else 6 if (sf >= 15 or dt >= 5)
                  else 3 if (sf >= 10 or dt >= 3) else 0)
            total += sq; bd["Squeeze"] = sq
    except: pass
    sc = min(int(total), 100)
    if bd.get("Squeeze", 0) >= 6 and bd.get("Momentum", 0) >= 15: op = "Short Squeeze Setup"
    elif bd.get("Momentum", 0) == 25: op = "Oversold Bounce"
    elif bd.get("Trend", 0) >= 18:    op = "Uptrend"
    elif bd.get("Volume", 0) >= 11:   op = "Volume Surge"
    elif bd.get("MACD", 0) == 15:     op = "MACD Breakout"
    else:                             op = "Watch"
    try:
        vs = df["close"].pct_change().std() * 100; beta = info.get("beta", 1) or 1 if info else 1
        sf = (info.get("sf", 0) or 0) * 100 if info else 0; mc = info.get("mktcap", 0) or 0 if info else 0
        rs = 0
        if beta > 2: rs += 3
        elif beta > 1.5: rs += 2
        elif beta > 1: rs += 1
        if vs > 4: rs += 3
        elif vs > 2: rs += 2
        elif vs > 1: rs += 1
        if sf > 20: rs += 2
        elif sf > 10: rs += 1
        if mc < 500e6: rs += 2
        elif mc < 2e9: rs += 1
        risk = "Very High" if rs >= 6 else "High" if rs >= 4 else "Medium" if rs >= 2 else "Low"
    except: risk = "Unknown"
    return sc, bd, op, risk, ("High" if sc >= 65 else "Medium" if sc >= 40 else "Low")


# ─────────────────────────────────────────────────────────────
# RICH FACTOR ENGINE  +  UNIQUE (NON-OVERLAPPING) CATEGORIES
# ─────────────────────────────────────────────────────────────
def _cl(v, lo, hi):
    try: return max(lo, min(hi, float(v)))
    except Exception: return lo


def compute_factors(df):
    """Flat dict of technical factors from a >=20-row OHLCV frame. Each indicator
    is computed ONCE. Numeric keys default to safe neutral values so callers need
    no None-checks (rel_strength stays None until assign_categories fills it from
    the universe-wide return distribution)."""
    f = {"rsi": 50.0, "trend_align": 0, "macd_state": 0, "vol_ratio": 1.0,
         "roc5": 0.0, "roc10": 0.0, "roc20": 0.0, "accel": 0.0,
         "near_high": False, "new_high": False, "pct_from_high": 0.0,
         "drawdown": 0.0, "range_pos": 0.5, "atr_pct": 0.0, "bb_squeeze": 0.0,
         "vol_trend": 1.0, "up_days": 0, "above_ma20": False, "above_ma50": False,
         "ma20_slope": 0.0, "gap": 0.0, "dist_ma20": 0.0, "rel_strength": None,
         "mfi": 50.0, "cmf": 0.0, "adx": 0.0, "obv_slope": 0.0}
    try:
        if df is None or len(df) < 20:
            return f
        close = df["close"].astype(float).reset_index(drop=True)
        high = df["high"].astype(float).reset_index(drop=True) if "high" in df.columns else close
        low  = df["low"].astype(float).reset_index(drop=True)  if "low"  in df.columns else close
        vol  = df["volume"].astype(float).reset_index(drop=True) if "volume" in df.columns else None
        n = len(close); price = float(close.iloc[-1])
        rsi = ta.momentum.RSIIndicator(close, 14).rsi()
        if pd.notna(rsi.iloc[-1]): f["rsi"] = float(rsi.iloc[-1])
        ma20 = close.rolling(20).mean(); ma50 = close.rolling(min(50, n)).mean()
        m20 = float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else price
        m50 = float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else price
        f["above_ma20"] = price > m20; f["above_ma50"] = price > m50
        f["trend_align"] = (1 if price>m20 else 0)+(1 if price>m50 else 0)+(1 if m20>m50 else 0)
        f["dist_ma20"] = (price-m20)/m20*100 if m20 else 0.0
        if n >= 25 and pd.notna(ma20.iloc[-5]) and float(ma20.iloc[-5]):
            f["ma20_slope"] = (m20-float(ma20.iloc[-5]))/float(ma20.iloc[-5])*100
        mac = ta.trend.MACD(close); ml = mac.macd(); ms = mac.macd_signal()
        if pd.notna(ml.iloc[-1]) and pd.notna(ms.iloc[-1]):
            up = bool(ml.iloc[-1] > ms.iloc[-1])
            cross = up and n>1 and pd.notna(ml.iloc[-2]) and pd.notna(ms.iloc[-2]) and bool(ml.iloc[-2] <= ms.iloc[-2])
            f["macd_state"] = 3 if cross else 2 if (up and ml.iloc[-1]>0) else 1 if up else 0
        def _roc(k):
            return (price-float(close.iloc[-k-1]))/float(close.iloc[-k-1])*100 if (n>k and float(close.iloc[-k-1])) else 0.0
        f["roc5"], f["roc10"], f["roc20"] = _roc(5), _roc(10), _roc(20)
        f["accel"] = f["roc5"] - f["roc20"]/4.0
        win = min(60, n); seg = close.iloc[-win:]
        h = float(seg.max()); lo = float(seg.min())
        f["pct_from_high"] = (price-h)/h*100 if h else 0.0
        f["near_high"] = bool(price >= 0.97*h)
        f["new_high"]  = bool(price >= h*0.999)
        f["range_pos"] = (price-lo)/(h-lo) if h>lo else 0.5
        w90 = min(90, n); h90 = float(close.iloc[-w90:].max())
        f["drawdown"] = (price-h90)/h90*100 if h90 else 0.0
        tr = (high-low).rolling(14).mean()
        if pd.notna(tr.iloc[-1]) and price: f["atr_pct"] = float(tr.iloc[-1])/price*100
        bb = ta.volatility.BollingerBands(close); wb = bb.bollinger_wband().dropna()
        if len(wb) >= 20:
            cur = float(wb.iloc[-1]); recent = wb.iloc[-min(60,len(wb)):]
            f["bb_squeeze"] = 1.0 - float((recent < cur).mean())
        if vol is not None and n >= 20:
            a20 = float(vol.rolling(20).mean().iloc[-1])
            f["vol_ratio"] = float(vol.iloc[-1])/a20 if a20>0 else 1.0
            r5 = float(vol.iloc[-5:].mean()); pr = float(vol.iloc[-20:-5].mean())
            f["vol_trend"] = r5/pr if pr>0 else 1.0
            # Money-flow factors (free, volume-weighted): MFI = volume-weighted RSI;
            # CMF (Chaikin Money Flow, -1..1) = buying vs selling pressure. CMF>0 =
            # accumulation. These capture institutional flow most retail screens miss.
            try:
                mfi = ta.volume.MFIIndicator(high, low, close, vol, 14).money_flow_index()
                if pd.notna(mfi.iloc[-1]): f["mfi"] = float(mfi.iloc[-1])
                cmf = ta.volume.ChaikinMoneyFlowIndicator(high, low, close, vol, min(20, n)).chaikin_money_flow()
                if pd.notna(cmf.iloc[-1]): f["cmf"] = float(cmf.iloc[-1])
                # OBV slope: net On-Balance-Volume change over 10 bars, in units of
                # 10×avg-daily-volume (~ -1..1) — positive = accumulation.
                obv = ta.volume.OnBalanceVolumeIndicator(close, vol).on_balance_volume()
                if len(obv) >= 11:
                    avgv = float(vol.iloc[-20:].mean())
                    if avgv > 0:
                        f["obv_slope"] = (float(obv.iloc[-1]) - float(obv.iloc[-11])) / (avgv * 10)
            except Exception:
                pass
        # ADX: trend STRENGTH (0-100; >25 = strong directional trend, <18 = chop).
        # Lets categories require a *real* trend, not random drift.
        try:
            adx = ta.trend.ADXIndicator(high, low, close, 14).adx()
            if pd.notna(adx.iloc[-1]): f["adx"] = float(adx.iloc[-1])
        except Exception:
            pass
        chg = close.diff()
        f["up_days"] = int((chg.iloc[-10:] > 0).sum())
        if "open" in df.columns and n>=2:
            o = float(df["open"].iloc[-1]); pc = float(close.iloc[-2])
            f["gap"] = (o-pc)/pc*100 if pc else 0.0
    except Exception:
        pass
    return f


def _feat_from_row(row):
    """Flatten a scored row (factors + score breakdown + sentiment + fundamentals
    + trending flag) into one dict the category fit functions read."""
    f = dict(row.get("factors") or {})
    bd = row.get("bd") or {}; sent = row.get("sent") or {}; info = row.get("info") or {}
    f["sc"]     = row.get("sc", 0) or 0
    f["vol_bd"] = bd.get("Volume", 0) or 0
    f["msgs"]   = sent.get("msgs", 0) or 0
    f["buzz"]   = sent.get("buzz_trend", 0) or 0
    f["sf"]     = (info.get("sf", 0) or 0) * 100
    f["dtc"]    = info.get("dtc", 0) or 0          # real FINRA days-to-cover (bulk)
    f["pe"]     = info.get("pe", None)
    f["mktcap"] = info.get("mktcap", 0) or 0
    f["in_hot"] = bool(row.get("hot"))
    f["insider_buys"]  = info.get("insider_buys", 0) or 0   # SEC Form 4 open-market buys (code P)
    f["insider_value"] = info.get("insider_value", 0.0) or 0.0
    f["has_8k"] = bool(info.get("has_8k"))                  # fresh SEC 8-K (material-event catalyst)
    for k, d in (("rsi",50.0),("roc5",0.0),("roc10",0.0),("roc20",0.0),("accel",0.0),
                 ("trend_align",0),("macd_state",0),("vol_ratio",1.0),("vol_trend",1.0),
                 ("atr_pct",0.0),("bb_squeeze",0.0),("dist_ma20",0.0),("ma20_slope",0.0),
                 ("drawdown",0.0),("range_pos",0.5),("up_days",0),("gap",0.0),("dtc",0.0),
                 ("mfi",50.0),("cmf",0.0),("adx",0.0),("obv_slope",0.0),("svr",0.0),
                 ("insider_buys",0),("insider_value",0.0)):
        f.setdefault(k, d)
    f.setdefault("has_8k", False)
    for k in ("near_high","new_high","above_ma20","above_ma50"): f.setdefault(k, False)
    f.setdefault("rel_strength", None)
    return f


CATEGORY_MIN_FIT = 8.0   # below this best-fit score, a stock matches NO category

# Each fit() weights its SIGNATURE factor so the argmax (primary category) reflects
# the stock's dominant character. Returns 0 when the stock fails the signature gate.
COMPOSITE_FIT = {
  "🌊 Momentum Leaders": lambda f: (
      _cl(f["roc20"],0,40) + f["trend_align"]*8 + (10 if 50<=f["rsi"]<=72 else 0) + _cl(f["adx"]-18,0,40)*0.4
      if (f["above_ma20"] and f["above_ma50"] and f["roc20"]>6 and not f["new_high"] and f["rsi"]<75) else 0),
  "⚡ Momentum Surge": lambda f: (
      _cl(f["accel"],0,30)*1.6 + f["macd_state"]*6 + _cl(f["roc5"],0,20)
      if (f["accel"]>3 and f["macd_state"]>=2 and f["roc5"]>2) else 0),
  "🚀 Breakout Watch": lambda f: (
      _cl(f["vol_ratio"]-1,0,6)*15 + 15 + f["trend_align"]*4
      if (f["new_high"] and f["vol_ratio"]>=1.4 and f["above_ma20"]) else 0),
  "🏆 Relative Strength": lambda f: (
      (f["rel_strength"] or 0)*70 + f["trend_align"]*6
      if (f["rel_strength"] is not None and f["rel_strength"]>=0.88 and f["above_ma50"]) else 0),
  "🎯 Pullback Buy": lambda f: (
      _cl(40-abs(f["dist_ma20"])*6,0,40) + _cl(f["ma20_slope"],0,10)*2 + 8
      if (f["above_ma50"] and f["ma20_slope"]>0.3 and abs(f["dist_ma20"])<3.5 and 40<=f["rsi"]<=58 and not f["new_high"] and f["drawdown"]>-20) else 0),
  "🦈 Quiet Accumulation": lambda f: (
      _cl(f["cmf"],0,0.35)*70 + (f["vol_trend"]-1)*20 + f["up_days"]*2 + _cl(6-f["atr_pct"],0,6)*2
      if (f["cmf"]>0.05 and f["vol_trend"]>1.1 and f["up_days"]>=5 and f["above_ma20"] and not f["new_high"]) else 0),
  "📉→📈 Oversold Reversal": lambda f: (
      (40-f["rsi"])*2.2 + f["macd_state"]*7 + 6
      if (f["rsi"]<38 and f["macd_state"]>=1 and f["roc5"]>-3) else 0),
  "🪂 Fallen Angels": lambda f: (
      _cl(-f["drawdown"],0,80) + (f["vol_trend"]-1)*18
      if (f["drawdown"]<=-28 and f["rsi"]<50 and f["vol_trend"]>1.05) else 0),
  "🌪️ Volatility Squeeze": lambda f: (
      f["bb_squeeze"]*55 + _cl(4-f["atr_pct"],0,4)*5
      if (f["bb_squeeze"]>=0.82 and f["atr_pct"]<4) else 0),
  "💥 Volatility Expansion": lambda f: (
      _cl(f["vol_ratio"],0,8)*9 + _cl(abs(f["roc5"]),0,30) + _cl(f["atr_pct"],0,15)*2
      if (f["vol_ratio"]>=2 and abs(f["roc5"])>=8) else 0),
  "🔥 Short Squeeze": lambda f: (
      _cl(f["dtc"],0,15)*5 + _cl(f["roc10"],0,25) + _cl(f["svr"]-40,0,30)*0.5 + (10 if f["in_hot"] else 0)
      if (f["dtc"]>=4 and f["roc10"]>-8) else 0),
  "⚡🧲 Smart-Money Squeeze": lambda f: (
      _cl(f["dtc"],0,15)*4 + _cl(f["cmf"],0,0.4)*55 + _cl(f["roc10"],0,20) + _cl(f["svr"]-45,0,25)*0.4
      if (f["dtc"]>=5 and f["cmf"]>0.08 and f["roc10"]>0) else 0),
  "🎭 Social Catalyst": lambda f: (
      _cl(f["msgs"],0,300)*0.18 + f["vol_bd"]*1.5 + (20 if f["in_hot"] else 0) + _cl(f["buzz"],0,100)*0.3
      if ((f["msgs"]>=SENT_MIN_MSGS or f["in_hot"]) and f["vol_ratio"]>=1.3) else 0),
  "🎪 Catalyst / Gap": lambda f: (
      _cl(abs(f["gap"]),0,25)*4 + _cl(f["vol_ratio"],0,8)*8 + (12 if f["has_8k"] else 0)
      if (abs(f["gap"])>=3.5 and f["vol_ratio"]>=1.5) else 0),
  "💎 Value Momentum": lambda f: (
      (25-(f["pe"] or 99)) + f["trend_align"]*7 + _cl(f["roc20"],0,15)
      if (f["pe"] is not None and 0<f["pe"]<22 and f["above_ma20"] and f["roc20"]>0) else 0),
  # Quality that's ALSO moving: a profitable, sanely-valued name (P/E loaded) in a
  # *confirmed* strong trend (ADX) with money flowing in. Distinct from Value Momentum
  # (deep-cheap, P/E<22, no trend-strength gate) and Momentum Leaders (pure technical,
  # no fundamentals) — this one needs earnings quality + ADX + CMF all at once.
  "🏅 Quality Momentum": lambda f: (
      _cl(f["adx"]-20,0,40)*1.3 + _cl(f["roc20"],0,30) + f["trend_align"]*5 + _cl(f["cmf"],0,0.3)*40
      + (12 if (f["pe"] and f["pe"]<25) else 6)
      if (f["pe"] is not None and 8<=f["pe"]<=45 and f["adx"]>=23 and f["roc20"]>5
          and f["above_ma50"] and f["cmf"]>0) else 0),
  # Climactic capitulation low: deep drawdown AND deeply oversold WHILE a volume spike
  # flushes out sellers and money flow stops bleeding. Distinct from Fallen Angels
  # (slow base, no oversold/spike gate) and Oversold Reversal (mild dip, no drawdown/
  # capitulation-volume gate) — the signature is the volume-spike washout at an extreme.
  "🩸 Capitulation Bottom": lambda f: (
      _cl(-f["drawdown"]-25,0,55)*0.7 + (33-f["rsi"])*1.6 + _cl(f["vol_ratio"]-1.5,0,5)*7 + _cl(f["cmf"]+0.1,0,0.3)*30
      if (f["drawdown"]<=-25 and f["rsi"]<33 and f["vol_ratio"]>=1.8 and f["roc5"]>-13) else 0),
  # Volatility Contraction Pattern (Minervini): price coils near its highs while volume
  # DRIES UP into an ever-tighter range — the textbook pre-breakout. Distinct from
  # Volatility Squeeze (band compression anywhere, mid-range OK, no volume-dry-up) and
  # Breakout Watch (already broke out on a volume *surge*): VCP demands volume CONTRACTING
  # near the high, coiled but not yet launched.
  "🍃 VCP Volume Dry-Up": lambda f: (
      f["bb_squeeze"]*38 + _cl((0.95-f["vol_trend"])*60,0,30) + _cl(f["range_pos"]-0.6,0,0.4)*40 + _cl(5-f["atr_pct"],0,5)*3
      if (f["bb_squeeze"]>=0.6 and f["vol_trend"]<0.95 and f["range_pos"]>=0.62
          and f["atr_pct"]<5 and f["above_ma50"] and not f["new_high"]) else 0),
  # Insider cluster buying (SEC Form 4, open-market purchases, code P). Two+ insiders
  # buying their own stock on the open market is a genuinely independent, well-documented
  # edge — a different DATA SOURCE entirely (EDGAR), so it never collides with the
  # technical categories on its signature. Bigger clusters / larger dollars score higher.
  "🏛️ Insider Cluster": lambda f: (
      22 + _cl(f["insider_buys"],2,8)*9 + _cl(f["insider_value"]/1e5,0,25) + (8 if f["roc20"]>-6 else 0)
      if (f["insider_buys"]>=2) else 0),
  "💡 Hidden Movers": lambda f: (
      f["sc"] - f["msgs"]*0.2 - (30 if f["in_hot"] else 0) - (25 if f["near_high"] else 0)
      if (f["sc"]>=48 and f["msgs"]<SENT_MIN_MSGS and not f["in_hot"] and not f["near_high"] and 0.2<f["range_pos"]<0.85) else 0),
  # ── Bearish / short setups — the inverse of the breakout/accumulation/oversold longs.
  # A stock that's genuinely weak fails the bullish gates (they require above-MA / positive
  # momentum), so the argmax naturally routes it here. ──
  # Bearish breakdown: pressing a fresh 60-day LOW on heavy volume, below the MAs.
  "📉 Breakdown": lambda f: (
      _cl(f["vol_ratio"]-1,0,6)*13 + 14 + (3-f["trend_align"])*4 + _cl(-f["roc10"],0,25)*0.5
      if (f["range_pos"]<=0.08 and f["vol_ratio"]>=1.4 and not f["above_ma20"] and f["roc10"]<-2) else 0),
  # Distribution: rising volume on a DECLINE with money flowing OUT (negative CMF) — the
  # mirror of Quiet Accumulation.
  "🐻 Distribution": lambda f: (
      _cl(-f["cmf"],0,0.35)*70 + (f["vol_trend"]-1)*20 + (10-f["up_days"])*2 + _cl(-f["roc10"],0,20)*0.5
      if (f["cmf"]<-0.05 and f["vol_trend"]>1.1 and not f["above_ma20"] and f["roc10"]<0) else 0),
  # Overbought fade: stretched/overbought with momentum rolling over near a high — short
  # the rip. The mirror of Oversold Reversal.
  "🔻 Overbought Fade": lambda f: (
      (f["rsi"]-65)*2.2 + (3-f["macd_state"])*5 + _cl(-f["accel"],0,30)
      if (f["rsi"]>=70 and f["macd_state"]<=1 and f["accel"]<0 and f["above_ma20"]) else 0),
}


def _category_why(cat, f):
    rsi=f.get("rsi",50); roc20=f.get("roc20",0); roc5=f.get("roc5",0); vr=f.get("vol_ratio",1)
    rs=f.get("rel_strength"); dd=f.get("drawdown",0); vt=f.get("vol_trend",1); pe=f.get("pe")
    W = {
      "🌊 Momentum Leaders":     f"Up {roc20:+.0f}% over 20d, above both MAs, RSI {rsi:.0f} — healthy sustained trend",
      "⚡ Momentum Surge":        f"Accelerating ({roc5:+.0f}% in 5d) with a fresh MACD upturn",
      "🚀 Breakout Watch":        f"New 60-day high on {vr:.1f}× volume — breakout underway",
      "🏆 Relative Strength":     (f"Top {max(1,round((1-(rs or 0))*100))}% performer vs the market" if rs is not None else "Outperforming the market"),
      "🎯 Pullback Buy":          f"Uptrend pulling back near its 20-day MA (RSI {rsi:.0f}) — dip-buy zone",
      "🦈 Quiet Accumulation":    f"Volume rising {vt:.1f}× on a quiet, steady climb — accumulation",
      "📉→📈 Oversold Reversal":  f"RSI oversold at {rsi:.0f} with MACD turning up — bounce setup",
      "🪂 Fallen Angels":         f"Down {dd:.0f}% from highs but basing with volume returning",
      "🌪️ Volatility Squeeze":    "Volatility compressed to a multi-week low — coiled for a move",
      "💥 Volatility Expansion":  f"{vr:.1f}× volume on a {roc5:+.0f}% move — range expanding",
      "🔥 Short Squeeze":         f"{f.get('dtc',0):.1f} days-to-cover (real FINRA short interest) with upward momentum — genuine squeeze fuel",
      "⚡🧲 Smart-Money Squeeze":  f"{f.get('dtc',0):.1f}-day cover + money flowing IN (CMF {f.get('cmf',0):+.2f}) on momentum — squeeze with smart money behind it",
      "🎭 Social Catalyst":       f"Social chatter elevated with {vr:.1f}× volume — catalyst in play",
      "🎪 Catalyst / Gap":        (f"Gapped {f.get('gap',0):+.0f}% on {vr:.1f}× volume with a fresh SEC 8-K — confirmed news/event" if f.get("has_8k") else f"Gapped {f.get('gap',0):+.0f}% on {vr:.1f}× volume — likely news/event"),
      "💎 Value Momentum":        f"Low P/E ({(pe or 0):.0f}×) with a rising trend — value meets momentum",
      "🏅 Quality Momentum":      f"P/E {(pe or 0):.0f}× and up {roc20:+.0f}% on a confirmed trend (ADX {f.get('adx',0):.0f}) with money flowing in — quality that's moving",
      "🩸 Capitulation Bottom":   f"Down {dd:.0f}% and RSI {rsi:.0f} (deeply oversold) on a {vr:.1f}× volume washout — sellers flushing out",
      "🍃 VCP Volume Dry-Up":     f"Coiled near its highs as volume dries up ({vt:.1f}× and falling) into a tight range — primed to break out",
      "🏛️ Insider Cluster":       f"{int(f.get('insider_buys',0))} insiders bought on the open market (~${f.get('insider_value',0)/1e3:.0f}K, SEC Form 4) — cluster buying",
      "💡 Hidden Movers":         f"Score {f.get('sc',0)} with little social attention yet — early discovery",
      "📉 Breakdown":             f"At a fresh 60-day low on {vr:.1f}× volume, below its MAs — bearish breakdown (short)",
      "🐻 Distribution":          f"Money flowing OUT (CMF {f.get('cmf',0):+.2f}) on rising volume into weakness — distribution (short)",
      "🔻 Overbought Fade":       f"Overbought (RSI {rsi:.0f}) and rolling over near a high — short-the-rip setup",
    }
    return W.get(cat, "MarketSignalPro composite signal")


def bear_conviction(feat):
    """The SHORT-side counterpart to conviction_score — a 0-100 number where HIGHER =
    a stronger bearish/short setup. Blends downtrend technicals, distribution (money
    flowing out), relative weakness vs the market and trend persistence (ADX). Used for
    categories whose direction is 'bear' so a strong short doesn't read as a weak long.
    Returns (score:int, breakdown:[(label, sub_0_100, weight)])."""
    comps = []
    dn = (3 - (feat.get("trend_align", 0) or 0)) / 3 * 55 + _cl(-(feat.get("roc20", 0) or 0), 0, 30) * 1.5
    comps.append(("Downtrend", _cl(dn, 0, 100), 0.34))
    comps.append(("Distribution", _cl((-(feat.get("cmf", 0.0) or 0.0) + 0.05) * 330, 0, 100), 0.24))
    rs = feat.get("rel_strength")
    if rs is not None:
        comps.append(("Relative Weakness", _cl((1 - rs) * 100, 0, 100), 0.24))
    adx = feat.get("adx", 0.0) or 0.0
    if adx > 0:
        comps.append(("Trend Strength", _cl(adx * 2.2, 0, 100), 0.18))
    tw = sum(w for _, _, w in comps)
    score = int(round(sum(s * w for _, s, w in comps) / tw)) if tw else 0
    return score, comps


def category_for_feat(feat):
    """Return (primary_category, fit_score) — the single best-fit category, or
    (None, 0) if nothing clears CATEGORY_MIN_FIT."""
    best, bestfit = None, 0.0
    for cat, fn in COMPOSITE_FIT.items():
        try: fit = float(fn(feat))
        except Exception: fit = 0.0
        if fit > bestfit:
            bestfit, best = fit, cat
    return (best, bestfit) if (best and bestfit >= CATEGORY_MIN_FIT) else (None, 0.0)


def conviction_score(feat):
    """MarketSignalPro CONVICTION — one proprietary 0-100 number that blends several
    INDEPENDENT edges, each scored 0-100 then weighted: Technical, Money Flow (CMF),
    Relative Strength (vs the whole market), Trend Strength (ADX), Squeeze Fuel
    (days-to-cover) and Valuation (P/E). Components with no data (P/E or short interest
    before backfill, rel-strength before the universe pass) drop out and the remaining
    weights re-normalize, so partial-data names aren't unfairly penalized. Every input
    is data we already pull. Returns (score:int, breakdown:[(label, sub_0_100, weight)])."""
    comps = []
    sc = feat.get("sc", 0) or 0
    comps.append(("Technical", _cl(sc * 1.15, 0, 100), 0.30))
    comps.append(("Money Flow", _cl((feat.get("cmf", 0.0) + 0.15) * 330, 0, 100), 0.20))
    rs = feat.get("rel_strength")
    if rs is not None:
        comps.append(("Relative Strength", _cl(rs * 100, 0, 100), 0.20))
    adx = feat.get("adx", 0.0) or 0.0
    if adx > 0:
        comps.append(("Trend Strength", _cl(adx * 2.2, 0, 100), 0.10))
    dtc = feat.get("dtc", 0.0) or 0.0
    if dtc > 0:
        comps.append(("Squeeze Fuel", _cl(dtc * 7, 0, 100), 0.12))
    pe = feat.get("pe")
    if pe is not None and pe > 0:
        val = 92 if pe < 12 else 72 if pe < 20 else 52 if pe < 30 else 32 if pe < 50 else 15
        comps.append(("Valuation", val, 0.12))
    ins = feat.get("insider_buys", 0) or 0
    if ins > 0:
        # Open-market insider buying is an independent, fundamentally-informed edge:
        # one buy is a positive, a cluster (2+) is a strong vote of confidence.
        comps.append(("Insider Buying", _cl(45 + ins * 22, 0, 100), 0.14))
    tw = sum(w for _, _, w in comps)
    score = int(round(sum(s * w for _, s, w in comps) / tw)) if tw else 0
    return score, comps


def assign_categories(rows):
    """One pass over the warm universe: fill each row's relative-strength percentile
    (vs the whole universe's 20-day returns), then assign its single best-fit
    primary category. Sets row['primary_cat'], row['comp'] (fit), row['why']."""
    import bisect
    if not rows:
        return
    for r in rows:
        if not r.get("factors"):
            r["factors"] = compute_factors(r.get("df"))
    srt = sorted((r["factors"].get("roc20", 0.0) or 0.0) for r in rows)
    nn = len(srt)
    for r in rows:
        roc = r["factors"].get("roc20", 0.0) or 0.0
        r["factors"]["rel_strength"] = (bisect.bisect_left(srt, roc) / nn) if nn else 0.5
        feat = _feat_from_row(r)
        cat, fit = category_for_feat(feat)
        r["primary_cat"] = cat
        r["comp"] = fit
        r["why"] = _category_why(cat, feat) if cat else ""
        r["direction"] = category_dir(cat) if cat else "bull"
        if r["direction"] == "bear":
            r["conviction"], r["conviction_breakdown"] = bear_conviction(feat)
        else:
            r["conviction"], r["conviction_breakdown"] = conviction_score(feat)
