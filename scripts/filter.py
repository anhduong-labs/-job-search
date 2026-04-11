#!/usr/bin/env python3
"""
filter.py - Filter + Score jobs
Output: ~/.openclaw/workspace/jobs_filtered.json (sorted by score desc)
"""
import json
import os
import sys

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")

if len(sys.argv) > 1:
    INPUT_FILE = sys.argv[1]
elif os.getenv("INPUT_FILE"):
    INPUT_FILE = os.getenv("INPUT_FILE")
else:
    INPUT_FILE = os.path.join(WORKSPACE, "jobs_raw.json")

OUTPUT_FILE = os.path.join(WORKSPACE, "jobs_filtered.json")

# ─── FILTER RULES ─────────────────────────────────────────────────────────────

# Location: chỉ giữ Remote hoặc APAC
REMOTE_KEYWORDS = ["remote", "fully remote", "work from home", "distributed", "work remotely"]
APAC_LOCATIONS = [
    "singapore", "bangkok", "ho chi minh", "hcm", "hanoi", "vietnam",
    "hong kong", "hk", "taipei", "taiwan", "seoul", "south korea",
    "tokyo", "japan", "sydney", "australia", "dubai", "uae",
    "kuala lumpur", "malaysia", "manila", "philippines", "jakarta", "indonesia",
]

# Role: giữ lại nếu title chứa ít nhất 1 keyword này
INCLUDE_ROLE_KEYWORDS = [
    "product", "growth", "research", "researcher", "analyst", "analytics",
    "business development", "bd", "partnerships", "marketing", "content",
    "strategy", "operations", "ops", "community", "ecosystem",
]

# Role: loại bỏ nếu title chứa bất kỳ keyword này
EXCLUDE_ROLE_KEYWORDS = [
    "engineer", "engineering", "developer", "dev ", "backend", "frontend",
    "fullstack", "full-stack", "full stack", "solidity", "smart contract",
    "blockchain developer", "software", "devops", "sre", "infrastructure",
    "hr", "human resources", "recruiter", "recruiting", "talent acquisition",
    "legal", "counsel", "compliance", "attorney", "lawyer",
    "accountant", "accounting", "finance manager", "controller",
    "designer", "ui/ux", "ux designer", "graphic",
    "ceo", "cto", "cfo", "chief",
]

# Luôn reject nếu là portal/listing page
SUSPICIOUS_TITLES = ["latest crypto jobs", "crypto jobs", "job board", "careers"]
SUSPICIOUS_URLS = ["https://cryptojobslist.com", "https://web3.career"]

# ─── SCORING ──────────────────────────────────────────────────────────────────

# Bonus score dựa theo role keywords khớp trong title
ROLE_SCORE_MAP = {
    "research": 30,
    "researcher": 30,
    "analyst": 25,
    "analytics": 20,
    "product": 20,
    "growth": 20,
    "strategy": 15,
    "business development": 15,
    "bd": 15,
    "partnerships": 15,
    "ecosystem": 10,
    "operations": 10,
    "ops": 10,
    "community": 10,
    "marketing": 10,
    "content": 5,
}

# Bonus score theo location
LOCATION_SCORE_MAP = {
    "remote": 30,
    "fully remote": 30,
    "distributed": 25,
    "singapore": 20,
    "hong kong": 18,
    "hk": 18,
    "vietnam": 20,
    "ho chi minh": 20,
    "hcm": 20,
    "hanoi": 18,
    "thailand": 15,
    "bangkok": 15,
    "taiwan": 12,
    "south korea": 12,
    "seoul": 12,
    "japan": 12,
    "tokyo": 12,
    "australia": 10,
    "sydney": 10,
    "malaysia": 10,
    "philippines": 10,
    "indonesia": 8,
}

# Bonus nếu description chứa web3/crypto keywords
WEB3_KEYWORDS = [
    "web3", "crypto", "blockchain", "defi", "nft", "dao", "token",
    "on-chain", "onchain", "protocol", "wallet", "dapp", "layer 2",
    "layer2", "solana", "ethereum", "base chain", "polygon",
]


