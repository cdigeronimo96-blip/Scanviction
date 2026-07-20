"""
FRED macro adapter (FREE, keyless) for Scanviction.

Uses FRED's public `fredgraph.csv` download endpoint — no API key required — to read
a handful of daily macro series and distill them into a single, plain-English MARKET
REGIME (Risk-On / Neutral / Risk-Off). The two cleanest free risk-appetite gauges are
VIX (equity fear) and the high-yield credit spread (credit stress); the yield curve
adds recession context. This is market BACKDROP, shown to the user so a "signal" is
read in context — calm tape vs. a fear spike are very different environments.

Stateless: callers cache the result (these are daily series). Degrades to a neutral
"unknown" regime on any failure so the app never breaks.
"""
import os
import io
import csv
import requests

FRED_UA = {"User-Agent": os.environ.get("EDGAR_UA", "Scanviction admin@scanviction.com")}
_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
TIMEOUT = (5, 20)

SERIES = {
    "vix":   "VIXCLS",        # CBOE Volatility Index — equity fear gauge
    "dgs10": "DGS10",         # 10-Year Treasury yield
    "dgs2":  "DGS2",          # 2-Year Treasury yield
    "hy":    "BAMLH0A0HYM2",  # ICE BofA US High-Yield OAS — credit stress
    "curve": "T10Y2Y",        # 10Y-2Y spread — recession/curve signal
}


def _latest(series_id):
    """Latest non-missing (date, float) for a FRED series via the keyless CSV. FRED
    encodes missing values as '.'. Returns (None, None) on any failure."""
    try:
        r = requests.get(f"{_BASE}?id={series_id}", headers=FRED_UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, None
        last_date, last = None, None
        for row in csv.reader(io.StringIO(r.text)):
            if len(row) >= 2 and row[1] not in (".", "", None) and row[0] != "DATE":
                try:
                    last = float(row[1]); last_date = row[0]
                except ValueError:
                    continue
        return last_date, last
    except Exception:
        return None, None


def market_regime():
    """{vix, dgs10, dgs2, hy_oas, curve, asof, regime, label, note} — a cached-by-the-
    caller macro snapshot + a Risk-On/Neutral/Risk-Off classification. Regime logic:
    calm vol AND tight credit = Risk-On; a vol spike OR wide credit = Risk-Off; else
    Neutral. Returns regime='unknown' if the data can't be fetched."""
    out = {"vix": None, "dgs10": None, "dgs2": None, "hy_oas": None, "curve": None,
           "asof": None, "regime": "unknown", "label": "Regime unavailable", "note": ""}
    asof = None
    for k, sid in SERIES.items():
        d, v = _latest(sid)
        key = {"vix": "vix", "dgs10": "dgs10", "dgs2": "dgs2", "hy": "hy_oas", "curve": "curve"}[k]
        out[key] = v
        if d and (asof is None or d > asof):
            asof = d
    out["asof"] = asof
    vix = out["vix"]; hy = out["hy_oas"]; curve = out["curve"]
    if vix is None and hy is None:
        return out  # unknown
    # Score risk appetite from the two cleanest free gauges.
    risk_off = 0; risk_on = 0
    if vix is not None:
        if vix >= 26: risk_off += 2
        elif vix >= 20: risk_off += 1
        elif vix < 15: risk_on += 1
        elif vix < 17: risk_on += 1
    if hy is not None:
        if hy >= 5.5: risk_off += 2
        elif hy >= 4.5: risk_off += 1
        elif hy < 3.2: risk_on += 1
    if risk_off >= 2:
        regime, label = "risk_off", "Risk-Off"
    elif risk_on >= 2 and risk_off == 0:
        regime, label = "risk_on", "Risk-On"
    else:
        regime, label = "neutral", "Neutral"
    out["regime"] = regime; out["label"] = label
    bits = []
    if vix is not None:
        bits.append(f"VIX {vix:.0f} " + ("(calm)" if vix < 17 else "(elevated)" if vix >= 20 else "(normal)"))
    if hy is not None:
        bits.append(f"credit spread {hy:.2f}% " + ("(tight)" if hy < 3.5 else "(wide)" if hy >= 5 else "(normal)"))
    if curve is not None:
        bits.append("curve " + ("inverted" if curve < 0 else "normal") + f" ({curve:+.2f})")
    out["note"] = " · ".join(bits)
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(market_regime(), indent=2))
