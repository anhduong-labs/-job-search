#!/usr/bin/env python3
"""validate_output.py - quick sanity checks for crawl/filter outputs.

Usage:
  python3 scripts/validate_output.py ~/.openclaw/workspace/jobs_raw.json
  python3 scripts/validate_output.py ~/.openclaw/workspace/jobs_filtered.json

Reports:
- total jobs
- by source
- % empty descriptions by source
- suspicious titles (aggregator/careers)
"""

import json
import re
import sys
from collections import Counter

SUS_TITLE = [
    r"\blatest\s+crypto\s+jobs\b",
    r"\bcrypto\s+jobs\b",
    r"\bjob\s+board\b",
    r"\bcareers\b",
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def main():
    if len(sys.argv) < 2:
        print("pass a json file path")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    total = len(jobs)
    src = Counter(j.get("source") for j in jobs)
    empty_by_src = Counter()
    susp = []

    for j in jobs:
        s = j.get("source")
        if not (j.get("description") or "").strip():
            empty_by_src[s] += 1
        title = norm(j.get("title"))
        if any(re.search(p, title) for p in SUS_TITLE):
            susp.append((j.get("source"), j.get("title"), j.get("url")))

    print(f"File: {path}")
    print(f"Total jobs: {total}")
    print("By source:")
    for k, v in src.most_common():
        print(f"  - {k}: {v}")

    print("Empty descriptions by source:")
    for k, v in empty_by_src.most_common():
        pct = (v / src[k] * 100) if src[k] else 0
        print(f"  - {k}: {v}/{src[k]} ({pct:.1f}%)")

    if susp:
        print("\nSuspicious titles (first 20):")
        for s, t, u in susp[:20]:
            print(f"  - [{s}] {t} | {u}")


if __name__ == "__main__":
    main()
