#!/home/chirobo/.openclaw/workspace/jobspy-env/bin/python3
"""
crawl.py - Crawl việc làm từ nhiều nguồn web3
Output: ~/.openclaw/workspace/jobs_raw.json
"""
import json
import os
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError
import re

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
OUTPUT_FILE = os.path.join(WORKSPACE, "jobs_raw.json")
PROFILE_FILE = os.path.join(WORKSPACE, "scan_job_candidate_profile.json")

def load_profile():
    with open(PROFILE_FILE) as f:
        return json.load(f)

def crawl_web3career(profile):
    """Crawl web3career.com"""
    print("  🌐 Crawling web3career.com...")
    jobs = []
    try:
        roles = profile.get("preferred_roles", [])
        domains = profile.get("preferred_domains", [])
        keywords = roles[:3] + domains[:3]

        for keyword in keywords[:3]:
            url = f"https://web3.career/remote+web3-jobs?search={keyword.replace(' ', '+')}"
            req = Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            })
            with urlopen(req, timeout=15) as res:
                html = res.read().decode("utf-8")

            # Basic regex extraction
            pattern = r'<h2[^>]*class="[^"]*job[^"]*"[^>]*>(.*?)</h2>'
            titles = re.findall(pattern, html, re.DOTALL)

            for title in titles[:5]:
                clean_title = re.sub(r"<[^>]+>", "", title).strip()
                if clean_title:
                    jobs.append({
                        "source": "web3career",
                        "title": clean_title,
                        "company": "Unknown",
                        "location": "Remote",
                        "url": url,
                        "date_crawled": datetime.now().strftime("%Y-%m-%d"),
                        "date_posted": "",
                        "salary": "",
                        "description": ""
                    })
    except Exception as e:
        print(f"    ⚠️  web3career error: {e}")
    return jobs

def crawl_cryptojobslist(profile):
    """Crawl cryptojobslist.com"""
    print("  🌐 Crawling cryptojobslist.com...")
    jobs = []
    try:
        url = "https://cryptojobslist.com"
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })
        with urlopen(req, timeout=15) as res:
            html = res.read().decode("utf-8")

        # Extract job listings
        title_pattern = r'<h2[^>]*>(.*?)</h2>'
        company_pattern = r'class="company[^"]*"[^>]*>(.*?)<'
        titles = re.findall(title_pattern, html, re.DOTALL)
        companies = re.findall(company_pattern, html, re.DOTALL)

        for i, title in enumerate(titles[:5]):
            clean_title = re.sub(r"<[^>]+>", "", title).strip()
            clean_company = re.sub(r"<[^>]+>", "", companies[i]).strip() if i < len(companies) else "Unknown"
            if clean_title:
                jobs.append({
                    "source": "cryptojobslist",
                    "title": clean_title,
                    "company": clean_company,
                    "location": "Remote",
                    "url": url,
                    "date_crawled": datetime.now().strftime("%Y-%m-%d"),
                    "date_posted": "",
                    "salary": "",
                    "description": ""
                })
    except Exception as e:
        print(f"    ⚠️  cryptojobslist error: {e}")
    return jobs

def crawl_jobspy(profile):
    """Crawl qua JobSpy (LinkedIn, Indeed, Google, v.v.)"""
    print("  🌐 Crawling via JobSpy (LinkedIn, Indeed, Google)...")
    jobs = []
    try:
        from jobspy import scrape_jobs
        import pandas as pd

        # Tạo keywords phong phú hơn
        key_roles = [
            "research", "analyst", "ecosystem",
            "growth", "product", "product manager",
            "marketing", "community manager"
        ]
        key_domains = ["web3", "crypto", "blockchain", "defi", "l1", "l2", "nft"]

        keywords = []
        for role in key_roles:
            for domain in key_domains[:3]: # Mix role với top 3 domains
                keywords.append(f"{role} {domain}")
        
        # Thêm keywords đơn lẻ quan trọng
        keywords += ["web3 marketing", "crypto analyst", "blockchain research", "growth lead crypto"]

        # Bỏ trùng, giới hạn 15 keywords (đủ cover các role quan trọng)
        keywords = list(dict.fromkeys(keywords))[:15]

        for keyword in keywords:
            try:
                # Crawl từ LinkedIn, Indeed, Google
                # Note: linkedin_fetch_description=False để tránh crash NoneType error
                result = scrape_jobs(
                    site_name=["linkedin", "indeed", "google"],
                    search_term=keyword,
                    location="Remote",
                    results_wanted=20, # Tăng số lượng kết quả mỗi keyword
                    linkedin_fetch_description=False,  # Tắt description để tránh crash, có thể fetch sau từ URL
                    hours_old=72 # Chỉ lấy jobs mới trong 3 ngày qua
                )
                if result is None or result.empty:
                    continue
                    
                for _, row in result.iterrows():
                    if row is None:
                        continue
                    source = str(row.get("site", "jobspy")) if row.get("site") else "jobspy"
                    jobs.append({
                        "source": source,
                        "title": str(row.get("title", "")),
                        "company": str(row.get("company", "")),
                        "location": str(row.get("location", "Remote")),
                        "url": str(row.get("job_url", "")),
                        "date_crawled": datetime.now().strftime("%Y-%m-%d"),
                        "date_posted": str(row.get("date_posted", "")),
                        "salary": str(row.get("min_amount", "")),
                        "description": str(row.get("description", ""))[:800] # Lấy desc dài hơn để filter tốt hơn
                    })
                print(f"    ✅ JobSpy keyword '{keyword}': +{len(result)} jobs")
            except Exception as e:
                print(f"    ⚠️  JobSpy keyword '{keyword}': {e}")

    except ImportError:
        print("    ⚠️  JobSpy not installed, skipping")
    return jobs

def deduplicate(jobs):
    """Xóa job trùng lặp theo URL hoặc title+company"""
    seen = set()
    unique = []
    for job in jobs:
        key = job.get("url") or f"{job.get('title','')}_{job.get('company','')}"
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique

def main():
    print("🔍 Bắt đầu crawl việc làm web3...")
    print(f"   Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    profile = load_profile()
    all_jobs = []

    all_jobs += crawl_web3career(profile)
    all_jobs += crawl_cryptojobslist(profile)
    all_jobs += crawl_jobspy(profile)

    unique_jobs = deduplicate(all_jobs)

    os.makedirs(WORKSPACE, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(unique_jobs, f, indent=2, ensure_ascii=False)

    print()
    print(f"✅ Crawl xong: {len(unique_jobs)} jobs (sau khi deduplicate)")
    print(f"   - web3career: {len([j for j in unique_jobs if j['source']=='web3career'])}")
    print(f"   - cryptojobslist: {len([j for j in unique_jobs if j['source']=='cryptojobslist'])}")
    print(f"   - linkedin: {len([j for j in unique_jobs if j['source']=='linkedin'])}")
    print(f"💾 Lưu vào: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
