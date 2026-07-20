# Scanviction — Render Migration Fix Pass (July 20, 2026)

Every issue from your list, what was actually wrong, and what changed. Changed files:
**app.py, signal_engine.py, analytics_store.py, requirements.txt, render.yaml, keepawake.yml** — plus new files **self_kick.py, webpush.py, static/sw.js, static/icon-192.png**. Deploy is a normal git push (Render auto-deploys); two one-time setup steps are flagged ⚙️ below.

---

## 1. Scanner not running until someone clicks a category — ROOT CAUSE FOUND

This was the big one, and it explains several other symptoms (Telegram delays, % since = 0.00%, stale prices, the empty Data Health panel).

**What was happening.** Streamlit only executes `app.py` — and `app.py` is what starts the background scan worker — when a *real browser session* connects. Render keeps the process alive 24/7, but Render's health checks hit `/_stcore/health`, which does **not** create a session. So after every deploy or restart, the scanner sat idle until a human loaded the site. Your keep-awake GitHub Action was supposed to cover this, but its URL defaults to the **old streamlit.app deployment** unless the repo variable `APP_URL` is set — so it was "succeeding" against the wrong site. Result: the first visitor after a deploy found cold categories, clicked one, and watched it warm — hence "only warms on category click."

**The fix — the service now warms itself.** New `self_kick.py` runs inside the same Render container (wired into `render.yaml`'s startCommand). After boot it opens a real Streamlit session against localhost using Streamlit's own websocket protocol, which runs the script and starts the scan worker — within seconds of every deploy/restart, no visitors needed. It then re-kicks every 10 minutes as a watchdog, so if the worker thread ever dies it's revived. I verified this end-to-end against a live Streamlit 1.59 server in a sandbox: server healthy + script never run → kick → script runs.

**9:30 open.** The worker's off-hours sleep could overshoot the open (weekend sleeps are up to 24h, so Monday's first scan could land mid-morning). The sleep is now capped at seconds-until-open, so the first scan of the day fires right at 9:30 ET, then re-scores every 15 minutes (`INTRADAY_RESCORE=900`) through the session. This was always the design — it just never ran unattended before.

**⚙️ One-time:** set the GitHub repo **Variable** `APP_URL` to your Render URL (Settings → Secrets and variables → Actions → Variables). See §22 for whether to keep the action at all.

## 2. Telegram alerts not immediate

Delivery is inline in the scan worker (`_deliver_new_signals` fires the moment a new entry is recorded) — the code was right; the worker just wasn't running (§1). With the self-kick, entries are detected within one 15-minute re-score and pushed instantly. I also made the Settings "Auto-Signals" pause toggle actually gate delivery (it was saved but never checked) and defaulted premium users into the email digest (see §19).

## 3. "% since" stuck at 0.00% + auto-refresh prices

Same root cause: the "% since" figure is *live price vs. the locked entry snapshot*. With the worker dead, the live price never moved off the price the signal was anchored at → permanent 0.00%. Entry anchors were never being reset (they're safe in Postgres) — the "now" side was frozen. With the worker alive, prices refresh every few minutes intraday and the figure accumulates. Note: a signal that entered a category *today* legitimately reads ~0.0% at first — the number grows as the signal ages.

**Auto-refresh is no longer a toggle.** Discover now refreshes automatically — every 2 minutes during market hours, every 10 minutes off-hours. The toggle is gone.

## 4. Breakout Watch appears broken — TWO causes, both fixed

(a) With the worker dead, scans ran on end-of-day bars, and "pressing a fresh 60-day high on heavy volume" only exists *intraday* — by the close it's often gone. The intraday forming-bar logic works once the worker runs all session (§1).

(b) **Real logic bug found once scoring.py arrived:** Breakout Watch's gate requires `vol_ratio ≥ 1.4`, but the intraday bar fed today's **partial** session volume against a **full-day** average. At 10:30 AM a stock trading at twice its normal pace still showed vol_ratio ≈ 0.25, so Breakout Watch — and every volume-gated category (Volatility Expansion, Catalyst/Gap, Capitulation Bottom, Social Catalyst) — could effectively only fire in the last hour of the session. The intraday bar's volume is now **pace-adjusted** (partial volume ÷ fraction of session elapsed, capped at 4× so the noisy open can't over-extrapolate), so a breakout on heavy relative volume is detected from mid-morning onward. The fit thresholds themselves (fresh 60-day high, above 20-day MA, 1.4× volume) are sound — no change needed there.

