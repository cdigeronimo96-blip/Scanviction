import streamlit as st
import requests
import pandas as pd
import pandas_ta as ta
import yfinance as yf

st.set_page_config(page_title="Daily Stock Picks", layout="wide", page_icon="📈")

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Configuration")
api_key = st.sidebar.text_input("Twelve Data API Key", type="password")

st.sidebar.markdown("---")
st.sidebar.subheader("📋 Manual Watchlist")
watchlist_input = st.sidebar.text_area("Tickers (comma separated)", "AAPL,TSLA,NVDA,AMD,MSFT,GOOGL,AMZN,META")
manual_watchlist = [t.strip().upper() for t in watchlist_input.split(',') if t.strip()]

st.sidebar.markdown("---")
st.sidebar.subheader("🌐 Social Sources")
use_stocktwits = st.sidebar.toggle("StockTwits Hot Stocks", value=True)
use_squeeze    = st.sidebar.toggle("Short Squeeze Scanner", value=True)
squeeze_threshold = st.sidebar.slider("Min Short Float % for Squeeze", 10, 40, 20)

st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Indicator Settings")
rsi_period     = st.sidebar.slider("RSI Period", 7, 21, 14)
rsi_oversold   = st.sidebar.slider("RSI Oversold", 15, 40, 30)
rsi_overbought = st.sidebar.slider("RSI Overbought", 60, 85, 70)
ma_short       = st.sidebar.slider("Short MA", 5, 30, 10)
ma_long        = st.sidebar.slider("Long MA", 20, 100, 50)

# ── HELPERS ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=900)
def get_stocktwits_hot():
    """Trending tickers from StockTwits — no API key needed."""
    try:
        url  = "https://api.stocktwits.com/api/2/trending/symbols.json"
        data = requests.get(url, timeout=8).json()
        return [s["symbol"] for s in data.get("symbols", [])]
    except Exception:
        return []

@st.cache_data(ttl=900)
def get_stocktwits_symbol_info(ticker):
    """Get message volume + sentiment for a specific ticker from StockTwits."""
    try:
        url  = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
        data = requests.get(url, timeout=8).json()
        symbol_data = data.get("symbol", {})
        watchlist_count = symbol_data.get("watchlist_count", "N/A")

        # Sentiment from recent messages
        messages = data.get("messages", [])
        bullish = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}) and
                      m["entities"]["sentiment"].get("basic") == "Bullish")
        bearish = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}) and
                      m["entities"]["sentiment"].get("basic") == "Bearish")
        total   = bullish + bearish

        sentiment_pct = round((bullish / total) * 100) if total > 0 else None
        return {
            "watchlist_count": watchlist_count,
            "bullish_pct":     sentiment_pct,
            "message_sample":  len(messages)
        }
    except Exception:
        return {}

@st.cache_data(ttl=1800)
def get_squeeze_candidates(tickers, threshold):
    """Finds high short float stocks using Yahoo Finance."""
    candidates = {}
    for ticker in tickers:
        try:
            info          = yf.Ticker(ticker).info
            short_float   = info.get("shortPercentOfFloat", 0)
            days_to_cover = info.get("shortRatio", 0)
            market_cap    = info.get("marketCap", 0)
            avg_volume    = info.get("averageVolume", 0)

            if short_float and short_float * 100 >= threshold:
                candidates[ticker] = {
                    "short_float":    round(short_float * 100, 1),
                    "days_to_cover":  round(days_to_cover, 1) if days_to_cover else "N/A",
                    "market_cap":     f"${market_cap/1e9:.2f}B" if market_cap else "N/A",
                    "avg_volume":     f"{avg_volume/1e6:.1f}M" if avg_volume else "N/A",
                }
        except Exception:
            continue
    return candidates

