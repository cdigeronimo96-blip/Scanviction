# MarketSignalPro — Architecture

A Streamlit web app that scores ~2,500 liquid US stocks every cycle and surfaces
"here are the stocks with a notable setup right now" across composite signal categories,
with alerts, a detail page, a screener, auth, and Stripe billing.

This document maps the codebase after the 2026 decomposition (the bulk of the logic was
pulled out of the original `app.py` monolith into focused, mostly-pure modules).

## Module map

| File | Lines | Responsibility | Streamlit / state? |
|------|------:|----------------|--------------------|
| `app.py` | ~10.6k | Streamlit UI (pages, nav, CSS), routing, the warm-universe worker, the universe build + Polygon/EDGAR/FRED enrichment glue, quote helpers. The "everything not yet extracted." | Yes (the app) |
| `scoring.py` | ~510 | `compute_scores`, `compute_factors`, `precompute_indicators` (shared RSI/MA/MACD computed once), `assign_categories`, the 15+ composite categories, conviction model. | Pure |
| `signal_engine.py` | ~760 | Signal-event history: `record_signal_event(s_bulk)`, `update_signal_outcomes` (forward-horizon labeling), category performance stats, ML confidence, demo seed. | Pure-ish (file I/O) |
| `polygon_adapter.py` / `edgar_adapter.py` / `fred_adapter.py` | — | Whole-market OHLCV + snapshots (Polygon); 8-K / Form-4 insider (SEC EDGAR); macro regime (FRED). | Network |
| `alerts_worker.py` | ~390 | Background cron: reads the shared stores, delivers push/Telegram/email alerts. | Standalone process |
| **Extracted pure modules** | | | |
| `kvstore.py` | ~145 | Key→document storage seam: Postgres `kv_store` OR atomic JSON files (`_read_json`/`_write_json`, DB-first reads, dual-write gated). | Pure |
| `msp_store.py` | ~170 | The SHARED store (app + worker) — canonical paths + read/write. Near-twin of kvstore but the cross-process one. | Pure |
| `recs_store.py` | ~135 | Recommendation snapshot store: `record_recommendations_bulk`, `_prune_recs` (bounded growth), the `__universe__` ML anchors. | st only for the lock |
| `auth_store.py` | ~165 | Accounts + sessions: users/alerts saves (locked), session tokens, pending Stripe upgrades, seed accounts, the shared users DB. | st only for lock + secrets |
| `perf_eval.py` | ~160 | Pure performance/outcome math: `compute_performance`, the horizon-labeling framework (`evaluate_recommendation`, `category_hit_rates`). | Pure |
| `advice.py` | ~80 | `get_recommendation` (BUY/WATCH/HOLD/AVOID), `get_insights` (plain-English badges), `risk_color`. | Pure |
| `security.py` | ~40 | Password hashing (bcrypt + legacy sha256 verify) + HTML escaping (`_esc`). | Pure |
| `theme.py` | ~15 | Brand color palette (single source of truth). | Pure constants |
| `market_utils.py` | ~50 | `market_status` (US market hours + countdown), `_fmt_countdown`. | Pure |

**Decomposition pattern:** each extracted module is imported back into `app.py` under the
SAME names, so every call site is unchanged. The `st.session_state`-coupled glue (e.g.
`_toggle_watchlist`, `render_market_timer`, login/signup UI) stays in `app.py` and uses the
imports. No circular imports: the pure modules depend only on each other / stdlib, never on
`app`.

## Data flow (warm path)

```
_universe_worker (daemon, app.py)                    [leader-only, multi-replica safe]
  └─ _build_universe_raw  → Polygon grouped-daily OHLCV + snapshots
                            + EDGAR (8-K / Form-4) + FRED (regime) enrichment
  └─ per ticker: precompute_indicators → compute_scores + compute_factors (scoring.py)
  └─ assign_categories  → each row gets its primary composite category
  └─ record_recommendations_bulk("__universe__", …)  (recs_store.py → kvstore)   [+ _prune_recs]
  └─ _record_category_entries / _record_event_signals → record_signal_events_bulk (signal_engine)
UI request path: build_scored_universe() serves the warm cache; _warm_index() gives O(1) lookups.
```

## Storage / persistence

All persistence is key→document. With `DATABASE_URL` set + a psycopg driver, each logical
"file" is one row in `kv_store(key TEXT PK, value JSONB)`; otherwise atomic JSON files under
`MSP_DATA_DIR` (default `.msp_data/`). `app.py` uses `kvstore.py`; the worker + app share
`msp_store.py` for the same rows. Writes are atomic (temp file + `os.replace`); concurrent
read-modify-write is serialized by process-wide `cache_resource` locks (`_STORE_LOCK`,
`_RECS_LOCK`).

## Tests

```
pip install -r requirements-dev.txt
pytest                      # 54 hermetic tests, ~8s, no network
```
`tests/conftest.py` makes runs hermetic: temp `MSP_DATA_DIR`, JSON-file mode (no DB), demo
seeding off, and `MSP_DISABLE_WORKER=1` so importing the monolith doesn't start the live
scanner. Coverage: scoring (incl. indicator-reuse byte-equivalence), signal engine (bulk +
outcomes), store atomicity, security, session/auth integration, recs prune, perf/labeling,
advisory decision tree, market hours.

## Running locally

```
streamlit run app.py
# Useful env:
#   SEED_DEMO_ACCOUNTS=1   seed demo@/premium@ showcase accounts (NEVER in prod)
#   MSP_DISABLE_WORKER=1   don't start the background scanner (tests/tooling)
#   MSP_DATA_DIR=...       data dir (default ./.msp_data)
#   DATABASE_URL=...       Postgres (Neon/Supabase) for durable, multi-replica storage
```
Secrets (`.streamlit/secrets.toml`): `POLYGON_API_KEY`, Stripe keys, owner/admin account
hashes, optional Resend / Anthropic / Telegram / OneSignal. No Polygon key → falls back to a
legacy yfinance/FMP universe.

## Known deferrals

- `app.py` is still large (~10.6k lines). The remaining core — the warm worker / universe
  build, the quote layer (session-state API keys + `st.cache_data` + the TD-usage counter),
  and the UI pages + CSS — is stateful/network/visual and wants a dedicated, screenshot-
  verified effort, not mechanical extraction.
- Stripe embedded checkout + OneSignal push intentionally remain on the deprecated
  `st.components.v1.html` (they load external SDKs that need a real same-origin iframe;
  see `_html_iframe` for the migrated visual blocks).
