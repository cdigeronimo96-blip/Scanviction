"""
Polygon.io (a.k.a. Massive) bulk data adapter for MarketSignalPro.

WHY THIS EXISTS
---------------
The legacy warm scored each ticker with ~4 yfinance calls (quote + 60d OHLCV +
fundamentals + sentiment). At ~4N calls on a shared/cloud IP, yfinance rate-limits
and stalls, capping the universe at ~82 curated names. This module replaces the
bulk "scan" layer with Polygon endpoints that return the WHOLE US market in a
handful of calls:

  * Grouped Daily Aggregates  -> one call = every ticker's OHLCV for one day.
    Pull the last ~90 trading days (cached, +1 new call/day) and you have enough
    history to compute every technical (RSI/MACD/MAs/Bollinger) for thousands of
    tickers without a single per-ticker request.
  * Snapshot (all tickers)    -> one call = current-ish quote for every ticker.
  * Reference Tickers         -> market cap / sector / name for filtering + display.

Detail-layer data (short interest, StockTwits sentiment, news, full fundamentals)
stays LAZY in app.py — fetched per-ticker only when the user opens a name. This
module deliberately does NOT touch Streamlit, so the universe worker thread can
call it.

DESIGN NOTES
------------
* Every network call has a hard timeout. The whole reason the legacy warm hung
  was yfinance calls with no timeout (see app.py history). Do not remove these.
* Stateless: callers (app.py's tiered cache / msp_store) own caching. We only
  keep a tiny in-process memo for the rarely-changing trading-calendar/reference
  pulls to avoid hammering them within a single warm.
* Base URL is configurable via POLYGON_BASE_URL in case the Massive rebrand moves
  the API host; defaults to the stable api.polygon.io.
"""

from __future__ import annotations

import os
import time
import datetime as _dt
from typing import Optional

import requests

# Polygon's REST host has historically stayed api.polygon.io even across the
# Massive rebrand. Override via env if that ever changes.
BASE_URL = os.environ.get("POLYGON_BASE_URL", "https://api.polygon.io").rstrip("/")

# Hard per-request timeout (connect, read). Load-bearing — never None.
HTTP_TIMEOUT = (5, 15)
_UA = {"User-Agent": "MarketSignalPro/1.0 (+polygon-adapter)"}

# Liquidity filter defaults for the dynamic universe. These prune illiquid OTC
# noise (and the delisted-penny dead weight that used to hang the warm) for free,
# in-process, with zero extra API calls.
MIN_PRICE = float(os.environ.get("POLY_MIN_PRICE", "1.0"))
MIN_DOLLAR_VOL = float(os.environ.get("POLY_MIN_DOLLAR_VOL", "1000000"))  # $1M/day
MAX_UNIVERSE = int(os.environ.get("POLY_MAX_UNIVERSE", "2500"))


class PolygonError(RuntimeError):
    pass


def _get(api_key: str, path: str, params: Optional[dict] = None) -> dict:
    """GET a Polygon REST path and return parsed JSON. Raises PolygonError on
    non-200 or transport failure — callers decide whether to fall back."""
    if not api_key:
        raise PolygonError("no Polygon API key")
    q = dict(params or {})
    q["apiKey"] = api_key
    url = f"{BASE_URL}{path}"
    try:
        r = requests.get(url, params=q, timeout=HTTP_TIMEOUT, headers=_UA)
    except requests.RequestException as e:
        raise PolygonError(f"transport error: {e}") from e
    if r.status_code == 429:
        raise PolygonError("rate limited (429) — unexpected on unlimited tier")
    if r.status_code != 200:
        raise PolygonError(f"HTTP {r.status_code}: {r.text[:200]}")
    try:
        return r.json()
    except ValueError as e:
        raise PolygonError(f"bad JSON: {e}") from e


# ── Trading calendar helpers ────────────────────────────────────────────────
# Grouped-daily for a weekend/holiday returns an empty resultset; we step back
# to the most recent date that actually has bars rather than guess the calendar.

def _iso(d: _dt.date) -> str:
    return d.isoformat()


def grouped_daily(api_key: str, date_iso: str, adjusted: bool = True) -> dict:
    """One call -> every US ticker's OHLCV for `date_iso` (YYYY-MM-DD).
    Returns {TICKER: {"o","h","l","c","v","vw","n"}}. Empty dict if the market
    was closed that day."""
    path = f"/v2/aggs/grouped/locale/us/market/stocks/{date_iso}"
    data = _get(api_key, path, {"adjusted": str(adjusted).lower()})
    out = {}
    for row in data.get("results", []) or []:
        sym = row.get("T")
        if not sym:
            continue
        out[sym] = {
            "o": row.get("o"), "h": row.get("h"), "l": row.get("l"),
            "c": row.get("c"), "v": row.get("v"), "vw": row.get("vw"),
            "n": row.get("n"),
        }
    return out


