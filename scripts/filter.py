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
    
    REJECT if:
    - Has exclude keywords (engineer, developer, etc.)
    - Blocked location (Mexico, LatAm, Africa, etc.)
    - No must-have keywords AND no nice-to-have keywords
    
    PASS if:
    - Has ≥1 must-have keyword OR ≥2 nice-to-have keywords
    - Location OK (Remote, APAC, or acceptable)
    - No exclude keywords
    """
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    location = (job.get("location") or "").lower()
    text = title + " " + description
    
    # 1. CHECK EXCLUDE KEYWORDS (auto-reject)
    exclude_roles = profile.get("exclude_roles", [])
    for keyword in exclude_roles:
        if keyword.lower() in title:  # Only check title for exclude keywords
            return False, f"Exclude keyword in title: {keyword}"
    
    # 2. CHECK BLOCKED LOCATIONS (auto-reject)
    blocked_locations = [
        "mexico", "africa", "latam", "latin america", "south america",
        "brazil", "argentina", "colombia", "nigeria", "kenya", "south africa",
        "cairo", "lagos", "nairobi", "johannesburg"
    ]
    for loc in blocked_locations:
        if loc in location:
            return False, f"Blocked location: {loc}"
    
    # 3. CHECK LOCATION PREFERENCE (must be Remote OR APAC)
    remote_field = (job.get("remote") or "").lower()
    is_remote = any(r in remote_field for r in ["remote", "fully remote", "work from home", "hybrid"])
    
    preferred_locations = profile.get("preferred_locations", [])
    location_match = any(loc.lower() in location for loc in preferred_locations)
    
    if not (is_remote or location_match):
        # Allow US/Europe remote jobs, but reject non-remote non-APAC
        if not is_remote and location not in ["", "remote"]:
            # Check if it's a major city we should reject
            non_apac_cities = [
                "berlin", "paris", "london", "new york", "chicago", "san francisco",
                "dubai", "istanbul", "moscow", "mumbai", "tokyo", "sydney",
                "toronto", "vancouver", "montreal"
            ]
            if any(city in location for city in non_apac_cities):
                return False, f"Non-APAC city: {location}"
    
    # 4. CHECK MUST-HAVE KEYWORDS (preferred_roles)
    preferred_roles = profile.get("preferred_roles", [])
    role_match = sum(1 for kw in preferred_roles if kw.lower() in text)
    
    # 5. CHECK NICE-TO-HAVE KEYWORDS (preferred_domains)
    preferred_domains = profile.get("preferred_domains", [])
    domain_match = sum(1 for kw in preferred_domains if kw.lower() in text)
    
    # PASS criteria: ≥1 role match OR ≥1 domain match
    if role_match >= 1:
        return True, f"Has {role_match} role keywords"
    elif domain_match >= 1:
        return True, f"Has {domain_match} domain keywords"
    else:
        return False, f"Insufficient keywords (role: {role_match}, domain: {domain_match})"

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
