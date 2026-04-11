#!/usr/bin/env python3
"""role_quality.py - Tầng A: role quality scoring (0 API)

Input:  ~/.openclaw/workspace/jobs_filtered.json
Output:
  - ~/.openclaw/workspace/jobs_role_quality_scored.json
  - ~/.openclaw/workspace/jobs_shortlist.json (top N, default 50)

Focus: rank jobs by Product/Growth/Research quality signals.
Penalty: BD/Sales/Payment roles even if labelled "growth".
"""

import json
import os
import re
import sys
from urllib.parse import urlparse

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
INPUT_FILE = os.path.join(WORKSPACE, "jobs_filtered.json")
SCORED_FILE = os.path.join(WORKSPACE, "jobs_role_quality_scored.json")
SHORTLIST_FILE = os.path.join(WORKSPACE, "jobs_shortlist.json")

DEFAULT_TOP_N = 50

# --------------------------- helpers ---------------------------

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def canonical_url(u: str) -> str:
    if not u:
        return ""
    try:
        p = urlparse(u)
        return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
    except Exception:
        return u

def word_hits(text: str, patterns):
    hits = []
    for pat in patterns:
        if re.search(pat, text, flags=re.I):
            hits.append(pat)
    return hits

# --------------------------- heuristics ---------------------------

GARBAGE_TITLE_PATTERNS = [
    r"\blatest\s+crypto\s+jobs\b",
    r"\bcrypto\s+jobs\b",
    r"\bjob\s+board\b",
    r"^\s*careers\s*$",
    r"\bwe'?re\s+hiring\b",
    r"\bjoin\s+our\s+team\b",
]

GARBAGE_URL_PATTERNS = [
    r"cryptojobslist\.com/?$",
    r"web3career(s)?\.(com|io)/?$",
]

HARD_REJECT_PATTERNS = [
    r"commission\s+only",
    r"unpaid",
]

# BD/Sales roles that often masquerade as "growth" — penalise hard
BD_SALES_PENALTY_TITLE = [
    r"\bbusiness\s*development\b",
    r"\bbusiness\s*partner(ship)?\b",
    r"\bstrategic\s*partner(ship)?\b",
    r"\bpartnership\s*manager\b",
    r"\bpartnership\s*director\b",
    r"\binstitutional\s*(sales|partner|growth|bd)\b",
    r"\bvip\b",
    r"\bpayment\s*partner\b",
    r"\bsales\s*manager\b",
    r"\bsales\s*director\b",
    r"\baccount\s*(manager|executive|director)\b",
    r"\bclient\s*(success|relations|partner)\b",
    r"\bbroker\b",
    r"payment\s*\(",            # "BD - Payment (LATAM)"
    r"\blatin\s*america\b",
    r"\blatam\b",
    r"\bmena\b",
    r"\bafrica\b",
    r"\bcis\s*region\b",
]

# Bucket detection — strict patterns to avoid mislabelling BD as growth
BUCKET_PATTERNS = {
    "product": [
        r"\bproduct\s*manager\b",
        r"\bsenior\s*pm\b",
        r"\bstaff\s*pm\b",
        r"\bproduct\s*ops\b",
        r"\bproduct\s*strategy\b",
        r"\bproduct\s*analyst\b",
        r"\bhead\s*of\s*product\b",
        r"\bvp\s*(of\s*)?product\b",
        r"\bproduct\s*lead\b",
        r"\bproduct\s*owner\b",
    ],
    "growth": [
        r"\bgrowth\s*manager\b",
        r"\bgrowth\s*lead\b",
        r"\bgrowth\s*hacker\b",
        r"\bgrowth\s*marketer\b",
        r"\bhead\s*of\s*growth\b",
        r"\bperformance\s*marketing\b",
        r"\blifecycle\s*market\w+\b",
        r"\bcommunity\s*manager\b",
        r"\becosystem\s*growth\b",
        r"\bgrowth\s*engineer\b",
        r"\buser\s*acquisition\b",
        r"\bmarketing\s*manager\b",
        r"\bmarketing\s*lead\b",
        r"\bhead\s*of\s*marketing\b",
    ],
    "research": [
        r"\bresearch\w*\b",
        r"\banalyst\b",
        r"\bmarket\s*intelligence\b",
        r"\binvestment\s*research\b",
        r"\bon-?chain\s*research\b",
        r"\bcrypto\s*research\b",
        r"\btokenomics\b",
        r"\becosystem\s*(manager|lead|analyst)\b",
    ],
}

