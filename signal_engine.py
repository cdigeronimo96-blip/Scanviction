"""
StockWins — Signal Performance Engine v2
==========================================
Tracks every proprietary signal trigger and computes:
  • 1d / 3d / 5d / 10d / 20d returns
  • Max upside and max drawdown since trigger
  • Options P&L estimates (calls and puts)
  • "What would you have made?" for any $ amount
  • Category win-rate and avg-return aggregates
  • Confidence score (data quality + agreement)
  • Setup lifecycle stages
  • Market regime at trigger
"""

import json, os, time, math
from datetime import datetime, timedelta
from typing import Optional


# ── Shared storage: use the same Postgres/file layer as the app & worker so
#    signal history survives reboots and is visible across all components. ──
try:
    import msp_store as _store
    SIGNAL_HISTORY_PATH = _store.SIGNAL_HISTORY_PATH
    SIGNAL_PERF_CACHE   = _store.SIGNAL_PERF_PATH
    _HAS_STORE = True
except Exception:
    SIGNAL_HISTORY_PATH = "/tmp/msp_signal_history.json"
    SIGNAL_PERF_CACHE   = "/tmp/msp_signal_perf_cache.json"
    _HAS_STORE = False


# ─────────────────────────────────────────────────────────────
# I/O HELPERS  (delegate to the shared store when available)
# ─────────────────────────────────────────────────────────────
def _read_json(path: str, default):
    if _HAS_STORE:
        try:
            return _store.read_json(path, default)
        except Exception:
            return default
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data):
    if _HAS_STORE:
        try:
            _store.write_json(path, data)
            return
        except Exception:
            pass
    try:
        with open(path, "w") as f:
            json.dump(data, f, default=str)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# CONFIDENCE ENGINE
# ─────────────────────────────────────────────────────────────
# Minimum social mentions before the bull/bear split is trusted. Mirrors the
# app's SENT_MIN_MSGS (same env var + default) so scoring and confidence agree:
# below this, sentiment is treated as noise and contributes nothing.
SENT_MIN_MSGS = int(os.environ.get("SENT_MIN_MSGS", "10"))

