"""Shared pytest setup for the Scanviction suite.

Everything here runs BEFORE the test modules import the app's modules, so this is
where we make the environment hermetic: storage is redirected to a throwaway dir,
the Postgres backend is disabled (JSON-file mode), demo seeding is off, and the
background universe worker is prevented from starting (it would otherwise hit the
live market-data API on import, since app.py runs top-to-bottom with no __main__
guard). The Streamlit "missing ScriptRunContext" log spam is silenced too.
"""
import os
import sys
import tempfile
import logging

# Make the project root importable (scoring/signal_engine/msp_store/app live there).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Hermetic environment — set before ANY project import below or in test modules.
os.environ.pop("DATABASE_URL", None)                              # force JSON-file mode
os.environ.setdefault("MSP_DATA_DIR", tempfile.mkdtemp(prefix="msp_tests_"))
os.environ.setdefault("SEED_DEMO_ACCOUNTS", "0")                  # no demo accounts
os.environ.setdefault("MSP_DISABLE_WORKER", "1")                  # no live scanner thread

logging.getLogger("streamlit").setLevel(logging.CRITICAL)

import math
import pandas as pd
import pytest


@pytest.fixture(scope="session")
def app():
    """The Streamlit monolith, imported ONCE for unit-testing its pure helpers.
    Storage is redirected to a temp dir and the worker is disabled (see above)."""
    import app as _app
    return _app


@pytest.fixture
def make_ohlcv():
    """Factory for a deterministic OHLCV frame (no RNG → reproducible across runs).
    `seed` varies the shape; `n` is the number of daily bars."""
    def _make(seed=0, n=60):
        opens, highs, lows, closes, vols = [], [], [], [], []
        p = 50.0 + seed
        for i in range(n):
            p = max(1.0, p * (1 + 0.02 * math.sin((i + seed) / 3.0)
                              + 0.001 * ((i * 7 + seed) % 11 - 5)))
            o = p * (1 + 0.003 * math.cos(i + seed))
            opens.append(o); closes.append(p)
            highs.append(max(o, p) * 1.01); lows.append(min(o, p) * 0.99)
            vols.append(1_000_000 * (1 + 0.5 * math.sin((i * 2 + seed) / 4.0))
                        + (i * seed % 5000))
        idx = pd.bdate_range(end=pd.Timestamp("2026-06-26"), periods=n)
        return pd.DataFrame({"datetime": idx, "open": opens, "high": highs,
                             "low": lows, "close": closes, "volume": vols})
    return _make