def recent_grouped_days(api_key: str, days: int = 90,
                        from_date: Optional[_dt.date] = None,
                        max_lookback: int = 160) -> "list[tuple[str, dict]]":
    """Walk backward from `from_date` (default today) collecting up to `days`
    trading days that actually have bars. Returns a list of (date_iso, grouped)
    oldest-first. `max_lookback` caps calendar days scanned so a long holiday
    stretch can't loop forever.

    NOTE: this is the history backfill. On a cold start it costs ~`days` calls
    (fine on the unlimited Starter tier); afterward callers cache it and only
    fetch the single newest day each refresh. For a true one-shot whole-market
    backfill, prefer Flat Files (S3) — see flat_file_url()."""
    if from_date is None:
        # Caller passes the date; we avoid Date.now-style nondeterminism by
        # requiring it explicitly when reproducibility matters. Default to UTC
        # today only as a convenience for ad-hoc/CLI use.
        from_date = _dt.datetime.utcnow().date()
    collected: "list[tuple[str, dict]]" = []
    scanned = 0
    d = from_date
    while len(collected) < days and scanned < max_lookback:
        if d.weekday() < 5:  # skip obvious weekends without a call
            try:
                grouped = grouped_daily(api_key, _iso(d))
            except PolygonError:
                # The current day's EOD aggregate is gated on the Starter tier
                # until after settlement ("Attempted to request today's data
                # before end of day" → HTTP 403), and a holiday/missing day can
                # also error. Treat any such day as "no bars" and step back to
                # the most recent COMPLETED trading day rather than aborting the
                # whole walk. A genuinely bad key errors on every day and the
                # caller gets an empty result → it falls back to the legacy scan.
                grouped = {}
            if grouped:
                collected.append((_iso(d), grouped))
        d -= _dt.timedelta(days=1)
        scanned += 1
    collected.reverse()  # oldest-first
    return collected


def build_universe(latest_grouped: dict,
                   min_price: float = MIN_PRICE,
                   min_dollar_vol: float = MIN_DOLLAR_VOL,
                   max_n: int = MAX_UNIVERSE) -> "list[str]":
    """Filter one day's grouped bars into a liquid, tradable universe — ranked
    by dollar volume, capped at `max_n`. Pure/in-process: zero API calls.

    Drops sub-$1 and thin names (where delisted/penny junk and yfinance hangs
    lived). Also skips symbols with non-alpha chars (warrants/units/preferreds
    like 'BRK.B', 'ABC.WS') that complicate downstream pricing."""
    scored = []
    for sym, bar in latest_grouped.items():
        c, v = bar.get("c"), bar.get("v")
        if c is None or v is None:
            continue
        if c < min_price:
            continue
        if not sym.isalpha():
            continue
        dollar_vol = c * v
        if dollar_vol < min_dollar_vol:
            continue
        scored.append((sym, dollar_vol))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in scored[:max_n]]


def frames_from_grouped(grouped_days: "list[tuple[str, dict]]",
                        tickers: "set[str] | None" = None) -> "dict[str, list]":
    """Pivot a list of (date, grouped) into per-ticker OHLCV rows suitable for
    compute_scores(). Returns {ticker: [ {datetime,open,high,low,close,volume}, ... ]}
    in chronological order. If `tickers` is given, only those are assembled."""
    out: "dict[str, list]" = {}
    for date_iso, grouped in grouped_days:
        for sym, bar in grouped.items():
            if tickers is not None and sym not in tickers:
                continue
            if bar.get("c") is None:
                continue
            out.setdefault(sym, []).append({
                "datetime": date_iso,
                "open": bar.get("o"), "high": bar.get("h"),
                "low": bar.get("l"), "close": bar.get("c"),
                "volume": bar.get("v"),
            })
    return out


def snapshot_all(api_key: str) -> dict:
    """One call -> current-ish quote for every ticker. Returns
    {TICKER: {"price","prev","pct","volume","open","high","low"}}.
    Use for the live-ish price layer; OHLCV/technicals come from grouped days."""
    path = "/v2/snapshot/locale/us/markets/stocks/tickers"
    data = _get(api_key, path)
    out = {}
    for row in data.get("tickers", []) or []:
        sym = row.get("ticker")
        if not sym:
            continue
        day = row.get("day") or {}
        prev = row.get("prevDay") or {}
        last = row.get("lastTrade") or {}
        price = last.get("p") or day.get("c") or prev.get("c")
        pc = prev.get("c")
        out[sym] = {
            "price": price,
            "prev": pc,
            "pct": row.get("todaysChangePerc"),
            "volume": day.get("v") or prev.get("v"),
            "open": day.get("o"), "high": day.get("h"), "low": day.get("l"),
        }
    return out


