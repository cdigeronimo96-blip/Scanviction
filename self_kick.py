#!/usr/bin/env python3
"""
Scanviction — self-kick sidecar (runs INSIDE the Render web container).

WHY THIS EXISTS
---------------
Streamlit only executes app.py — and therefore only starts the in-process
universe/scan worker — when a REAL browser session connects. Render keeps the
process alive 24/7, but its health checks hit /_stcore/health, which does NOT
create a session. So after every deploy/restart the scanner sat idle until a
human (or the GitHub keep-awake action) happened to load the site — the
"nothing scans until someone clicks a category" bug.

This sidecar removes that dependency entirely: it waits for the local Streamlit
port to come up, then opens a real session against localhost using Streamlit's
own websocket protocol (a BackMsg rerun request — exactly what the browser
frontend sends). One kick runs app.py top-to-bottom, which calls
ensure_universe_worker() and starts the daemon scan thread. It then re-kicks
every SELF_KICK_INTERVAL seconds as a watchdog (idempotent — the worker-start
guard makes extra kicks free), so even if the worker thread ever dies the next
kick revives it.

Launched from render.yaml's startCommand:
    python self_kick.py &
    streamlit run app.py ...

Zero external services required. The GitHub keep-awake action is now optional
(useful only as an external uptime monitor).
"""
import os
import sys
import time
import urllib.request

PORT = os.environ.get("PORT", "8501")
BASE = f"http://127.0.0.1:{PORT}"
INTERVAL = int(os.environ.get("SELF_KICK_INTERVAL", "600"))   # re-kick cadence (s)
HOLD = int(os.environ.get("SELF_KICK_HOLD", "20"))            # keep session open (s)
BOOT_TIMEOUT = int(os.environ.get("SELF_KICK_BOOT_TIMEOUT", "300"))


def _log(msg):
    try:
        sys.stderr.write(f"[self-kick] {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def _wait_for_server(timeout=BOOT_TIMEOUT):
    """Block until Streamlit's health endpoint answers (server booted)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/_stcore/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _kick_once():
    """Open a real Streamlit session and request a script run, then hold it
    open briefly. Returns True if the server accepted the rerun request."""
    import websocket  # websocket-client (in requirements.txt)
    from streamlit.proto.BackMsg_pb2 import BackMsg

    ws = websocket.create_connection(
        f"ws://127.0.0.1:{PORT}/_stcore/stream",
        timeout=15,
        origin=BASE,
        subprotocols=["streamlit", "PLACEHOLDER_AUTH_TOKEN"],
    )
    try:
        bm = BackMsg()
        bm.rerun_script.query_string = ""
        ws.send(bm.SerializeToString(), opcode=0x2)  # binary frame
        # Drain a few ForwardMsgs so the session counts as active, then hold.
        ws.settimeout(5)
        got = 0
        end = time.time() + HOLD
        while time.time() < end:
            try:
                data = ws.recv()
                if data:
                    got += 1
            except Exception:
                time.sleep(1)
        return got > 0
    finally:
        try:
            ws.close()
        except Exception:
            pass


def main():
    if os.environ.get("SELF_KICK_DISABLE") == "1":
        _log("disabled via SELF_KICK_DISABLE=1")
        return
    if not _wait_for_server():
        _log(f"server never became healthy on port {PORT}; giving up")
        return
    _log(f"server healthy on :{PORT} — kicking a session to start the scan worker")
    while True:
        try:
            ok = _kick_once()
            _log("session kicked — worker running" if ok
                 else "kick sent but no ForwardMsg received (will retry)")
        except Exception as e:
            _log(f"kick failed: {type(e).__name__}: {e} (will retry)")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
