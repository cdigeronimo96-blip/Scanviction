# Scanviction — Round 2 Fix Pass (July 20, 2026)

Second pass on the post-Render-migration issues. Changed files: **app.py, scoring.py, render.yaml**.
No new dependencies, no new setup steps — deploy is a normal git push.

---

## 1. Cards now show WHEN a signal was recommended, and prices keep updating

- Every "% since" surface (Top Signals cards, category cards, landing hero) now shows the
  actual **signal timestamp** — e.g. `Jul 19, 9:45am ET · 1d ago` — not just a relative age.
- The stock **detail page previously froze the price at the moment you clicked the card**
  (it reused the click-time snapshot for the whole visit). It now always prefers the warm
  scan row's quote, which the worker refreshes in place every few minutes — so the header
  price and the Signal Performance "Current" track the live 15-minute scan.
- The **Signal Performance box is now an auto-refreshing fragment**: every 2 minutes during
  market hours it re-reads the live quote and updates in place — no full-page rerun, no flash.
- "Held" shows hours/minutes on day one (`3h`) instead of a flat `0d`.

## 2. Top Signals shows winners only (and measures shorts as shorts)

- The board pulls a deep pool (24), loads each pick's locked entry snapshot, and **drops any
  pick that's underwater in its own called direction**. Longs must be flat-or-green since
  their signal; a short whose stock has FALLEN is a *winner* and stays — labeled with the
  SHORT badge and its "% since (short)" measured as the short's return (decline = green +).
- Fresh signals with no snapshot yet aren't losers — they backfill remaining slots so the
  board never sits empty.
- Same rule applied to the public landing hero feed.
- **Bug found while doing this:** the detail page's Long/Short badge compared
  `category_dir(...) == "short"`, but that function returns `"bear"`/`"bull"` — so every
  signal displayed as LONG. Fixed; Breakdown / Distribution / Overbought Fade signals now
  correctly show 📉 SHORT and measure the short's return.
- **Consistency bug fixed:** a card could say "Signaled 1d ago · +4.2% since" while the
  detail page said "no prior signal" (the two read different stores). Signal Performance
  now falls back to the locked Discover snapshot when no signal-engine event exists, so
  both surfaces agree on entry, timestamp and return.

## 3. Random screen flash eliminated

The flash was Discover's auto-refresh: `streamlit_autorefresh` forced a **full-page rerun
every 2 minutes**, which tears down and repaints the whole page. Both Discover and the
detail page's performance box now refresh via **fragment-scoped `run_every`** — Streamlit
re-renders only that section, in place, with the page chrome untouched. Data still updates
on the same cadence (2 min market hours / 10 min off-hours); the flash is gone.

## 4. Catalyst / Gap now scores the catalyst's QUALITY, not just its size

The old fit was `gap size + volume + 8-K bonus`. It now weighs, per your list:

| Factor | How it's measured |
|---|---|
| What's the news? | Fresh SEC 8-K filing = confirmed catalyst (+14) |
| Is it justified? | **Gap-hold**: trading beyond its open = buyers justifying it (+10); fading back through the open = penalized (−8). Money flow (CMF) agreeing with the gap's direction adds +6. |
| Potential | Gap magnitude (capped so one huge gap can't drown the quality factors) |
| Volume since | Today's volume vs 20-day average (pace-adjusted intraday) |
| Volume held over period | 5-day vs prior-15-day volume trend (+ up to 20) |

The card's "why" now reads e.g. *"Gapped +7% on 3.1× volume with a fresh SEC 8-K
(confirmed news), gap holding and volume staying elevated."*

## 5. Social Catalyst was structurally empty — fixed

Every stock gets ONE best-fit category (argmax over all fits). Social Catalyst's fit was
weighted so low that a genuinely viral name **always scored higher in some generic
technical category** (Volatility Expansion, Momentum Surge…), so Social Catalyst nearly
never won the argmax and sat permanently empty. The fit is rebalanced around its signature
(mention count, 24h buzz trend, trending-list membership, volume confirmation) so a real
social spike now outscores the technical fallbacks. It also now requires the buzz to be
*rising* (buzz trend ≥ +25%, or trending, or heavy mentions) — matching the category's
"catalyst-driven attention TODAY" promise.

Note: social data comes from the free ApeWisdom feed. If the category still looks quiet,
check Admin → System → Data Health for the `apewisdom` row — if it's failing, that's a
data-source outage, not the category.

## 6. Category click landing mid-page — actually fixed this time

The scroll-to-top script was injected via `st.html`, and **browsers do not execute
`<script>` tags inserted that way** — so the reset never ran reliably. It's now rendered
through `components.html` (a same-origin iframe, where scripts are guaranteed to run), and
the retry tail extends to ~2.6s so the reset still wins after the category's content
finishes streaming in.

## 7. Category open speed

On entering a category the app batch-refreshed stale quotes and then **re-ran the whole
category scoring pull even when nothing was refreshed**. The second pull now only happens
when at least one quote actually updated (with the worker alive, quotes are already fresh,
so this usually skips entirely).

## 8. Daily Brief now shows "% since"

Each signal row in the Daily Brief shows the live percent move since that signal's trigger
price (same figure and direction rules as Discover — shorts labeled and measured as shorts),
next to the trigger price.

## 9. "Still not scanning until someone clicks" — deployment, not code ⚙️

The code already self-warms: `self_kick.py` opens a real local session at boot and the scan
worker then runs 24/7 (9:30 open + 15-min re-scores). **But two deployment gaps mean it may
never have activated on your service:**

1. **Your GitHub repo had no folders** (the web "upload files" flow skipped them), so
   `.github/workflows/keep-awake.yml`, `static/sw.js`, `tests/`, `.streamlit/config.toml`
   were never deployed. This push restores the full tree.
2. **If the Render service was created manually (not via Blueprint), Render IGNORES
   `render.yaml`'s startCommand** — so `self_kick.py` never launches. Check:
   Render dashboard → your service → Settings → **Start Command**. It must match the
   startCommand in `render.yaml` (the one that runs `python self_kick.py &` before
   streamlit). Then watch the deploy logs for:
   `[self-kick] session kicked — worker running`.
   **No `[self-kick]` lines in the logs = the scanner will stay idle until a visitor.**
3. Backup: set the GitHub repo **Variable** `APP_URL` to your Render URL so the keep-awake
   Action (now actually on GitHub) opens a real browser session every 10 minutes as an
   external warm-up.

*(Verified from the live Render logs after deploy: `[self-kick] session kicked — worker
running` every ~10 min and `[polygon] warm: scored 2497/2505 tickers` every cycle — the
scanner runs continuously with no visitors. The only cold window left is the ~2-3 minutes
right after each deploy while the first market-wide warm completes.)*

## 10. Follow-up: dashboard teaser winners-only + Streamlit deprecation

- The dashboard's "Today's Top Signals" 3-card teaser was a third surface calling the
  ranking directly and still showed losers — it now uses the same winners-only filter as
  the Discover board and the landing hero.
- The `st.components.v1.html is deprecated` log warning: all five remaining uses (Stripe
  checkout, OneSignal + native Web Push subscribe, two scroll-to-top helpers) REQUIRE the
  deprecated API's same-origin srcdoc iframe — the replacement (`st.iframe`, data: URL =
  opaque origin) breaks Stripe.js, the OneSignal SDK, service-worker registration and
  parent-page scrolling alike. They are all annotated in code, and `requirements.txt` now
  pins `streamlit>=1.40,<1.60` so a future Streamlit release can't remove the API out from
  under the payment path mid-deploy. Bump the ceiling deliberately, after testing checkout
  + push + scroll on the new version.