## 5. Signal Performance — Long/Short now automatic

The Direction dropdown is gone. Direction is derived from the signal itself: bear/short categories (Breakdown, Distribution, Overbought Fade…) measure a short's return, everything else measures long. A small badge shows "📈 LONG position · set by the signal type" (or 📉 SHORT).

## 6. AI Support Chat — 400 error fixed + fully briefed

**Bug:** the Anthropic Messages API requires the first message to be role `user` with strictly alternating roles. Your chat history starts with the assistant's greeting ("Hi! I'm the Scanviction support assistant…"), so *every* request was invalid → HTTP 400. The payload builder now skips leading assistant messages and merges any same-role runs. **Knowledge:** the system prompt now also covers alerts & notification channels, Telegram setup steps, account/billing flows (upgrade path, billing portal, cancel, 30-day refund), on top of the existing categories/features/pricing/data-sources briefing, and it's instructed to defer to support@scanviction.com rather than guess.

## 7. Login lost on navigating to Contact

**Bug:** cookies are disabled (they caused the rerun-loop blanking), so the `?sid=` URL token is the *only* session carrier — and the footer's Contact/Privacy/Terms links were raw `href="?page=contact"` anchors that replaced the whole query string, wiping `sid` → full reload, logged out. Footer links (and the PWA bottom-nav tabs, which had the same bug) now carry `&sid=…`. The Stripe billing-portal return URL and the push-enable redirect had the same hole — both fixed (§16, §18).

## 8. Contact page email prefill

The prefill code was already there — it looked broken because §7 logged you out on the way to the page. With the session held, name + email prefill from the logged-in account.

## 9. Social Buzz table slow to populate

It was doing a per-ticker network fetch (quote + sentiment) for each of 8 names, serially, on every render — while Gainers/Losers read from the warm cache. Social Buzz now reads quote + sentiment straight from the warm scan rows and renders the whole table in a single paint, same as the others.

## 10. Navigation cleanup

- **Discover → back to all categories:** clicking Discover in the navbar now always returns to the all-categories home. Previously, with a category drilled in, it was a silent no-op (page was already "discover").
- **Category click lands mid-page:** scroll-to-top now fires on *any* category change (not just tile clicks — dashboard links and deep links were missing it), with an extra late retry so slow-populating content can't strand you mid-page.
- **Navbar active pill not holding:** several pages (Contact, Features, detail…) called `render_topbar()` without the active-page argument, so the highlight dropped. The topbar now derives the active page from router state automatically.

## 11. Scanner result tiles = wall of text

The conviction-card CSS was only injected on the Dashboard and Discover pages — the Scanner rendered the *same cards with no styles at all*. The card styles are now a shared block injected by the grid renderer itself, so the cards look identical everywhere.

## 12. Brief button count clipped

"🔔 Brief (12)" overflowed its fixed-width pill (`overflow:hidden`). The Brief tab now widens automatically when a count is showing, uses parentheses, and gets tighter padding. No more clipping.

## 13. Admin overview — wrong stats, Yahoo Finance tile

The 1,847 signups / 312 premium / 634 daily active / 16.9% were **hardcoded demo numbers**. The overview now shows real data: verified signups from the funnel, actual premium count from the users DB, real 24-hour distinct-active from Postgres events (new `analytics_store.daily_active()`), real conversion (premium ÷ accounts). The data-source tiles now reflect the actual stack — Polygon, SEC EDGAR, FINRA short interest, ApeWisdom, Twelve Data (optional) — with live health status from the worker's telemetry. Yahoo Finance and StockTwits tiles are gone. The security checklist and "Secrets Setup" card were also updated from Streamlit Cloud instructions to your actual Render secret-file setup.

