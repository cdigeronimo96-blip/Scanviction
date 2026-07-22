# Scanviction — Round 3 Fix Pass (July 22, 2026)

Changed files: **app.py, self_kick.py, render.yaml, styles.css**. Tests: 107/107 passing.

## 1. Duplicate Top Signals on the main page — root cause + fix

Round 2 wrapped the Discover body and the detail performance box in auto-refresh
fragments **dynamically** (`st.fragment(run_every=…)(fn)()`). That mints a NEW fragment
identity on every script run — and the previous identity's scheduled auto-rerun could
still fire and APPEND a second copy of the board. Both are now **statically decorated**
(`@st.fragment(run_every=120)`), the documented pattern with one stable identity. The
flash-free in-place refresh behavior is unchanged (fixed 2-minute cadence).

## 2. "Didn't scan today until I logged in" — three layers of hardening

Evidence gathered: the site was healthy at check time, and the keep-awake GitHub Action
has been green all day — **but GitHub throttles its `*/10` schedule to every 1.5–2.5
hours in practice**, so it's a weak backup. If the in-container watchdog dies, the
scanner can sit idle for hours. Three failure modes are now closed:

1. **self_kick gave up permanently on a slow boot.** If Streamlit wasn't healthy within
   5 minutes (slow build/deploy), `self_kick.py` logged "giving up" and EXITED — no
   watchdog until the next deploy. It now waits forever, and an outer supervisor
   (`run_forever`) restarts `main()` if anything unexpected escapes.
2. **The self_kick PROCESS could die with no restart** (e.g. OOM kill). render.yaml's
   startCommand now runs it under a shell supervisor loop that relaunches it in 30s.
3. **A HUNG worker thread was undetectable.** `ensure_universe_worker` only checked the
   thread NAME was alive — a worker stuck in a no-timeout network call passed that check
   forever while scans and notifications silently stopped ("it was running but stopped
   sending"). The worker now stamps a per-second heartbeat, and every session/self-kick/
   keep-awake ping checks it: heartbeat older than 30 min → a replacement worker thread
   is started and the stall is recorded to Data Health.

## 3. Intermittent page timeouts

The full re-score is a tight pandas loop (~45s over ~2,500 tickers) in a background
thread of the SAME process serving web requests — Python's GIL let it starve the web
server during every scan cycle, which is exactly "timing out here and there." The loop
now yields the GIL briefly every 25 tickers (~0.5s added per warm). If timeouts persist
after this, the next step up is moving the scan to a separate process/worker service.

## 4. Telegram / email delivery — found one real bug + made failures visible

- **Real bug: email alerts from the scanner could never send.** `_alert_email` read
  `RESEND_API_KEY` via `st.secrets` — which is only reliable on the MAIN thread. From
  the worker thread (where all signal delivery runs) a failed read silently returned ""
  and the function no-opped. The key (plus EMAIL_FROM / APP_URL) is now captured on the
  main thread at startup, exactly like the Telegram token and Polygon key already were.
- **Silent failure everywhere, fixed with observability.** The whole delivery pass was
  wrapped in a bare `except: pass`; Telegram sends returned False with no trace on HTTP
  errors (blocked bot, bad chat id, HTML rejects). Now: every Telegram/Resend response
  is recorded to **Admin → System → Data Health** (`telegram_alerts`, `email_alerts`
  rows, with the HTTP status/error text), each delivery cycle records an `alerts`
  summary row (events seen, users checked, channel key status), and unexpected delivery
  crashes print a full traceback to the Render logs.

**How to verify delivery now:** Admin → System → Data Health after the next re-score
with a new signal — the `alerts` row shows the cycle ran; `telegram_alerts` /
`email_alerts` rows show per-channel success or the exact error.

## 5. Double password-reveal eye on the reset form

Edge on Windows injects its own reveal eye INSIDE every password input, on top of
Streamlit's reveal toggle beside the field — two eyeballs. `styles.css` now suppresses
the browser-native one (`input::-ms-reveal { display:none }`); Streamlit's stays.