@st.cache_data(ttl=600)
def fetch_and_analyze(ticker, api_key, outputsize=60):
    url = (
        f"https://api.twelvedata.com/time_series"
        f"?symbol={ticker}&interval=1day&outputsize={outputsize}&apikey={api_key}"
    )
    try:
        response = requests.get(url, timeout=10).json()
    except Exception:
        return None

    if "values" not in response:
        return None

    df = pd.DataFrame(response["values"])
    for col in ["close", "high", "low", "volume"]:
        df[col] = df[col].astype(float)

    df = df.iloc[::-1].reset_index(drop=True)
    df["RSI"]      = ta.rsi(df["close"], length=rsi_period)
    df["MA_short"] = df["close"].rolling(ma_short).mean()
    df["MA_long"]  = df["close"].rolling(ma_long).mean()
    macd_result    = ta.macd(df["close"])
    df["MACD"]     = macd_result["MACD_12_26_9"] if macd_result is not None else None
    return df

# ── MAIN ─────────────────────────────────────────────────────────────────────
st.title("📈 Daily Stock Intelligence Dashboard")

tab1, tab2, tab3 = st.tabs(["🎯 Indicator Picks", "🔥 StockTwits Buzz", "💥 Squeeze Scanner"])

# ── TAB 2: STOCKTWITS ────────────────────────────────────────────────────────
with tab2:
    st.header("🔥 StockTwits Hot Stocks")

    if not use_stocktwits:
        st.info("Enable StockTwits in the sidebar.")
    else:
        with st.spinner("Fetching StockTwits trending list..."):
            hot_tickers = get_stocktwits_hot()

        if not hot_tickers:
            st.warning("Could not reach StockTwits. Try again shortly.")
        else:
            st.success(f"📡 {len(hot_tickers)} tickers trending on StockTwits right now")
            st.markdown("---")

            # Show sentiment for each hot ticker
            rows = []
            prog = st.progress(0, text="Loading sentiment data...")
            for i, ticker in enumerate(hot_tickers):
                prog.progress((i + 1) / len(hot_tickers), text=f"Fetching {ticker}...")
                info = get_stocktwits_symbol_info(ticker)
                rows.append({
                    "Ticker":         ticker,
                    "Watchlists":     info.get("watchlist_count", "N/A"),
                    "Bullish %":      f"{info['bullish_pct']}%" if info.get("bullish_pct") else "N/A",
                    "Recent Posts":   info.get("message_sample", "N/A"),
                })
            prog.empty()

            df_hot = pd.DataFrame(rows)
            st.dataframe(df_hot, use_container_width=True, hide_index=True)

