#!/usr/bin/env python3
"""
filter.py - Binary filter (Pass/Reject) - prepare jobs for LLM evaluation
Output: ~/.openclaw/workspace/jobs_filtered.json (PASS jobs only)
"""
import json
import os
import sys

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
# Allow override via command line argument or environment variable
if len(sys.argv) > 1:
    INPUT_FILE = sys.argv[1]
elif os.getenv("INPUT_FILE"):
    INPUT_FILE = os.getenv("INPUT_FILE")
else:
    INPUT_FILE = os.path.join(WORKSPACE, "jobs_raw.json")

PROFILE_FILE = os.path.join(WORKSPACE, "scan_job_candidate_profile.json")
OUTPUT_FILE = os.path.join(WORKSPACE, "jobs_filtered.json")

def load_files():
    with open(INPUT_FILE) as f:
        jobs = json.load(f)
    with open(PROFILE_FILE) as f:
        profile = json.load(f)
    return jobs, profile

def should_pass(job, profile):
    """Binary decision: True = send to LLM, False = reject
    
    STRICT location filter:
    - ACCEPT: Fully Remote
    - ACCEPT: APAC cities only (Singapore, Bangkok, Ho Chi Minh, Hong Kong, etc.)
    - REJECT: Everything else (US, EU, Hybrid, On-site)
    
    Keyword filter (relaxed):
    - If location OK → PASS (bỏ keyword requirement)
    - If location BAD → REJECT (regardless of keywords)
    - Exception: if has strong must-have keywords → PASS even if location is sub-optimal
    """
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    location = (job.get("location") or "").lower()
    text = title + " " + description
    
    # 1. CHECK EXCLUDE KEYWORDS (auto-reject)
    exclude_roles = profile.get("exclude_roles", [])
    for keyword in exclude_roles:
        if keyword.lower() in title:
            return False, f"Exclude keyword in title: {keyword}"
    
    # 2. STRICT LOCATION FILTER (whitelist approach)
    # List of accepted remote keywords
    remote_keywords = ["remote", "fully remote", "work from home", "distributed"]
    is_remote = any(r in location for r in remote_keywords) or any(r in title for r in remote_keywords)
    
    # List of ACCEPTED APAC cities/regions
    apac_cities = [
        "singapore", "bangkok", "ho chi minh", "hcm", "hanoi", "vietnam",
        "hong kong", "hk", "taipei", "taiwan", "seoul", "south korea",
        "tokyo", "japan", "sydney", "australia", "dubai", "uae",
        "kuala lumpur", "malaysia", "manila", "philippines", "jakarta", "indonesia",
        "penang", "ang mo kio", "marina bay", "changi"
    ]
    is_apac = any(city in location for city in apac_cities)
    
    # Rejection logic: HARD NO on non-remote non-APAC
    if not is_remote and not is_apac:
        return False, f"Location not Remote or APAC: {location}"
    
    # 3. CHECK EXCLUDE ROLES AGAIN (in description)
    for keyword in exclude_roles:
        if keyword.lower() in title:
            return False, f"Exclude keyword found: {keyword}"
    
    # 4. ACCEPTANCE LOGIC
    # If location is good (remote OR apac) → PASS
    # (We'll let LLM decide if it's actually a good fit)
    if is_remote or is_apac:
        location_status = "Remote" if is_remote else f"APAC ({location})"
        return True, f"Location OK: {location_status}"
    
    # Should not reach here, but as fallback
    return False, f"Location check failed: {location}"

def main():
    print("🔍 Binary keyword filter (Pass/Reject)...")
    print()
    
    jobs, profile = load_files()
    
    passed = []
    rejected = []
    
    for job in jobs:
        should_keep, reason = should_pass(job, profile)
        
        if should_keep:
            job["filter_reason"] = reason
            passed.append(job)
        else:
            job["reject_reason"] = reason
            rejected.append(job)
    
    # Save ONLY passed jobs
    os.makedirs(WORKSPACE, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(passed, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Filter complete:")
    print(f"   Total input: {len(jobs)} jobs")
    print(f"   PASS (→ LLM): {len(passed)} jobs")
    print(f"   REJECT: {len(rejected)} jobs")
    print()
    print(f"💾 Saved to: {OUTPUT_FILE}")
    
    # Show rejection breakdown
    rejection_reasons = {}
    for job in rejected:
        reason = job.get("reject_reason", "Unknown")
        key = reason.split(":")[0]  # Group by reason type
        rejection_reasons[key] = rejection_reasons.get(key, 0) + 1
    
    print()
    print("📊 Rejection reasons:")
    for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1]):
        print(f"   - {reason}: {count}")

if __name__ == "__main__":
    main()
