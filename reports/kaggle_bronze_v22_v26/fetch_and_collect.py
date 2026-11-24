#!/usr/bin/env python3
"""Download and parse Kaggle trnphc15122004/silver saved versions 22-26 (Bronze runs)."""

import csv
import json
import os
import re
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi

ROOT = Path(__file__).resolve().parent
VERSIONS = [22, 23, 24, 25, 26]


def decode_session_log(raw_log_json: str) -> str:
    try:
        events = json.loads(raw_log_json)
        return "".join(ev.get("data", "") for ev in events if isinstance(ev, dict))
    except Exception:
        return raw_log_json


def main():
    api = KaggleApi()
    api.authenticate()

    for v in VERSIONS:
        v_dir = ROOT / f"v{v:02d}"
        v_dir.mkdir(parents=True, exist_ok=True)
        raw_log = api.kernels_logs(f"trnphc15122004/silver/{v}")
        (v_dir / "session.json").write_text(raw_log, encoding="utf-8")
        decoded = decode_session_log(raw_log)
        (v_dir / "session.log").write_text(decoded, encoding="utf-8")
        print(f"Downloaded v{v:02d}: session.json={len(raw_log)} bytes, session.log={len(decoded)} chars")


if __name__ == "__main__":
    main()