def compute_confidence(score_components: dict, info: dict, sent: dict, df) -> dict:
    """
    Returns a confidence dict:
      score       - 0-100 raw score
      confidence  - Low / Medium / High / Very High
      risk        - Low / Medium / High / Very High
      factors     - list of contributing factors
    """
    factors = []
    penalty = 0

    # Data completeness
    completeness = sum([
        1 if score_components.get("Momentum") is not None else 0,
        1 if score_components.get("Trend") is not None else 0,
        1 if score_components.get("MACD") is not None else 0,
        1 if score_components.get("Volume") is not None else 0,
        1 if sent and sent.get("bull") is not None else 0,
        1 if info and info.get("sf") is not None else 0,
    ]) / 6
    if completeness < 0.6:
        penalty += 20; factors.append("⚠️ Incomplete data")
    elif completeness < 0.9:
        penalty += 8; factors.append("📊 Partial data")
    else:
        factors.append("✅ Full data coverage")

    # Component agreement (how many are bullish)
    bullish_components = sum([
        1 if score_components.get("Momentum", 0) >= 15 else 0,
        1 if score_components.get("Trend", 0) >= 14 else 0,
        1 if score_components.get("MACD", 0) >= 9 else 0,
        1 if score_components.get("Volume", 0) >= 7 else 0,
        1 if sent and sent.get("bull", 0) >= 55 and (sent.get("msgs", 0) or 0) >= SENT_MIN_MSGS else 0,
    ])
    if bullish_components >= 4:
        factors.append("✅ Strong signal agreement (4-5 components)")
    elif bullish_components >= 3:
        factors.append("🟡 Moderate signal agreement (3 components)")
        penalty += 5
    else:
        factors.append("⚠️ Weak signal agreement (1-2 components)")
        penalty += 15

    # Trend persistence (is price above MAs?)
    try:
        lat = df.iloc[-1]
        if "ma20" in df.columns and "ma50" in df.columns:
            if lat["close"] > lat.get("ma20", 0) and lat["close"] > lat.get("ma50", 0):
                factors.append("✅ Price above MA20 and MA50")
            elif lat["close"] > lat.get("ma20", 0):
                factors.append("🟡 Price above MA20 only")
                penalty += 5
            else:
                factors.append("⚠️ Price below moving averages")
                penalty += 12
    except Exception:
        pass

    # Sentiment stability — only when there's enough social volume to trust the
    # split (below SENT_MIN_MSGS mentions the bull/bear ratio is noise, so it
    # contributes neither a bonus nor a penalty; consistent with compute_scores).
    if sent and (sent.get("msgs", 0) or 0) >= SENT_MIN_MSGS:
        bull = sent.get("bull", 50)
        msgs = sent.get("msgs", 0)
        if bull >= 65 and msgs >= 20:
            factors.append("✅ Strong positive sentiment with volume")
        elif bull >= 55:
            factors.append("🟡 Moderate bullish sentiment")
            penalty += 3
        elif bull < 40:
            factors.append("⚠️ Bearish sentiment")
            penalty += 10

    # Liquidity check (volume ratio)
    if score_components.get("Volume", 0) == 0:
        factors.append("⚠️ Very low volume — low liquidity")
        penalty += 10

    # Squeeze flag adds confidence FOR squeeze categories
    if info and (info.get("sf", 0) or 0) * 100 >= 15:
        factors.append(f"🔥 High short float ({(info.get('sf',0)*100):.1f}%) — squeeze fuel")

    # Final confidence score (inverse of penalty)
    total_score = max(0, 100 - penalty)
    conf_label = (
        "Very High" if total_score >= 80
        else "High"    if total_score >= 65
        else "Medium"  if total_score >= 45
        else "Low"
    )

    # Risk (independent of confidence)
    risk_pts = 0
    if info:
        beta = info.get("beta", 1) or 1
        mc = info.get("mktcap", 1e9) or 1e9
        sf = (info.get("sf", 0) or 0) * 100
        if beta > 2:   risk_pts += 3
        elif beta > 1.5: risk_pts += 2
        elif beta > 1:   risk_pts += 1
        if mc < 500e6:  risk_pts += 3
        elif mc < 2e9:  risk_pts += 2
        if sf > 20:     risk_pts += 2
        elif sf > 10:   risk_pts += 1

    try:
        vol_std = df["close"].pct_change().std() * 100
        if vol_std > 5: risk_pts += 3
        elif vol_std > 3: risk_pts += 2
        elif vol_std > 1.5: risk_pts += 1
    except Exception:
        pass

    risk_label = (
        "Very High" if risk_pts >= 7
        else "High"   if risk_pts >= 5
        else "Medium" if risk_pts >= 3
        else "Low"
    )

    return {
        "score": total_score,
        "confidence": conf_label,
        "risk": risk_label,
        "factors": factors,
        "risk_pts": risk_pts,
    }


