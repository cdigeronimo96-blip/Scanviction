"""seo_export (snapshot projection) + seo_generate (static site) — tested in isolation, no app import."""
import os
import json
import seo_export
import seo_generate as gen


# ── seo_export.project_row ───────────────────────────────────────────────────
def test_project_row_basic_fields():
    r = {"t": "aapl", "q": {"price": 214.3, "pct": 1.8}, "sc": 71, "conviction": 82,
         "primary_cat": "🌊 Momentum Leaders", "why": "strong uptrend", "info": {}}
    p = seo_export.project_row(r)
    assert p["t"] == "AAPL"                    # upper-cased
    assert p["price"] == 214.3 and p["pct"] == 1.8
    assert p["conv"] == 82 and p["sc"] == 71
    assert p["cat"] == "🌊 Momentum Leaders"
    assert "dtc" not in p and "insider_buys" not in p and "pe" not in p   # no fabricated sub-stats


def test_project_row_real_substats_only():
    base = {"t": "X", "q": {}, "primary_cat": "c", "conviction": 50}
    assert "insider_buys" in seo_export.project_row({**base, "info": {"insider_buys": 3}})
    assert "insider_buys" not in seo_export.project_row({**base, "info": {"insider_buys": 1}})  # <2 dropped
    assert "dtc" in seo_export.project_row({**base, "info": {"dtc": 8.3}})
    assert "dtc" not in seo_export.project_row({**base, "info": {"dtc": 1.0}})                  # <3 dropped
    assert "pe" in seo_export.project_row({**base, "info": {"pe": 21.0}})
    assert "pe" not in seo_export.project_row({**base, "info": {"pe": 0}})


def test_project_row_rejects_junk_and_nan():
    assert seo_export.project_row({"t": ""}) is None
    assert seo_export.project_row({"t": "A B/<script>"}) is None      # illegal ticker chars
    p = seo_export.project_row({"t": "AAPL", "q": {"price": float("nan")}, "primary_cat": "c"})
    assert p["price"] is None                                          # NaN coerced to None


def test_build_snapshot_sorts_by_conviction():
    rows = [{"t": "A", "q": {}, "primary_cat": "c", "conviction": 40},
            {"t": "B", "q": {}, "primary_cat": "c", "conviction": 90},
            {"t": "C", "q": {}, "primary_cat": "c", "conviction": 65}]
    snap = seo_export.build_snapshot(rows, generated_at="2026-07-02T00:00:00Z")
    assert [r["t"] for r in snap["rows"]] == ["B", "C", "A"]
    assert snap["count"] == 3 and snap["generated_at"] == "2026-07-02T00:00:00Z"


def test_write_snapshot_roundtrip(tmp_path):
    p = tmp_path / "snap.json"
    seo_export.write_snapshot([{"t": "AAPL", "q": {"price": 1.0}, "primary_cat": "c", "conviction": 5}],
                              path=str(p), generated_at="2026-07-02T00:00:00Z")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["rows"][0]["t"] == "AAPL"


# ── seo_generate ─────────────────────────────────────────────────────────────
def _snapshot(tmp_path):
    snap = {"generated_at": "2026-07-02T12:00:00Z", "count": 2, "rows": [
        {"t": "AAPL", "price": 214.3, "pct": 1.8, "sc": 71, "conv": 82,
         "cat": "🌊 Momentum Leaders", "dir": "long", "why": "strong uptrend", "insider_buys": 3},
        {"t": "GME", "price": 28.4, "pct": -2.1, "sc": 60, "conv": 55,
         "cat": "🔥 Short Squeeze", "dir": "long", "why": "high days to cover <script>x</script>", "dtc": 8.3},
    ]}
    sp = tmp_path / "universe_snapshot.json"
    sp.write_text(json.dumps(snap), encoding="utf-8")
    return str(sp)


def test_generate_writes_all_pages(tmp_path):
    out = tmp_path / "site"
    gen.generate(_snapshot(tmp_path), str(out), "https://site.test", "https://app.test")
    assert (out / "index.html").exists()
    assert (out / "stocks" / "AAPL.html").exists()
    assert (out / "stocks" / "GME.html").exists()
    assert (out / "category" / "momentum-leaders.html").exists()
    assert (out / "sitemap.xml").exists()
    assert (out / "robots.txt").exists()


def test_ticker_page_has_seo_tags_and_escapes(tmp_path):
    out = tmp_path / "site"
    gen.generate(_snapshot(tmp_path), str(out), "https://site.test", "https://app.test")
    aapl = (out / "stocks" / "AAPL.html").read_text(encoding="utf-8")
    assert "<title>AAPL Stock Signals" in aapl
    assert '<link rel="canonical" href="https://site.test/stocks/AAPL.html">' in aapl
    assert 'application/ld+json' in aapl and '"BreadcrumbList"' in aapl
    assert "3 open-market insider buys" in aapl          # real sub-stat surfaced
    gme = (out / "stocks" / "GME.html").read_text(encoding="utf-8")
    assert "8.3 days to cover" in gme
    assert "<script>x</script>" not in gme               # user 'why' is HTML-escaped
    assert "&lt;script&gt;" in gme


def test_sitemap_lists_every_page(tmp_path):
    out = tmp_path / "site"
    gen.generate(_snapshot(tmp_path), str(out), "https://site.test", "https://app.test")
    sm = (out / "sitemap.xml").read_text(encoding="utf-8")
    for loc in ("https://site.test/", "https://site.test/stocks/AAPL.html",
                "https://site.test/stocks/GME.html", "https://site.test/category/short-squeeze.html"):
        assert f"<loc>{loc}</loc>" in sm


def test_generate_empty_snapshot_is_safe(tmp_path):
    sp = tmp_path / "empty.json"
    sp.write_text(json.dumps({"generated_at": "2026-07-02T00:00:00Z", "count": 0, "rows": []}), encoding="utf-8")
    out = tmp_path / "site"
    gen.generate(str(sp), str(out), "https://site.test", "https://app.test")
    assert (out / "index.html").exists()                 # never crashes on an un-warm snapshot