# ── TAB 3: SQUEEZE SCANNER ───────────────────────────────────────────────────
with tab3:
    st.header("💥 Short Squeeze Candidates")
    st.caption(f"Stocks with short float ≥ {squeeze_threshold}% — data via Yahoo Finance")

    if not use_squeeze:
        st.info("Enable Squeeze Scanner in the sidebar.")
    else:
        # Build universe: manual watchlist + StockTwits hot
        universe = list(set(manual_watchlist))
        if use_stocktwits:
            universe += get_stocktwits_hot()
        universe = list(set(universe))[:40]

        with st.spinner(f"Checking short interest data for {len(universe)} tickers..."):
            squeeze_data = get_squeeze_candidates(tuple(universe), squeeze_threshold)

        if not squeeze_data:
            st.info(f"No stocks above {squeeze_threshold}% short float in your current universe.")
        else:
            st.success(f"🔥 Found {len(squeeze_data)} potential squeeze candidates!")
            squeeze_df = pd.DataFrame([
                {
                    "Ticker":        k,
                    "Short Float %": v["short_float"],
                    "Days to Cover": v["days_to_cover"],
                    "Market Cap":    v["market_cap"],
                    "Avg Volume":    v["avg_volume"],
                }
                for k, v in squeeze_data.items()
            ]).sort_values("Short Float %", ascending=False)

            st.dataframe(squeeze_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("What makes a squeeze candidate?")
            col1, col2, col3 = st.columns(3)
            col1.metric("Short Float", f"≥ {squeeze_threshold}%", "Higher = more fuel")
            col2.metric("Days to Cover", "≥ 5 days", "Harder to unwind")
            col3.metric("Volume Spike", "Watch for it", "The trigger")

# ── TAB 1: INDICATOR PICKS ───────────────────────────────────────────────────
with tab1:
    st.header("🎯 Technical Indicator Picks")

    if not api_key:
        st.warning("👈 Enter your Twelve Data API key in the sidebar to begin.")
        st.stop()

    # Merge manual + StockTwits into scan universe
    social_tickers = get_stocktwits_hot() if use_stocktwits else []
    full_universe  = list(set(manual_watchlist + social_tickers))[:30]

    st.caption(
        f"Scanning **{len(full_universe)}** tickers "
        f"({len(manual_watchlist)} manual + {len(social_tickers)} from StockTwits)"
    )

    picks  = []
    errors = []
    prog   = st.progress(0)

    for i, ticker in enumerate(full_universe):
        prog.progress((i + 1) / len(full_universe), text=f"Analyzing {ticker}...")
        df = fetch_and_analyze(ticker, api_key)

        if df is None or len(df) < ma_long:
            errors.append(ticker)
            continue

        latest       = df.iloc[-1]
        prev         = df.iloc[-2]
        latest_rsi   = latest["RSI"]
        latest_price = latest["close"]
        price_change = ((latest_price - prev["close"]) / prev["close"]) * 100
        golden_cross = prev["MA_short"] < prev["MA_long"] and latest["MA_short"] > latest["MA_long"]
        death_cross  = prev["MA_short"] > prev["MA_long"] and latest["MA_short"] < latest["MA_long"]

        signals = []
        if pd.notna(latest_rsi):
            if latest_rsi < rsi_oversold:   signals.append("🟢 RSI Oversold")
            if latest_rsi > rsi_overbought: signals.append("🔴 RSI Overbought")
        if golden_cross: signals.append("✨ Golden Cross")
        if death_cross:  signals.append("💀 Death Cross")
        if pd.notna(latest["MACD"]):
            signals.append("📈 MACD Bullish" if latest["MACD"] > 0 else "📉 MACD Bearish")

        is_social = ticker in social_tickers
        badge     = "🔥 " if is_social else ""

        if signals:
            picks.append({
                "Ticker":     f"{badge}{ticker}",
                "Price":      f"${latest_price:.2f}",
                "Day Change": f"{price_change:+.2f}%",
                "RSI":        round(latest_rsi, 1) if pd.notna(latest_rsi) else "N/A",
                "Signals":    "  |  ".join(signals),
                "_df":        df,
            })

    prog.empty()

    if errors:
        st.warning(f"Skipped (no data / API limit reached): {', '.join(errors)}")

    if not picks:
        st.info("No stocks hitting your thresholds right now. Try widening your RSI range.")
    else:
        st.success(f"✅ {len(picks)} signal(s) found!  🔥 = also trending on StockTwits")
        st.markdown("---")

        for pick in picks:
            df = pick.pop("_df")
            c1, c2, c3, c4 = st.columns([1, 1, 1, 4])
            c1.metric("Ticker",    pick["Ticker"])
            c2.metric("Price",     pick["Price"], pick["Day Change"])
            c3.metric("RSI",       pick["RSI"])
            c4.markdown(f"**Signals:** {pick['Signals']}")

            with st.expander(f"📊 Chart — {pick['Ticker']}"):
                chart_df = df[["datetime", "close", "MA_short", "MA_long"]].copy()
                chart_df = chart_df.rename(columns={
                    "datetime": "Date",
                    "close":    "Price",
                    "MA_short": f"{ma_short}d MA",
                    "MA_long":  f"{ma_long}d MA",
                }).set_index("Date")
                st.line_chart(chart_df)

            st.markdown("---")

st.caption("⚠️ Educational analysis only — not financial advice.")
