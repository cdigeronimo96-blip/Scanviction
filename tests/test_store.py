"""msp_store.py — write_json must be atomic (never leaves a torn/partial file)."""
import json
import os
import threading
import msp_store as ms


def test_write_json_valid_and_no_leftover_tmp(tmp_path):
    key = str(tmp_path / "store.json")
    ms.write_json(key, {"a": 1, "b": [1, 2, 3], "n": None})
    assert json.load(open(key)) == {"a": 1, "b": [1, 2, 3], "n": None}
    leftovers = [f for f in os.listdir(tmp_path) if f.startswith("store.json.tmp")]
    assert leftovers == []                       # temp file was replaced, not left behind


def test_concurrent_writes_never_corrupt_the_file(tmp_path):
    """Atomic replace means a reader/concurrent writer can never observe a partial
    file: after N racing writers the file is always valid JSON equal to exactly one
    writer's payload (last-writer-wins is fine; a torn read is not)."""
    key = str(tmp_path / "concur.json")
    ms.write_json(key, {"init": True})
    payloads = [{"writer": i, "blob": "x" * 5000} for i in range(60)]

    threads = [threading.Thread(target=ms.write_json, args=(key, p)) for p in payloads]
    for t in threads: t.start()
    for t in threads: t.join()

    loaded = json.load(open(key))                # must not raise (no torn file)
    assert loaded in payloads


def test_read_json_default_on_missing(tmp_path):
    missing = str(tmp_path / "nope.json")
    assert ms.read_json(missing, default=[]) == []
    assert ms.read_json(missing, default={"d": 1}) == {"d": 1}