# Quality signals: product (weight 1.0x)
PRODUCT_SIGNALS = {
    "metrics":         ([r"north\s*star", r"\bkpi\b", r"\bmetrics\b", r"\bcohort\b", r"\bretention\b", r"\bfunnel\b"], 10),
    "experimentation": ([r"a\/?b\s*test", r"\bexperiment\b", r"\bhypothesis\b"], 10),
    "discovery":       ([r"user\s*research", r"\bdiscovery\b", r"problem\s*space", r"customer\s*interview"], 8),
    "strategy":        ([r"product\s*strategy", r"\broadmap\b", r"\bprioritization\b", r"\bokr\b", r"trade-?off"], 8),
    "execution":       ([r"cross-?functional", r"\bstakeholder\b", r"\bprd\b", r"\brequirements\b"], 6),
    "0to1":            ([r"0\s*[-–to]{1,3}\s*1", r"zero\s*to\s*one", r"\bgreenfield\b"], 8),
}

# Quality signals: growth (weight 0.9x)
GROWTH_SIGNALS = {
    "perf":      ([r"performance\s*marketing", r"paid\s*social", r"google\s*ads", r"\btiktok\b", r"meta\s*ads"], 10),
    "seo":       ([r"\bseo\b", r"\baso\b", r"content\s*strategy"], 8),
    "lifecycle": ([r"\blifecycle\b", r"\bcrm\b", r"\bemail\s*market", r"push\s*notification", r"\bsegmentation\b"], 10),
    "loops":     ([r"growth\s*loop", r"\breferral\b", r"\bviral\b"], 8),
    "analytics": ([r"\battribution\b", r"\bcohort\b", r"\bfunnel\b", r"\bretention\b", r"\bltv\b", r"\bcac\b"], 8),
    "community": ([r"\bcommunity\s*manager\b", r"\bambassador\b", r"\bguild\b", r"\bkols?\b"], 6),
    "ecosystem": ([r"ecosystem\s*growth", r"developer\s*relations", r"\bdevrel\b", r"ecosystem\s*manager"], 8),
}

# Quality signals: research (weight 0.7x)
RESEARCH_SIGNALS = {
    "crypto":    ([r"tokenomics", r"on-?chain", r"market\s*structure", r"\bvaluation\b", r"due\s*diligence", r"investment\s*memo"], 15),
    "analysis":  ([r"market\s*research", r"competitive\s*analysis", r"industry\s*report", r"trend\s*analysis"], 10),
    "data":      ([r"\bsql\b", r"\bpython\b", r"\bdune\b", r"\bnansen\b", r"on-chain\s*data"], 8),
}

# Weights by bucket preference
BUCKET_WEIGHT = {
    "product":  1.00,
    "growth":   0.90,
    "research": 0.70,
    "other":    0.20,
}

BD_PENALTY = -30  # applied before weight

def detect_bucket(text: str) -> str:
    scores = {}
    for b, pats in BUCKET_PATTERNS.items():
        scores[b] = len(word_hits(text, pats))
    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else "other"

def is_garbage(job, text):
    title = norm(job.get("title") or "")
    url = canonical_url(job.get("url") or "")
    if word_hits(title, GARBAGE_TITLE_PATTERNS):
        return True, "garbage_title"
    if url and word_hits(url, GARBAGE_URL_PATTERNS):
        return True, "garbage_url"
    if len(text) < 80:
        return True, "too_thin"
    return False, ""

def hard_reject(text):
    return bool(word_hits(text, HARD_REJECT_PATTERNS))

