"""
SEC EDGAR adapter (FREE, keyless) for MarketSignalPro.

Two free signals straight from EDGAR's daily index + Form 4 filings — neither is
available from Polygon/Massive on the Starter plan:
  * recent_8k_tickers()   -> tickers that filed a fresh 8-K (material-event catalyst).
  * recent_insider_buys() -> tickers with OPEN-MARKET insider PURCHASES (Form 4,
                             transaction code 'P'); cluster buying is one of the
                             better-documented retail edges. Grants/awards (codes
                             'A','M','G') are ignored — only real buys count.

SEC requires a descriptive User-Agent with a contact and asks for <= 10 req/s. The
contact comes from EDGAR_UA. Stateless: callers cache results (filings are daily
events). Every function degrades to empty on failure so the app never breaks.
"""
import os
import re
import time
import datetime as _dt
import requests

EDGAR_UA = {"User-Agent": os.environ.get("EDGAR_UA", "MarketSignalPro admin@marketsignalpro.com")}
_BASE = "https://www.sec.gov"
TIMEOUT = (5, 20)


class EdgarError(RuntimeError):
    pass


_CIK_CACHE = {"map": None}


def cik_ticker_map(force: bool = False) -> "dict":
    """{cik(int): TICKER} from company_tickers.json (one ~800KB fetch). Memoized."""
    if _CIK_CACHE["map"] is not None and not force:
        return _CIK_CACHE["map"]
    r = requests.get(f"{_BASE}/files/company_tickers.json", headers=EDGAR_UA, timeout=TIMEOUT)
    if r.status_code != 200:
        raise EdgarError(f"company_tickers HTTP {r.status_code}")
    out = {}
    for v in (r.json() or {}).values():
        try:
            out[int(v["cik_str"])] = str(v["ticker"]).upper()
        except Exception:
            continue
    _CIK_CACHE["map"] = out
    return out


def _utcdate() -> _dt.date:
    try:
        return _dt.datetime.now(_dt.timezone.utc).date()
    except Exception:
        return _dt.date.today()


def _qtr(d: _dt.date) -> int:
    return (d.month - 1) // 3 + 1


def _recent_index_rows(days: int, from_date: _dt.date) -> "list":
    """[[CIK, Company, Form, Date, Filename], ...] from the daily master indexes for
    up to `days` recent weekdays ending at from_date. Today's index may 404 until
    EOD, so we just skip missing days and walk back."""
    rows = []
    d = from_date
    got = 0
    scanned = 0
    while got < days and scanned < days * 2 + 6:
        if d.weekday() < 5:
            url = (f"{_BASE}/Archives/edgar/daily-index/{d.year}/QTR{_qtr(d)}/"
                   f"master.{d.strftime('%Y%m%d')}.idx")
            try:
                r = requests.get(url, headers=EDGAR_UA, timeout=TIMEOUT)
            except requests.RequestException:
                r = None
            if r is not None and r.status_code == 200 and len(r.text) > 500:
                for line in r.text.splitlines():
                    if line.count("|") == 4:
                        rows.append(line.split("|"))
                got += 1
            time.sleep(0.15)  # be polite to SEC
        d -= _dt.timedelta(days=1)
        scanned += 1
    return rows


def recent_8k_tickers(days: int = 4, from_date=None) -> "set":
    """Set of tickers that filed an 8-K in the last `days` trading days — a
    material-event / news catalyst flag. Cheap: daily index only (no per-filing
    fetch). Returns an empty set on failure."""
    if from_date is None:
        from_date = _utcdate()
    try:
        c2t = cik_ticker_map()
        out = set()
        for cik, name, form, date, fname in _recent_index_rows(days, from_date):
            if form.strip().upper().startswith("8-K"):
                try:
                    t = c2t.get(int(cik))
                except Exception:
                    t = None
                if t:
                    out.add(t)
        return out
    except Exception:
        return set()


def recent_insider_buys(days: int = 3, universe=None, max_parse: int = 280,
                        from_date=None) -> "dict":
    """{ticker: {"buys": n, "value": usd, "last": "YYYYMMDD"}} for OPEN-MARKET insider
    PURCHASES (Form 4, transactionCode 'P'). Walks the daily index for Form 4s, maps
    CIK->ticker, keeps only `universe` tickers (if given), then fetches+parses up to
    `max_parse` filings (modestly threaded, SEC-polite) for purchase transactions.
    Bounded so it never stalls; callers cache the result (daily). Empty on failure."""
    if from_date is None:
        from_date = _utcdate()
    try:
        c2t = cik_ticker_map()
    except Exception:
        return {}
    uni = set(universe) if universe else None
    cands = []
    try:
        for cik, name, form, date, fname in _recent_index_rows(days, from_date):
            if form.strip() != "4":
                continue
            try:
                t = c2t.get(int(cik))
            except Exception:
                t = None
            if not t or (uni is not None and t not in uni):
                continue
            cands.append((t, date, fname))
    except Exception:
        return {}
    cands = cands[:max_parse]
    if not cands:
        return {}

    def _parse(item):
        t, date, fname = item
        try:
            r = requests.get(f"{_BASE}/Archives/{fname}", headers=EDGAR_UA, timeout=TIMEOUT)
            if r.status_code != 200:
                return None
            body = r.text
        except requests.RequestException:
            return None
        if not re.search(r"<transactionCode>\s*P\s*</transactionCode>", body):
            return None  # no open-market purchase in this filing
        shares = re.findall(r"<transactionShares>\s*<value>([\d.]+)</value>", body)
        prices = re.findall(r"<transactionPricePerShare>\s*<value>([\d.]+)</value>", body)
        val = 0.0
        for s, p in zip(shares, prices):
            try:
                val += float(s) * float(p)
            except Exception:
                pass
        return (t, date, val)

    from concurrent.futures import ThreadPoolExecutor, as_completed
    out = {}
    ex = ThreadPoolExecutor(max_workers=4)   # SEC is ~10 req/s; stay polite
    try:
        futs = [ex.submit(_parse, c) for c in cands]
        for fu in as_completed(futs):
            try:
                res = fu.result()
            except Exception:
                res = None
            if not res:
                continue
            t, date, val = res
            e = out.setdefault(t, {"buys": 0, "value": 0.0, "last": ""})
            e["buys"] += 1
            e["value"] += val
            if date > e["last"]:
                e["last"] = date
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return out


if __name__ == "__main__":
    import json
    print("8-K (last 4d):")
    k = recent_8k_tickers(4)
    print("  count:", len(k), "sample:", sorted(k)[:15])
    print("insider buys (last 3d, parse 60):")
    b = recent_insider_buys(days=3, max_parse=60)
    print(json.dumps(b, indent=2)[:800])