# ─────────────────────────────────────────────────────────────
# MARKET REGIME DETECTOR
# ─────────────────────────────────────────────────────────────
def detect_market_regime(sector_changes: dict, avg_mover_pct: float,
                         squeeze_count: int, vix_proxy: float = None) -> dict:
    """
    Classify current market regime from available data.
    Returns: {regime, label, description, best_strategies}
    """
    total_sectors = len(sector_changes) if sector_changes else 1
    bullish_sectors = sum(1 for v in sector_changes.values() if v > 0.3)
    bearish_sectors = sum(1 for v in sector_changes.values() if v < -0.3)

    # Classify
    if bullish_sectors >= total_sectors * 0.7 and avg_mover_pct > 0.5:
        regime = "risk_on"
        label = "🚀 Risk-On"
        desc = "Broad market strength across sectors. Momentum strategies are working."
        strategies = ["🌊 Momentum Leaders", "⚡📈 Volume Breakout", "🏆 Relative Strength"]
    elif bearish_sectors >= total_sectors * 0.6 and avg_mover_pct < -0.3:
        regime = "risk_off"
        label = "🛡️ Risk-Off"
        desc = "Defensive posture. Short opportunities and mean-reversion setups are active."
        strategies = ["📉→📈 Fallen Angels", "🎯 Smart Reversal", "🔁 Mean Reversion"]
    elif squeeze_count >= 3:
        regime = "squeeze_friendly"
        label = "💥 Squeeze-Friendly"
        desc = "High short interest + social momentum. Squeeze setups have elevated potential."
        strategies = ["🔥💥 Squeeze + Buzz", "⚡🧲 Smart Money Signal", "🎭 Social Catalyst"]
    elif abs(avg_mover_pct) < 0.2 and bullish_sectors < total_sectors * 0.5:
        regime = "low_vol_drift"
        label = "😴 Low-Volatility Drift"
        desc = "Choppy, directionless market. Focus on high-conviction setups only."
        strategies = ["🎯📊 Triple Lock", "💎 Value Momentum", "💡 Hidden Movers"]
    else:
        regime = "mixed"
        label = "⚖️ Mixed Signals"
        desc = "No clear directional bias. Diversified composite signals recommended."
        strategies = ["💡 Hidden Movers", "📡 Sentiment Flip", "🔬 Micro-Cap Movers"]

    return {
        "regime": regime,
        "label": label,
        "description": desc,
        "best_strategies": strategies,
        "bullish_sectors": bullish_sectors,
        "bearish_sectors": bearish_sectors,
        "detected_at": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# RECORD SIGNAL EVENT
# ─────────────────────────────────────────────────────────────
def record_signal_event(ticker: str, category: str, score: int,
                         score_components: dict, price: float,
                         info: dict = None, sent: dict = None,
                         recommendation: str = "WATCH",
                         confidence: dict = None,
                         regime: str = "mixed") -> dict:
    """
    Called when a stock enters a composite category.
    Stores the full snapshot for outcome tracking.
    """
    events = _read_json(SIGNAL_HISTORY_PATH, [])

    # Deduplicate: same ticker+category in last 20h → skip
    cutoff = (datetime.now() - timedelta(hours=20)).isoformat()
    for e in events:
        if (e["ticker"] == ticker and e["category"] == category
                and e.get("triggered_at", "") > cutoff):
            return e

    event = {
        "id": f"{ticker}_{category[:24].replace(' ','_')}_{int(time.time())}",
        "ticker": ticker,
        "category": category,
        "triggered_at": datetime.now().isoformat(),
        "trigger_price": float(price),
        "score_at_trigger": int(score),
        "components_at_trigger": score_components or {},
        "recommendation": recommendation,
        "confidence": confidence or {},
        "regime_at_trigger": regime,
        "info_snapshot": {
            "short_float": (info.get("sf", 0) or 0) * 100 if info else None,
            "days_to_cover": info.get("dtc", 0) if info else None,
            "mktcap": info.get("mktcap", None) if info else None,
            "sector": info.get("sector", None) if info else None,
            "beta": info.get("beta", None) if info else None,
        },
        "sentiment_snapshot": {
            "bullish_pct": sent.get("bull", None) if sent else None,
            "bearish_pct": sent.get("bear", None) if sent else None,
            "message_count": sent.get("msgs", None) if sent else None,
            "watchlist_count": sent.get("wl", None) if sent else None,
        },
        # Lifecycle
        "lifecycle_stage": "candidate",  # candidate → confirmed → active → extended → failed/completed
        # Outcomes (filled by update_outcomes)
        "outcomes": {
            "1d_pct": None, "3d_pct": None, "5d_pct": None,
            "10d_pct": None, "20d_pct": None,
            "max_upside": None, "max_drawdown": None,
            "current_pct": None,
            "label": "pending",  # pending, success, failure, mixed
        },
        "last_updated": datetime.now().isoformat(),
    }
    events.append(event)
    # Keep last 500 events only (FIFO)
    events = events[-500:]
    _write_json(SIGNAL_HISTORY_PATH, events)
    return event


# ─────────────────────────────────────────────────────────────
# UPDATE OUTCOMES (called periodically / by worker)
# ─────────────────────────────────────────────────────────────
def update_signal_outcomes(price_fetch_fn):
    """
    For every stored signal event, fetch recent prices and update outcome fields.
    price_fetch_fn(ticker, days) -> DataFrame with 'close' column (or None)
    """
    events = _read_json(SIGNAL_HISTORY_PATH, [])
    changed = False

    for ev in events:
        # Skip recently updated
        try:
            last_upd = datetime.fromisoformat(ev.get("last_updated", "2000-01-01"))
            if (datetime.now() - last_upd).total_seconds() < 2 * 3600:
                continue
        except Exception:
            pass

        trigger_dt = datetime.fromisoformat(ev["triggered_at"])
        days_since = max(0, (datetime.now() - trigger_dt).days)
        trigger_price = ev.get("trigger_price", 0)
        if trigger_price <= 0:
            continue

        try:
            df = price_fetch_fn(ev["ticker"], days_since + 30)
            if df is None or df.empty:
                continue

            closes = list(df["close"].dropna())
            if len(closes) < 2:
                continue

            outs = ev.get("outcomes", {})

            # Current price (latest available)
            current_price = closes[-1]
            outs["current_pct"] = round(((current_price - trigger_price) / trigger_price) * 100, 2)

            # Returns at fixed intervals
            for n_days, key in [(1, "1d_pct"), (3, "3d_pct"), (5, "5d_pct"),
                                  (10, "10d_pct"), (20, "20d_pct")]:
                if outs.get(key) is None and days_since >= n_days:
                    idx = min(n_days, len(closes) - 1)
                    future_price = closes[-idx] if idx > 0 else closes[-1]
                    outs[key] = round(((future_price - trigger_price) / trigger_price) * 100, 2)

            # Max upside and drawdown since trigger
            future_closes = closes[-(min(days_since + 1, len(closes))):]
            if future_closes:
                highs = max(future_closes)
                lows  = min(future_closes)
                outs["max_upside"]   = round(((highs - trigger_price) / trigger_price) * 100, 2)
                outs["max_drawdown"] = round(((lows  - trigger_price) / trigger_price) * 100, 2)

            # Outcome label
            curr = outs.get("current_pct", 0) or 0
            if curr >= 5:
                outs["label"] = "success"
            elif curr <= -5:
                outs["label"] = "failure"
            elif outs.get("5d_pct") is not None:
                outs["label"] = "mixed"

            # Lifecycle stage update
            if days_since == 0:
                ev["lifecycle_stage"] = "candidate"
            elif days_since <= 2:
                ev["lifecycle_stage"] = "confirmed"
            elif days_since <= 10:
                ev["lifecycle_stage"] = "active"
            elif days_since <= 20:
                ev["lifecycle_stage"] = "extended"
            else:
                ev["lifecycle_stage"] = "completed" if outs["label"] == "success" else "failed"

            ev["outcomes"] = outs
            ev["last_updated"] = datetime.now().isoformat()
            changed = True

        except Exception:
            pass

    if changed:
        _write_json(SIGNAL_HISTORY_PATH, events)

    return events


# ─────────────────────────────────────────────────────────────
# P&L ESTIMATOR — "What Would You Have Made?"
# ─────────────────────────────────────────────────────────────
def calculate_pnl(investment_usd: float, trigger_price: float,
                   current_price: float, direction: str = "long") -> dict:
    """
    Calculates stock P&L for a given dollar investment.
    direction: "long" (buy) or "short" (short-sell)
    """
    if trigger_price <= 0:
        return {}

    shares = investment_usd / trigger_price
    price_change = current_price - trigger_price
    pct_change = (price_change / trigger_price) * 100

    if direction == "long":
        pnl_usd = shares * price_change
        pnl_pct = pct_change
    else:  # short
        pnl_usd = -shares * price_change
        pnl_pct = -pct_change

    current_value = investment_usd + pnl_usd

    return {
        "direction": direction,
        "investment_usd": round(investment_usd, 2),
        "shares": round(shares, 4),
        "trigger_price": round(trigger_price, 2),
        "current_price": round(current_price, 2),
        "price_change": round(price_change, 2),
        "pct_change": round(pct_change, 2),
        "pnl_usd": round(pnl_usd, 2),
        "pnl_pct": round(pnl_pct, 2),
        "current_value": round(current_value, 2),
    }


def estimate_options_pnl(investment_usd: float, trigger_price: float,
                          current_price: float, days_held: int,
                          option_type: str = "call",
                          implied_vol: float = 0.45) -> dict:
    """
    Rough Black-Scholes delta-approximated options P&L estimate.
    This is an EDUCATIONAL ESTIMATE — not financial advice.

    Assumes ATM options at trigger, typical retail contracts.
    Uses simplified delta * price_change approximation + time decay.
    """
    if trigger_price <= 0 or current_price <= 0:
        return {}

    strike = trigger_price  # ATM option
    price_change_pct = (current_price - trigger_price) / trigger_price

    # Approximate premium for 30-DTE ATM option (simplified)
    # Premium ≈ 0.4 × IV × Stock_Price × sqrt(T/252) for ATM options
    T = max(30, days_held + 5) / 252  # annualized time
    approx_premium_per_share = 0.4 * implied_vol * trigger_price * math.sqrt(T)
    contract_cost = approx_premium_per_share * 100  # 1 contract = 100 shares

    # Contracts we can buy
    num_contracts = max(1, int(investment_usd / contract_cost))
    total_premium_paid = num_contracts * contract_cost

    # Delta approximation (0.5 for ATM, adjusts with move)
    # For call: delta ≈ 0.5 + 0.3 * normalized_move
    # For put:  delta ≈ -0.5 - 0.3 * normalized_move
    price_change = current_price - trigger_price
    normalized_move = price_change / (implied_vol * trigger_price * math.sqrt(days_held / 252 if days_held > 0 else 1/252))
    normalized_move = max(-2, min(2, normalized_move))

    if option_type == "call":
        delta = min(0.95, max(0.05, 0.5 + 0.25 * normalized_move))
        # Option value at current price (simplified)
        intrinsic = max(0, current_price - strike)
        time_value_left = approx_premium_per_share * max(0, 1 - days_held / 45) * 0.5
        option_value_per_share = intrinsic + time_value_left
    else:  # put
        delta = max(-0.95, min(-0.05, -0.5 - 0.25 * normalized_move))
        intrinsic = max(0, strike - current_price)
        time_value_left = approx_premium_per_share * max(0, 1 - days_held / 45) * 0.5
        option_value_per_share = intrinsic + time_value_left

    # P&L
    option_current_value = num_contracts * option_value_per_share * 100
    pnl_usd = option_current_value - total_premium_paid
    pnl_pct = (pnl_usd / total_premium_paid) * 100 if total_premium_paid > 0 else 0

    # Leverage multiple
    leverage = abs(pnl_pct) / (abs(price_change_pct) * 100 + 0.001) if price_change_pct != 0 else 1

    return {
        "option_type": option_type,
        "strike": round(strike, 2),
        "contracts": num_contracts,
        "premium_per_contract": round(contract_cost, 2),
        "total_premium_paid": round(total_premium_paid, 2),
        "approx_current_value": round(option_current_value, 2),
        "pnl_usd": round(pnl_usd, 2),
        "pnl_pct": round(pnl_pct, 2),
        "delta_at_trigger": round(delta, 3),
        "leverage_multiple": round(leverage, 2),
        "disclaimer": "⚠️ Educational estimate only. Actual options pricing depends on IV, Greeks, spread, and timing.",
        "days_held_estimate": days_held,
    }


# ─────────────────────────────────────────────────────────────
# AGGREGATED PERFORMANCE STATS BY CATEGORY
# ─────────────────────────────────────────────────────────────
def get_category_performance_stats() -> dict:
    """
    Aggregates all signal outcomes by category.
    Returns: { category: { win_rate, avg_1d, avg_5d, avg_20d, count, best, worst } }
    """
    events = _read_json(SIGNAL_HISTORY_PATH, [])
    cats: dict = {}

    for ev in events:
        cat = ev.get("category", "Unknown")
        outs = ev.get("outcomes", {})
        label = outs.get("label", "pending")
        if label == "pending":
            continue

        if cat not in cats:
            cats[cat] = {"wins": 0, "losses": 0, "mixed": 0, "total": 0,
                          "pcts_1d": [], "pcts_5d": [], "pcts_20d": [], "pcts_current": []}

        cats[cat]["total"] += 1
        if label == "success":    cats[cat]["wins"] += 1
        elif label == "failure":  cats[cat]["losses"] += 1
        else:                     cats[cat]["mixed"] += 1

        if outs.get("1d_pct") is not None:  cats[cat]["pcts_1d"].append(outs["1d_pct"])
        if outs.get("5d_pct") is not None:  cats[cat]["pcts_5d"].append(outs["5d_pct"])
        if outs.get("20d_pct") is not None: cats[cat]["pcts_20d"].append(outs["20d_pct"])
        if outs.get("current_pct") is not None: cats[cat]["pcts_current"].append(outs["current_pct"])

    result = {}
    for cat, d in cats.items():
        total = d["total"]
        if total == 0:
            continue
        win_rate = round((d["wins"] / total) * 100, 1)
        avg = lambda lst: round(sum(lst) / len(lst), 2) if lst else None
        best = max(d["pcts_5d"]) if d["pcts_5d"] else None
        worst = min(d["pcts_5d"]) if d["pcts_5d"] else None
        result[cat] = {
            "win_rate": win_rate,
            "avg_1d": avg(d["pcts_1d"]),
            "avg_5d": avg(d["pcts_5d"]),
            "avg_20d": avg(d["pcts_20d"]),
            "avg_current": avg(d["pcts_current"]),
            "count": total,
            "wins": d["wins"],
            "losses": d["losses"],
            "mixed": d["mixed"],
            "best_5d": round(best, 2) if best is not None else None,
            "worst_5d": round(worst, 2) if worst is not None else None,
        }
    return result


# ─────────────────────────────────────────────────────────────
# GET EVENTS FOR A SPECIFIC TICKER
# ─────────────────────────────────────────────────────────────
def get_ticker_signal_history(ticker: str, limit: int = 20) -> list:
    """Return all signal events for a given ticker, newest first."""
    events = _read_json(SIGNAL_HISTORY_PATH, [])
    ticker_events = [e for e in events if e.get("ticker") == ticker]
    return sorted(ticker_events, key=lambda x: x.get("triggered_at", ""), reverse=True)[:limit]


def get_recent_signal_events(limit: int = 50, category: str = None) -> list:
    """Return the N most recent signal events, optionally filtered by category."""
    events = _read_json(SIGNAL_HISTORY_PATH, [])
    if category:
        events = [e for e in events if e.get("category") == category]
    return sorted(events, key=lambda x: x.get("triggered_at", ""), reverse=True)[:limit]


# ─────────────────────────────────────────────────────────────
# SEED DEMO DATA (for UI testing when no real signals yet)
# ─────────────────────────────────────────────────────────────
def seed_demo_signal_history(price_fn=None):
    """Populate signal history with realistic demo data for UI.

    price_fn (optional): a callable ticker->live_price. When provided, each demo signal's
    entry (trigger_price) is ANCHORED to the live price so the demo is internally
    consistent — entry = current/(1+current_pct/100), i.e. the live "since signal" return
    equals the seeded outcome. The hardcoded prices below are stale illustrative values
    (real tickers drift), so without anchoring a demo entry can imply a nonsensical move
    vs the live price (e.g. a $268 entry on a stock now trading at $104)."""
    events = _read_json(SIGNAL_HISTORY_PATH, [])
    _EVT_CATS = ("🏛️ Insider Buy", "📰 8-K Filing", "📊 Short Interest")
    have_events = any(e.get("category") in _EVT_CATS for e in events)
    if len(events) >= 10 and have_events:
        return  # already fully seeded (categories + event types)

    now = datetime.now()
    demo_events = [
        # Squeeze + Buzz — GME — 8 days ago — BIG win
        {
            "id": f"GME_Squeeze_Buzz_{int(time.time())}_1",
            "ticker": "GME",
            "category": "🔥💥 Squeeze + Buzz",
            "triggered_at": (now - timedelta(days=8)).isoformat(),
            "trigger_price": 18.40,
            "score_at_trigger": 82,
            "components_at_trigger": {"Momentum": 20, "Trend": 16, "MACD": 15, "Volume": 15, "Sentiment": 10, "Squeeze": 10},
            "recommendation": "🟢 BUY",
            "confidence": {"confidence": "High", "risk": "Very High", "score": 74},
            "regime_at_trigger": "squeeze_friendly",
            "info_snapshot": {"short_float": 21.3, "days_to_cover": 4.2, "sector": "Consumer Cyclical", "beta": 1.9},
            "sentiment_snapshot": {"bullish_pct": 78, "bearish_pct": 22, "message_count": 312, "watchlist_count": 94200},
            "lifecycle_stage": "completed",
            "outcomes": {"1d_pct": 12.4, "3d_pct": 24.7, "5d_pct": 31.2, "10d_pct": 18.6, "20d_pct": None,
                         "max_upside": 34.1, "max_drawdown": -4.2, "current_pct": 18.6, "label": "success"},
            "last_updated": now.isoformat(),
        },
        # Triple Lock — NVDA — 5 days ago — moderate win
        {
            "id": f"NVDA_Triple_Lock_{int(time.time())}_2",
            "ticker": "NVDA",
            "category": "🎯📊 Triple Lock",
            "triggered_at": (now - timedelta(days=5)).isoformat(),
            "trigger_price": 127.50,
            "score_at_trigger": 88,
            "components_at_trigger": {"Momentum": 20, "Trend": 20, "MACD": 15, "Volume": 11, "Sentiment": 15, "Squeeze": 0},
            "recommendation": "🟢 STRONG BUY",
            "confidence": {"confidence": "Very High", "risk": "Medium", "score": 88},
            "regime_at_trigger": "risk_on",
            "info_snapshot": {"short_float": 1.1, "days_to_cover": 1.8, "sector": "Technology", "beta": 1.6},
            "sentiment_snapshot": {"bullish_pct": 82, "bearish_pct": 18, "message_count": 687, "watchlist_count": 310400},
            "lifecycle_stage": "active",
            "outcomes": {"1d_pct": 3.2, "3d_pct": 6.8, "5d_pct": 9.1, "10d_pct": None, "20d_pct": None,
                         "max_upside": 10.4, "max_drawdown": -1.8, "current_pct": 9.1, "label": "success"},
            "last_updated": now.isoformat(),
        },
        # Hidden Mover — PLTR — 3 days ago — early
        {
            "id": f"PLTR_Hidden_Movers_{int(time.time())}_3",
            "ticker": "PLTR",
            "category": "💡 Hidden Movers",
            "triggered_at": (now - timedelta(days=3)).isoformat(),
            "trigger_price": 22.80,
            "score_at_trigger": 71,
            "components_at_trigger": {"Momentum": 18, "Trend": 16, "MACD": 9, "Volume": 11, "Sentiment": 10, "Squeeze": 2},
            "recommendation": "🟢 BUY",
            "confidence": {"confidence": "High", "risk": "High", "score": 72},
            "regime_at_trigger": "mixed",
            "info_snapshot": {"short_float": 3.2, "days_to_cover": 2.1, "sector": "Technology", "beta": 2.1},
            "sentiment_snapshot": {"bullish_pct": 66, "bearish_pct": 34, "message_count": 89, "watchlist_count": 42100},
            "lifecycle_stage": "confirmed",
            "outcomes": {"1d_pct": 2.1, "3d_pct": 5.4, "5d_pct": None, "10d_pct": None, "20d_pct": None,
                         "max_upside": 6.2, "max_drawdown": -2.3, "current_pct": 5.4, "label": "success"},
            "last_updated": now.isoformat(),
        },
        # Smart Reversal — AMD — 12 days ago — failure
        {
            "id": f"AMD_Smart_Reversal_{int(time.time())}_4",
            "ticker": "AMD",
            "category": "🎯 Smart Reversal",
            "triggered_at": (now - timedelta(days=12)).isoformat(),
            "trigger_price": 168.20,
            "score_at_trigger": 65,
            "components_at_trigger": {"Momentum": 25, "Trend": 12, "MACD": 9, "Volume": 7, "Sentiment": 6, "Squeeze": 0},
            "recommendation": "🟡 WATCH",
            "confidence": {"confidence": "Medium", "risk": "High", "score": 56},
            "regime_at_trigger": "risk_off",
            "info_snapshot": {"short_float": 2.8, "days_to_cover": 1.9, "sector": "Technology", "beta": 1.7},
            "sentiment_snapshot": {"bullish_pct": 51, "bearish_pct": 49, "message_count": 142, "watchlist_count": 178000},
            "lifecycle_stage": "failed",
            "outcomes": {"1d_pct": -1.8, "3d_pct": -4.2, "5d_pct": -7.6, "10d_pct": -11.3, "20d_pct": None,
                         "max_upside": 2.1, "max_drawdown": -13.4, "current_pct": -11.3, "label": "failure"},
            "last_updated": now.isoformat(),
        },
        # Volume Breakout — MSTR — 2 days ago — very fresh
        {
            "id": f"MSTR_Volume_Breakout_{int(time.time())}_5",
            "ticker": "MSTR",
            "category": "⚡📈 Volume Breakout",
            "triggered_at": (now - timedelta(days=2)).isoformat(),
            "trigger_price": 342.60,
            "score_at_trigger": 79,
            "components_at_trigger": {"Momentum": 20, "Trend": 20, "MACD": 15, "Volume": 15, "Sentiment": 10, "Squeeze": 6},
            "recommendation": "🟢 BUY",
            "confidence": {"confidence": "High", "risk": "Very High", "score": 70},
            "regime_at_trigger": "squeeze_friendly",
            "info_snapshot": {"short_float": 17.2, "days_to_cover": 3.6, "sector": "Technology", "beta": 3.2},
            "sentiment_snapshot": {"bullish_pct": 71, "bearish_pct": 29, "message_count": 428, "watchlist_count": 118700},
            "lifecycle_stage": "confirmed",
            "outcomes": {"1d_pct": 8.7, "3d_pct": None, "5d_pct": None, "10d_pct": None, "20d_pct": None,
                         "max_upside": 11.2, "max_drawdown": -3.1, "current_pct": 8.7, "label": "success"},
            "last_updated": now.isoformat(),
        },
        # ── Event-driven alerts: insider buy / 8-K filing / short-interest surge ──
        {
            "id": f"FLUT_insider_{int(time.time())}_6",
            "ticker": "FLUT", "category": "🏛️ Insider Buy",
            "triggered_at": (now - timedelta(days=3, hours=4)).isoformat(),
            "trigger_price": 268.10, "score_at_trigger": 78,
            "components_at_trigger": {}, "recommendation": "2 open-market insider buys (~$69K, SEC Form 4)",
            "confidence": {"confidence": "High", "risk": "Medium", "score": 72},
            "regime_at_trigger": "neutral",
            "info_snapshot": {"short_float": 4.1, "days_to_cover": 2.0, "sector": "Consumer Cyclical", "beta": 1.1},
            "sentiment_snapshot": {},
            "lifecycle_stage": "confirmed",
            "outcomes": {"1d_pct": 1.2, "3d_pct": 2.8, "5d_pct": None, "10d_pct": None, "20d_pct": None,
                         "max_upside": 3.4, "max_drawdown": -0.9, "current_pct": 2.8, "label": "success"},
            "last_updated": now.isoformat(),
        },
        {
            "id": f"ON_8k_{int(time.time())}_7",
            "ticker": "ON", "category": "📰 8-K Filing",
            "triggered_at": (now - timedelta(days=1)).isoformat(),
            "trigger_price": 58.30, "score_at_trigger": 64,
            "components_at_trigger": {}, "recommendation": "Fresh SEC 8-K filing — possible material catalyst",
            "confidence": {"confidence": "Medium", "risk": "Medium", "score": 58},
            "regime_at_trigger": "neutral",
            "info_snapshot": {"short_float": 3.0, "days_to_cover": 1.6, "sector": "Technology", "beta": 1.4},
            "sentiment_snapshot": {},
            "lifecycle_stage": "active",
            "outcomes": {"1d_pct": 3.1, "3d_pct": None, "5d_pct": None, "10d_pct": None, "20d_pct": None,
                         "max_upside": 4.0, "max_drawdown": -1.1, "current_pct": 3.1, "label": "success"},
            "last_updated": now.isoformat(),
        },
        {
            "id": f"KYMR_si_{int(time.time())}_8",
            "ticker": "KYMR", "category": "📊 Short Interest",
            "triggered_at": (now - timedelta(days=4)).isoformat(),
            "trigger_price": 41.80, "score_at_trigger": 70,
            "components_at_trigger": {}, "recommendation": "Days-to-cover at 15.6 — short-squeeze fuel building",
            "confidence": {"confidence": "High", "risk": "High", "score": 66},
            "regime_at_trigger": "neutral",
            "info_snapshot": {"short_float": 18.4, "days_to_cover": 15.6, "sector": "Healthcare", "beta": 1.8},
            "sentiment_snapshot": {},
            "lifecycle_stage": "confirmed",
            "outcomes": {"1d_pct": 2.4, "3d_pct": 6.1, "5d_pct": None, "10d_pct": None, "20d_pct": None,
                         "max_upside": 8.0, "max_drawdown": -2.2, "current_pct": 6.1, "label": "success"},
            "last_updated": now.isoformat(),
        },
    ]
    # Anchor entry prices to LIVE prices so the demo is internally consistent (entry =
    # current / (1 + current_pct/100)). Falls back to the hardcoded value if the lookup
    # fails or returns nothing.
    if price_fn:
        for e in demo_events:
            cp = (e.get("outcomes") or {}).get("current_pct")
            if cp is None or cp <= -99:
                continue
            try:
                live = float(price_fn(e.get("ticker")) or 0)
            except Exception:
                live = 0
            if live > 0:
                e["trigger_price"] = round(live / (1 + cp / 100.0), 2)
    # If plenty of category demos already exist, only top up the filing/data examples.
    if len(events) >= 10:
        demo_events = [e for e in demo_events if e["category"] in _EVT_CATS]
    events.extend(demo_events)
    _write_json(SIGNAL_HISTORY_PATH, events)