def score_job(job):
    """Score job từ 0-100 dựa theo role, location, và web3 relevance"""
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    location = (job.get("location") or "").lower()

    score = 0

    # Role score (max ~30)
    for keyword, pts in ROLE_SCORE_MAP.items():
        if keyword in title:
            score += pts
            break  # chỉ tính keyword khớp đầu tiên để không bị cộng quá

    # Location score (max ~30)
    for keyword, pts in LOCATION_SCORE_MAP.items():
        if keyword in location:
            score += pts
            break

    # Web3/Crypto relevance (max 20)
    web3_hits = sum(1 for kw in WEB3_KEYWORDS if kw in title or kw in description[:500])
    score += min(web3_hits * 5, 20)

    # Seniority bonus (nếu title có senior/lead/head)
    if any(w in title for w in ["senior", "lead", "head of", "principal", "director"]):
        score += 10
    # Penalize nếu quá junior
    if any(w in title for w in ["intern", "internship", "junior", "entry"]):
        score -= 10

    return max(0, min(score, 100))


def should_pass(job):
    """True nếu job qua filter, kèm lý do"""
    title = (job.get("title") or "").lower()
    location = (job.get("location") or "").lower()
    url = (job.get("url") or "").lower()

    # 0. Reject portal/listing pages
    if any(k in title for k in SUSPICIOUS_TITLES):
        return False, "Portal page"
    if url.rstrip("/") in SUSPICIOUS_URLS:
        return False, "Suspicious URL"

    # 1. Reject excluded roles (check title)
    for kw in EXCLUDE_ROLE_KEYWORDS:
        if kw in title:
            return False, f"Excluded role: {kw}"

    # 2. Location filter: phải là Remote (không bị gắn US/EU) hoặc APAC
    # Non-APAC regions: nếu location chứa những này thì reject dù có "remote"
    non_apac_regions = [
        "united states", ", us", "(us)", "us,", "usa", "u.s.",
        "new york", "san francisco", "california", "texas", "chicago",
        "london", "united kingdom", ", uk", "(uk)", "uk,", "u.k.",
        "germany", "france", "netherlands", "spain", "italy", "sweden",
        "europe", "eu,", "(eu)", ", eu",
        "canada", "toronto", "vancouver",
        "brazil", "sao paulo", "mexico city", "argentina", "colombia",
        "latam", "latin america",
    ]

    is_apac = any(city in location for city in APAC_LOCATIONS)
    is_non_apac = any(r in location for r in non_apac_regions)

    # Remote OK nếu không bị gắn non-APAC location
    raw_remote = any(r in location for r in REMOTE_KEYWORDS) or any(r in title for r in REMOTE_KEYWORDS)
    is_remote = raw_remote and not is_non_apac

    if not is_remote and not is_apac:
        return False, f"Not remote/APAC: {location or 'unknown'}"

    # 3. Role filter: title phải chứa ít nhất 1 included keyword
    has_included_role = any(kw in title for kw in INCLUDE_ROLE_KEYWORDS)
    if not has_included_role:
        return False, f"Role not in scope: {title}"

    loc_label = "Remote" if is_remote else location
    return True, f"OK ({loc_label})"


def main():
    print("🔍 Filter + Score jobs...")
    print()

    with open(INPUT_FILE) as f:
        jobs = json.load(f)

    passed = []
    rejected = []
    reject_reasons = {}

    for job in jobs:
        keep, reason = should_pass(job)
        if keep:
            job["filter_reason"] = reason
            job["fit_score"] = score_job(job)
            passed.append(job)
        else:
            job["reject_reason"] = reason
            rejected.append(job)
            key = reason.split(":")[0]
            reject_reasons[key] = reject_reasons.get(key, 0) + 1

    # Sort by score (cao → thấp)
    passed.sort(key=lambda x: x.get("fit_score", 0), reverse=True)

    os.makedirs(WORKSPACE, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(passed, f, indent=2, ensure_ascii=False)

    print(f"✅ Filter xong:")
    print(f"   Input:   {len(jobs)} jobs")
    print(f"   Passed:  {len(passed)} jobs")
    print(f"   Rejected:{len(rejected)} jobs")
    print()
    print("📊 Rejection breakdown:")
    for reason, count in sorted(reject_reasons.items(), key=lambda x: -x[1]):
        print(f"   - {reason}: {count}")
    print()
    if passed:
        print("🏆 Top 3:")
        for j in passed[:3]:
            print(f"   [{j.get('fit_score',0)}] {j.get('title')} @ {j.get('company')} ({j.get('location','')})")

    print(f"\n💾 Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
