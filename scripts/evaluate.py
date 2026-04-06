#!/usr/bin/env python3
"""
evaluate.py - LLM-based job evaluation (Stage 2)
Input: jobs_filtered.json (from binary filter)
Output: jobs_evaluated.json (with archetype, grade, analysis)
"""
import sys
sys.stdout.reconfigure(line_buffering=True)
import json
import os
import time
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
INPUT_FILE = os.path.join(WORKSPACE, "jobs_filtered.json")
PROFILE_FILE = os.path.join(WORKSPACE, "scan_job_candidate_profile.json")
OUTPUT_FILE = os.path.join(WORKSPACE, "jobs_evaluated.json")

# Allow override via command line
if len(sys.argv) > 1:
    INPUT_FILE = sys.argv[1]
if len(sys.argv) > 2:
    OUTPUT_FILE = sys.argv[2]

# ezai proxy (OpenAI-compatible)
EZAI_BASE_URL = "https://ezaiapi.com/v1"
EZAI_API_KEY = os.getenv("EZAI_API_KEY", "")
EZAI_MODEL = "claude-haiku-4-5"  # Fast & cheap for batch evaluation

# Rate limit: monthly_starter = 2 concurrent, 30 RPM
MAX_WORKERS = 2


def load_files():
    with open(INPUT_FILE) as f:
        jobs = json.load(f)
    with open(PROFILE_FILE) as f:
        profile = json.load(f)
    return jobs, profile


def create_evaluation_prompt(job, profile):
    candidate_summary = """
CANDIDATE PROFILE:
- Name: Duong Nguyen
- Experience: 6+ years in Web3/crypto
- Previous roles:
  * Head of R&D at Ancient8 (gaming L2, $10M funding)
    - Built 10+ native products (launchpad, NFT marketplace, gaming infra)
    - Scaled product 0 → 1M+ users
    - Designed $A8 tokenomics & airdrop (65k+ DAU, listed on Coinbase)
  * Head of Research at Kyros Ventures (crypto VC)
    - Evaluated 200+ Web3 startups
    - Produced market reports (100k+ readers)
  * Founder at Elden Labs (Web3 product lab)
    - NFT collections: $2M+ trading volume
    - 10+ collaborations across DeFi, gaming, L1/L2
- Core strengths: ecosystem development, tokenomics, market research, BD, product strategy
- Preferred roles: research, analyst, ecosystem, growth, product
- Location: Open to Remote or APAC
"""
    job_description = f"""
JOB POSTING:
- Title: {job.get('title', 'N/A')}
- Company: {job.get('company', 'N/A')}
- Location: {job.get('location', 'N/A')}
- Description: {job.get('description', 'N/A')[:800]}
"""
    prompt = f"""{candidate_summary}
{job_description}

EVALUATE THIS JOB:

1. Archetype: Ecosystem | Research | Growth | Product | Other
2. Grade:
   - A: Perfect match, apply immediately
   - B: Strong match, high priority
   - C: Decent match, worth considering
   - D: Weak match
   - F: No match, skip
3. Match reasons (3 bullets max)
4. Gaps (1-2 max)
5. Priority (1-10)

Respond ONLY with valid JSON:
{{
  "archetype": "Ecosystem|Research|Growth|Product|Other",
  "grade": "A|B|C|D|F",
  "score": 85,
  "match_reasons": ["reason1", "reason2", "reason3"],
  "gaps": ["gap1"],
  "priority": 8
}}"""
    return prompt


def evaluate_job(job, profile, client):
    """Call Claude via ezai proxy with retry on 429"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            prompt = create_evaluation_prompt(job, profile)
            message = client.chat.completions.create(
                model=EZAI_MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = message.choices[0].message.content.strip()

            # Strip markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            evaluation = json.loads(response_text)
            job["evaluation"] = evaluation
            job["eval_status"] = "success"
            return job

        except Exception as e:
            err = str(e)
            if "429" in err and attempt < max_retries - 1:
                wait = 15 * (attempt + 1)
                print(f"    ⏳ Rate limit, retry sau {wait}s...")
                time.sleep(wait)
                continue
            print(f"    ⚠️  Error: {job.get('title', '')[:40]}: {err[:80]}")
            job["eval_status"] = "error"
            job["eval_error"] = err
            return job


def main():
    print(f"🤖 LLM evaluation ({EZAI_MODEL}, {MAX_WORKERS} parallel)...")
    print()

    jobs, profile = load_files()
    print(f"   Jobs to evaluate: {len(jobs)}")
    print()

    client = OpenAI(
        base_url=EZAI_BASE_URL,
        api_key=EZAI_API_KEY,
        default_headers={"User-Agent": "EzAI/1.0"}
    )

    evaluated_jobs = [None] * len(jobs)

    def eval_worker(args):
        i, job = args
        print(f"  [{i+1}/{len(jobs)}] {job.get('title', 'Unknown')[:50]}...")
        result = evaluate_job(job, profile, client)
        return i, result

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for i, result in executor.map(eval_worker, enumerate(jobs)):
            evaluated_jobs[i] = result

    # Save
    os.makedirs(WORKSPACE, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(evaluated_jobs, f, indent=2, ensure_ascii=False)

    # Stats
    success = [j for j in evaluated_jobs if j and j.get("eval_status") == "success"]
    errors = len(evaluated_jobs) - len(success)

    print()
    print(f"✅ Done: {len(success)} success, {errors} errors")

    if success:
        grades = [j["evaluation"]["grade"] for j in success]
        grade_counts = {g: grades.count(g) for g in ["A", "B", "C", "D", "F"]}
        archetypes = {}
        for j in success:
            a = j["evaluation"]["archetype"]
            archetypes[a] = archetypes.get(a, 0) + 1

        print()
        print("📊 Grades:")
        for g in ["A", "B", "C", "D", "F"]:
            print(f"   {g}: {grade_counts.get(g, 0)}")

        print()
        print("📋 Archetypes:")
        for a, c in sorted(archetypes.items(), key=lambda x: -x[1]):
            print(f"   {a}: {c}")

    print()
    print(f"💾 Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