def ticker_reference(api_key: str, ticker: str) -> dict:
    """Per-ticker reference (name, market cap, sector-ish, exchange). Lazy — call
    only for names the user opens, not the whole universe."""
    path = f"/v3/reference/tickers/{ticker}"
    data = _get(api_key, path)
    res = data.get("results") or {}
    return {
        "name": res.get("name"),
        "mktcap": res.get("market_cap"),
        "exchange": res.get("primary_exchange"),
        "sic": res.get("sic_description"),  # closest free "sector" proxy
        "shares": res.get("weighted_shares_outstanding"),
        "desc": (res.get("description") or "")[:300],
    }


def list_ticker_symbols(api_key: str, types=("CS",), market: str = "stocks",
                        active: bool = True, max_pages: int = 25) -> "set[str]":
    """Whole-market symbol set for the given security `types`, via the paginated
    Reference Tickers list endpoint (1000/page, cursor-paged through `next_url`).

    Use this to build a STOCKS-ONLY filter: pass types=("CS","ADRC") to get every
    active common stock + ADR common (excludes ETF/ETN/FUND/units/warrants). Cheap
    (~6-10 calls for the whole market) and slow-changing, so callers cache it.
    Returns a set of ticker symbols; raises PolygonError on transport/HTTP failure
    so the caller can decide to skip the filter rather than ship a wrong universe."""
    out: "set[str]" = set()
    for tp in types:
        url = f"{BASE_URL}/v3/reference/tickers"
        params = {"market": market, "type": tp, "active": str(active).lower(),
                  "limit": 1000, "apiKey": api_key}
        pages = 0
        while url and pages < max_pages:
            try:
                r = requests.get(url, params=params, timeout=HTTP_TIMEOUT, headers=_UA)
            except requests.RequestException as e:
                raise PolygonError(f"transport error: {e}") from e
            if r.status_code != 200:
                raise PolygonError(f"HTTP {r.status_code}: {r.text[:200]}")
            try:
                data = r.json()
            except ValueError as e:
                raise PolygonError(f"bad JSON: {e}") from e
            for row in data.get("results", []) or []:
                sym = row.get("ticker")
                if sym:
                    out.add(sym)
            # next_url already encodes the cursor + all filters; only apiKey must
            # be re-appended (Polygon strips it from the echoed next_url).
            url = data.get("next_url")
            params = {"apiKey": api_key}
            pages += 1
    return out