## 14. API research + panel fix

The panel now splits into "Integrated now" (Polygon paid, SEC EDGAR free, FRED free, ApeWisdom free, news+VADER free) and "Worth adding":

- **Finnhub — best free win.** ~60 calls/min free. The app *already* upgrades its news-direction sentiment automatically if you add `FINNHUB_API_KEY` to Secrets — that's a zero-code improvement today. Their earnings calendar is the next best integration candidate.
- **Alpha Vantage** free tier is now only ~25 requests/day — fine for one daily earnings-calendar/macro pull, useless per-ticker.
- **Twelve Data** free 800 credits/day — already wired as optional quote top-up.
- **Unusual Whales / Benzinga / Finviz Elite** — paid only; skip until revenue justifies (options-flow via Unusual Whales is the strongest future premium differentiator).

Sources: [Alpha Vantage premium/pricing](https://www.alphavantage.co/premium/), [Alpha Vantage API limits](https://www.macroption.com/alpha-vantage-api-limits/), [Finnhub pricing](https://finnhub.io/pricing), [Finnhub rate limits](https://finnhub.io/docs/api/rate-limit).

## 15. Tab spacing (admin + settings)

Tabs get proper gaps, roomier padding, hover states, wrap instead of clipping on narrow widths, and breathing room below the tab row.

## 16. Upgrade/downgrade + billing portal — bugs found in review

- **Admin role Update didn't persist.** It only changed session memory — the role reverted on restart and the alert worker never saw it. Now persisted to the shared store (same for user deletion).
- **Billing portal "nothing happens".** The portal was opened via `window.open()` on a rerun — not a direct user gesture, so popup blockers silently killed it. It's now a real link button. Also, the portal's return URL dropped your session token (you came back logged out) — fixed.

**Live test checklist for you:** (1) Admin → Users → change a test account free↔premium → restart the service → role should stick. (2) Settings → Subscription → Open Billing Portal → button appears → opens Stripe → finish → you land back on Settings *still logged in*. (3) Stripe test-mode checkout end-to-end on a test account. (4) Telegram: connect, wait for the next re-score cycle with a new entry, confirm instant delivery.

## 17. Signal Engine data + Refresh Outcomes + Seed Demo — explained & fixed

**Why every category showed 1W/0L, 100%:** those rows were **seeded demo events** (the Smart Reversal 0W/1L −7.6% row in your screenshot is literally the hardcoded AMD demo event). Changes:

- Demo seeding is now **opt-in** (`SEED_DEMO_SIGNALS=1`) and off in production; seeded events are tagged `demo` and excluded from performance stats.
- New **"🧹 Purge Demo Data"** button in Admin → Signal Engine removes all seeded events (including old untagged ones) — click it once after deploying and the panel becomes real-signals-only.
- **"Refresh Outcomes"** re-prices every tracked signal: fills 1d/3d/5d/10d/20d forward returns, max upside/drawdown, and the win/loss label (events refreshed <2h ago are skipped — that skip plus its other bug is why it "did nothing"). Its other bug: it fetched prices via the **removed Yahoo path**, which silently returned nothing. It now uses Polygon.
- Outcomes also refresh **automatically every hour** inside the worker now (this used to be the retired cron's job — nothing was doing it).
- **"Seed Demo Signal History"** inserts the fake example signals for demos/screenshots. It stays as a dev tool, clearly labeled, and everything it creates is purgeable.

## 18. Push notifications without OneSignal — done (native Web Push)

OneSignal is replaced with **self-hosted Web Push (VAPID)** — the browser-native push standard. No third-party account, no SDK script, no fees; notifications are sent directly from your own alert pipeline (new `webpush.py` + `static/sw.js` service worker + subscribe flow in Settings → Profile). Works on desktop Chrome/Edge/Firefox, Android, and iOS 16.4+ (installed to home screen). Category entries, event filings, digests, and custom alerts all deliver over it for premium users, alongside Telegram and email. Dead subscriptions are pruned automatically. The OneSignal path remains as a fallback only if you already have keys set.

**⚙️ One-time:** generate a VAPID key pair (one-liner in `webpush.py`'s docstring) and add `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL` to your Render secrets file.

**Future app:** when you go native, the same pipeline extends — keep VAPID for web/PWA and add FCM/APNs adapters behind `webpush.py`'s interface. The PWA + push + home-screen install already gets you ~90% of the app feel with zero store friction.

## 19. Premium-SaaS alert defaults

New/premium users now get the premium experience out of the box: push, email, Telegram-when-connected, watchlist, and category alerts all default ON; all 23 categories + the three event types are covered by default (matching what the Settings page already claimed); marketing stays default OFF. The email digest previously required manually picking categories even for premium — premium users are now included by default, and every master toggle (including the Auto-Signals pause) is genuinely enforced in the delivery path.

## 20. Twelve Data "showing nothing" vs Postgres — explained + panel fixed

These are unrelated systems, and the panel was blurring them. **Postgres (DATABASE_URL) is where customer data lives** — accounts, sessions, alerts, signal history, funnel events. That's the green "Durable storage active" banner, and it's correct. **Twelve Data is an optional market-data API** for per-ticker quote top-ups; you haven't set a key, which is fine — market data runs fully on Polygon. The System panel now only shows the credits bar when a key exists, with an explanatory note otherwise. Also fixed: the Data Health table was **always empty** ("No data fetches have run yet…") because its store was reset on every rerun — the worker's health records were invisible. It's now a persistent singleton, so you'll actually see Polygon/worker health there.

## 21. Pop-in / loading jank + navbar state

Fixed the concrete causes found: unstyled-then-styled card flash on the scanner (shared CSS, §11), row-by-row table pop-in on Social Buzz (single-paint, §9), navbar active pill dropping (§10), scroll-position jumps on category entry (§10), and the earlier page-enter fade replay was already removed in styles.css. The remaining "streaming in" of sections top-to-bottom is inherent to how Streamlit renders; the biggest perceived-speed win left is that pages now serve from an always-warm cache instead of cold-loading (§1).

## 22. Do we still need the keep-awake job?

**Render never sleeps your paid service, so "keep-awake" was never about sleep on Render** — it existed to start the scan worker after deploys (§1). With `self_kick.py`, that job is handled inside the container. Recommendation: point `APP_URL` at the Render URL and keep the action for a week as an external backup/uptime probe while you verify the self-kick in Render logs (look for `[self-kick] session kicked — worker running`), then either delete it or dial it down to `*/30` as a free uptime monitor. It costs nothing on a public repo, but it's no longer load-bearing.

---

## Deploy notes

1. Commit all changed/new files (zip attached — `static/sw.js` and `static/icon-192.png` must be committed so Streamlit serves them).
2. Render picks up `render.yaml`'s new startCommand on the next deploy. Check logs for the `[self-kick]` lines.
3. Add the VAPID keys to the Render secret file (§18) whenever you want push live — everything else works without them.
4. Set the GitHub repo variable `APP_URL` (§1/§22).
5. In Admin → Signal Engine, click **Purge Demo Data** once.
6. Optional free win: add `FINNHUB_API_KEY` to secrets (§14).

## Verification done here

All edited files compile clean, and with scoring.py in hand the **full project test suite passes: 98/98** (test_seo.py excluded — `seo_generate.py` wasn't uploaded; it's the standalone SEO site generator and untouched by these changes). The self-kick sidecar was verified end-to-end against a live Streamlit 1.59 server in a sandbox.