def score_quality(bucket: str, title_text: str, full_text: str):
    """title_text = title only (for penalty check); full_text = all fields combined"""
    tags = []
    score = 0
    penalty = 0

    # BD/Sales penalty: check title specifically
    bd_hits = word_hits(title_text, BD_SALES_PENALTY_TITLE)
    if bd_hits:
        penalty += BD_PENALTY
        tags.append(f"bd_penalty({len(bd_hits)})")

    def apply_signals(prefix, signals):
        nonlocal score
        for name, (pats, pts) in signals.items():
            if word_hits(full_text, pats):
                score += pts
                tags.append(f"{prefix}:{name}")

    if bucket == "product":
        apply_signals("product", PRODUCT_SIGNALS)
    elif bucket == "growth":
        apply_signals("growth", GROWTH_SIGNALS)
    elif bucket == "research":
        apply_signals("research", RESEARCH_SIGNALS)
    else:
        if re.search(r"analytics|data|sql|python|dashboard", full_text, flags=re.I):
            score += 6
            tags.append("other:analytics")

    # Richness bonus
    if len(full_text) > 800:
        score += 8
        tags.append("rich_jd")
    elif len(full_text) > 400:
        score += 4
        tags.append("jd_ok")

    raw = score + penalty
    w = BUCKET_WEIGHT.get(bucket, 0.2)
    weighted = raw * w
    weighted = round(weighted, 2)
    return weighted, tags


# --------------------------- main ---------------------------

def main():
    top_n = DEFAULT_TOP_N
    if len(sys.argv) > 1:
        try:
            top_n = int(sys.argv[1])
        except Exception:
            pass

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    scored = []
    rejected = []

    for j in jobs:
        title = j.get("title") or ""
        desc = j.get("description") or ""
        company = j.get("company") or ""
        location = j.get("location") or ""

        title_norm = norm(title)
        full_text = norm(" ".join([title, company, location, desc]))

        if hard_reject(full_text):
            j["role_quality_decision"] = "reject"
            j["role_quality_reason"] = "hard_reject_pattern"
            rejected.append(j)
            continue

        garb, reason = is_garbage(j, full_text)
        if garb:
            j["role_quality_decision"] = "reject"
            j["role_quality_reason"] = reason
            rejected.append(j)
            continue

        bucket = detect_bucket(full_text)
        score, tags = score_quality(bucket, title_norm, full_text)

        j2 = dict(j)
        j2["role_bucket"] = bucket
        j2["role_quality_score"] = score
        j2["role_quality_tags"] = tags
        j2["role_quality_decision"] = "keep"
        j2["role_quality_reason"] = ";".join(tags[:6])
        j2["url_canon"] = canonical_url(j2.get("url") or "")

        scored.append(j2)

    # Dedup by (company, title) OR canonical url
    seen = set()
    deduped = []
    for j in sorted(scored, key=lambda x: x.get("role_quality_score", 0), reverse=True):
        key = (norm(j.get("company") or ""), norm(j.get("title") or ""))
        u = j.get("url_canon")
        k2 = (u,) if u else None
        if key in seen or (k2 and k2 in seen):
            continue
        seen.add(key)
        if k2:
            seen.add(k2)
        deduped.append(j)

    shortlist = deduped[:top_n]

    os.makedirs(WORKSPACE, exist_ok=True)
    with open(SCORED_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "input": os.path.basename(INPUT_FILE),
                "total_input": len(jobs),
                "kept_for_scoring": len(scored),
                "rejected": len(rejected),
                "deduped": len(deduped),
                "shortlist_n": top_n,
            },
            "jobs": deduped
        }, f, ensure_ascii=False, indent=2)

    with open(SHORTLIST_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "meta": {
                "generated_from": os.path.basename(SCORED_FILE),
                "shortlist_n": top_n,
            },
            "jobs": shortlist
        }, f, ensure_ascii=False, indent=2)

    # Print summary
    bucket_counts = {}
    for j in shortlist:
        b = j.get("role_bucket", "other")
        bucket_counts[b] = bucket_counts.get(b, 0) + 1

    print("✅ Role quality scoring done")
    print(f"Input: {len(jobs)} | rejected: {len(rejected)} | deduped: {len(deduped)} | shortlist: {len(shortlist)}")
    print("Shortlist buckets:", bucket_counts)
    print("Top 10:")
    for i, j in enumerate(shortlist[:10], 1):
        print(f"{i}. [{j.get('role_quality_score')}] {j.get('title')} @ {j.get('company')} ({j.get('location')})\n   {j.get('url')}")

if __name__ == "__main__":
    main()