def short_interest_latest(api_key: str, lookback_days: int = 40,
                          max_pages: int = 15) -> "dict":
    """Whole-market LATEST FINRA short interest. Returns
    {TICKER: {"short_interest","days_to_cover","avg_daily_volume","settlement_date"}}.

    days_to_cover is provided directly by the endpoint and is the academically
    strongest squeeze signal (NBER w21166 / RFS 2016 — a better predictor than the
    plain short ratio). Two-step, because this endpoint does NOT honour sort/order:
      1. filter settlement_date.gte=<recent> to find the most recent settlement_date
         (FINRA reports bi-weekly, ~9-day lag, the same date for all tickers);
      2. page every ticker for that exact settlement_date (~6-10 calls).
    Available on the Stocks Starter plan. Raises PolygonError on failure so callers
    can fall back to technical-only squeeze scoring."""
    since = (_dt.datetime.utcnow().date() - _dt.timedelta(days=lookback_days)).isoformat()
    head = _get(api_key, "/stocks/v1/short-interest",
                {"settlement_date.gte": since, "limit": 1000})
    rows = head.get("results", []) or []
    dates = [r.get("settlement_date") for r in rows if r.get("settlement_date")]
    if not dates:
        return {}
    latest = max(dates)
    out: "dict" = {}
    url = f"{BASE_URL}/stocks/v1/short-interest"
    params = {"settlement_date": latest, "limit": 1000, "apiKey": api_key}
    pages = 0
    while url and pages < max_pages:
        try:
            r = requests.get(url, params=params, timeout=HTTP_TIMEOUT, headers=_UA)
        except requests.RequestException as e:
            raise PolygonError(f"transport error: {e}") from e
        if r.status_code != 200:
            raise PolygonError(f"HTTP {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()
        except ValueError as e:
            raise PolygonError(f"bad JSON: {e}") from e
        for row in data.get("results", []) or []:
            t = row.get("ticker")
            if not t:
                continue
            out[t] = {"short_interest": row.get("short_interest"),
                      "days_to_cover": row.get("days_to_cover"),
                      "avg_daily_volume": row.get("avg_daily_volume"),
                      "settlement_date": row.get("settlement_date")}
        # next_url already encodes the cursor + filters; only apiKey must be re-added.
        url = data.get("next_url")
        params = {"apiKey": api_key}
        pages += 1
    return out


def short_volume_latest(api_key: str, lookback_days: int = 7,
                        max_pages: int = 15) -> "dict":
    """Whole-market LATEST daily off-exchange short VOLUME ratio. Returns
    {TICKER: short_volume_ratio} (percent of the day's volume that was short-sold).
    Distinct from short INTEREST: this is the *intraday* shorting pressure, updated
    daily (T+1). High ratio + price RISING = shorts pressing into strength (squeeze
    fuel happening now). Same two-step as short interest (the endpoint ignores
    sort/order): filter date.gte=<recent> → max date → page all tickers. On the
    Stocks Starter plan. Raises PolygonError on failure."""
    since = (_dt.datetime.utcnow().date() - _dt.timedelta(days=lookback_days)).isoformat()
    head = _get(api_key, "/stocks/v1/short-volume", {"date.gte": since, "limit": 1000})
    rows = head.get("results", []) or []
    dates = [r.get("date") for r in rows if r.get("date")]
    if not dates:
        return {}
    latest = max(dates)
    out: "dict" = {}
    url = f"{BASE_URL}/stocks/v1/short-volume"
    params = {"date": latest, "limit": 1000, "apiKey": api_key}
    pages = 0
    while url and pages < max_pages:
        try:
            r = requests.get(url, params=params, timeout=HTTP_TIMEOUT, headers=_UA)
        except requests.RequestException as e:
            raise PolygonError(f"transport error: {e}") from e
        if r.status_code != 200:
            raise PolygonError(f"HTTP {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()
        except ValueError as e:
            raise PolygonError(f"bad JSON: {e}") from e
        for row in data.get("results", []) or []:
            t = row.get("ticker")
            svr = row.get("short_volume_ratio")
            if t and svr is not None:
                out[t] = float(svr)
        url = data.get("next_url")
        params = {"apiKey": api_key}
        pages += 1
    return out


def diluted_eps_ttm(api_key: str, ticker: str):
    """Trailing-twelve-month diluted EPS for one ticker from the Financials endpoint
    (/vX/reference/financials). Per-ticker only (no bulk financials on the Starter
    plan), so callers should background-fill + cache it — fundamentals change only
    quarterly. Returns a float or None. Used to compute real P/E = price / EPS for
    the Value Momentum category."""
    data = _get(api_key, "/vX/reference/financials",
                {"ticker": ticker, "timeframe": "ttm", "order": "desc",
                 "sort": "period_of_report_date", "limit": 1})
    res = data.get("results") or []
    if not res:
        return None
    inc = (res[0].get("financials") or {}).get("income_statement") or {}
    eps = (inc.get("diluted_earnings_per_share") or {}).get("value")
    try:
        return float(eps) if eps is not None else None
    except (TypeError, ValueError):
        return None


def flat_file_url(date_iso: str) -> str:
    """S3 path for a whole-market daily Flat File (bulk CSV). Starter includes
    Flat Files — for a cold-start history backfill this is one download instead
    of ~90 grouped-daily calls. Requires S3 credentials from the dashboard;
    wire this in later if the per-call backfill proves too slow."""
    return (f"s3://flatfiles/us_stocks_sip/day_aggs_v1/"
            f"{date_iso[:4]}/{date_iso[5:7]}/{date_iso}.csv.gz")


def healthcheck(api_key: str) -> dict:
    """Cheap end-to-end probe: pull one recent grouped-daily and report counts.
    Use this right after dropping in the key to confirm the tier/endpoints work
    before wiring into the warm."""
    t0 = time.time()
    days = recent_grouped_days(api_key, days=1)
    if not days:
        return {"ok": False, "error": "no trading day with bars in lookback window"}
    date_iso, grouped = days[-1]
    uni = build_universe(grouped)
    return {
        "ok": True,
        "date": date_iso,
        "total_symbols": len(grouped),
        "liquid_universe": len(uni),
        "sample": uni[:15],
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


if __name__ == "__main__":
    # CLI self-test:  python polygon_adapter.py <API_KEY>
    import json
    import sys
    key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("POLYGON_API_KEY", "")
    if not key:
        print("usage: python polygon_adapter.py <API_KEY>  (or set POLYGON_API_KEY)")
        raise SystemExit(2)
    print(json.dumps(healthcheck(key), indent=2))
