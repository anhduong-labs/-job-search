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
    """Crawl cryptojobslist.com

    Previously this function added the homepage/listing as a fake "job" with an
    empty description. That pollutes downstream scoring/evaluation.

    Until we implement per-job detail extraction, we skip this source.
    """
    print("  ⏭️  Skipping cryptojobslist.com (detail parsing not implemented)")
    return []

def crawl_jobspy(profile):
    """Crawl qua JobSpy (LinkedIn, Indeed, Google, v.v.)"""
    print("  🌐 Crawling via JobSpy (LinkedIn, Indeed, Google)...")
    jobs = []
    try:
        from jobspy import scrape_jobs
        import pandas as pd

        keywords = ["web3", "crypto", "blockchain"]
        search_locations = [
            "Remote",
            "Ho Chi Minh City, Vietnam",
            "Hanoi, Vietnam",
            "Singapore",
            "Bangkok, Thailand",
            "Hong Kong",
        ]

        for keyword in keywords:
            for location_target in search_locations:
                try:
                    result = scrape_jobs(
                        site_name=["linkedin", "indeed"],
                        search_term=keyword,
                        location=location_target,
                        results_wanted=20,
                        linkedin_fetch_description=False,
                        hours_old=168
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
                            "location": str(row.get("location", location_target)),
                            "url": str(row.get("job_url", "")),
                            "date_crawled": datetime.now().strftime("%Y-%m-%d"),
                            "date_posted": str(row.get("date_posted", "")),
                            "salary": str(row.get("min_amount", "")),
                            "description": str(row.get("description", ""))[:800]
                        })
                    print(f"    ✅ [{keyword}][{location_target}]: +{len(result)} jobs")
                except Exception as e:
                    print(f"    ⚠️  [{keyword}][{location_target}]: {e}")

    except ImportError:
        print("    ⚠️  JobSpy not installed, skipping")
    return jobs

def crawl_lever(profile):
    """Crawl từ Lever companies (Binance, Uniswap, Aave, Chainlink, Kraken, Immutable)

    Goal: produce a non-empty description/snippet per job (for downstream role-quality scoring)
    without fetching too much (keep it lightweight).
    """
    print("  🏢 Crawling Lever companies...")
    jobs = []

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("    ⚠️  BeautifulSoup not installed, skipping Lever crawl")
        return jobs

    def fetch_html(u: str) -> str:
        req = Request(u, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Referer': 'https://jobs.lever.co/',
        })
        with urlopen(req, timeout=20) as res:
            return res.read().decode('utf-8', errors='ignore')

    def extract_lever_snippet(job_html: str, max_chars: int = 600) -> str:
        soup = BeautifulSoup(job_html, 'html.parser')
        # Lever job page: main content is usually inside .content or .posting
        container = soup.find('div', class_=re.compile(r"content|posting")) or soup.body
        if not container:
            return ""
        text = container.get_text("\n", strip=True)
        # Basic cleanup
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:max_chars]

    lever_companies = [
        ("Binance", "https://jobs.lever.co/binance"),
        ("Kraken", "https://jobs.lever.co/kraken"),
        ("Uniswap Labs", "https://jobs.lever.co/uniswaplabs"),
        ("Aave", "https://jobs.lever.co/aave"),
        ("Chainlink", "https://jobs.lever.co/chainlink"),
        ("Immutable", "https://jobs.lever.co/immutable"),
    ]

    # Limit per company to avoid heavy crawling
    per_company_limit = int(os.getenv('LEVER_LIMIT_PER_COMPANY', '60'))

    for company_name, url in lever_companies:
        try:
            html = fetch_html(url)
            soup = BeautifulSoup(html, 'html.parser')

            postings = soup.find_all('div', class_='posting')
            if not postings:
                postings = soup.find_all('div', class_=lambda x: x and 'posting' in x)

            count = 0
            for posting in postings:
                if count >= per_company_limit:
                    break
                try:
                    # Lever listings: 'Apply' button is not the title. Real title often in .posting-title / h5.
                    title_elem = (
                        posting.find('a', class_=re.compile(r"posting-title"))
                        or posting.find('h5')
                        or posting.find(['h2', 'a'], class_=re.compile('title|posting'))
                    )
                    title = title_elem.get_text(" ", strip=True) if title_elem else None
                    if title:
                        title = re.sub(r"\bRemote\s*[—-].*$", "", title).strip()  # remove trailing location stub
                        if title.lower() == 'apply':
                            title = None

                    location_elem = posting.find(['span', 'div'], class_=re.compile('location|category'))
                    location = location_elem.get_text(strip=True) if location_elem else "Unknown"

                    link_elem = posting.find('a', href=True)
                    job_url = link_elem['href'] if link_elem else url
                    if job_url and not job_url.startswith('http'):
                        job_url = url.rstrip('/') + '/' + job_url.lstrip('/')

                    if not (title and title.strip() and job_url):
                        continue

                    # Fetch snippet via Lever API (fast + stable)
                    snippet = ""
                    try:
                        # Lever API returns rich plain text fields for most postings
                        api_url = f"https://api.lever.co/v0/postings/{url.split('/')[-1]}/{job_url.rstrip('/').split('/')[-1]}?mode=json"
                        api_req = Request(api_url, headers={
                            'User-Agent': 'Mozilla/5.0',
                            'Accept': 'application/json'
                        })
                        import json as _json
                        api_data = _json.loads(urlopen(api_req, timeout=20).read().decode('utf-8','ignore'))
                        snippet = (api_data.get('descriptionPlain') or api_data.get('descriptionBodyPlain') or api_data.get('additionalPlain') or '')
                        snippet = snippet.strip().replace('\u00a0',' ')
                        snippet = snippet[:600]
                    except Exception:
                        # fallback to HTML parsing
                        try:
                            job_html = fetch_html(job_url)
                            snippet = extract_lever_snippet(job_html)
                        except Exception:
                            snippet = ""

                    jobs.append({
                        "source": "lever",
                        "title": title.strip(),
                        "company": company_name,
                        "location": location.strip() if location else "Unknown",
                        "url": job_url,
                        "date_crawled": datetime.now().strftime("%Y-%m-%d"),
                        "date_posted": "",
                        "salary": "",
                        "description": snippet
                    })
                    count += 1
                except Exception:
                    pass

            if count > 0:
                print(f"    ✅ {company_name}: {count} jobs")
            else:
                print(f"    ⚠️  {company_name}: No jobs found")

        except Exception as e:
            print(f"    ⚠️  {company_name} error: {e}")

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
    all_jobs += crawl_lever(profile)

    unique_jobs = deduplicate(all_jobs)

    os.makedirs(WORKSPACE, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(unique_jobs, f, indent=2, ensure_ascii=False)

    print()
    print(f"✅ Crawl xong: {len(unique_jobs)} jobs (sau khi deduplicate)")
    print(f"   - web3career: {len([j for j in unique_jobs if j['source']=='web3career'])}")
    print(f"   - cryptojobslist: {len([j for j in unique_jobs if j['source']=='cryptojobslist'])}")
    print(f"   - linkedin: {len([j for j in unique_jobs if j['source']=='linkedin'])}")
    print(f"   - lever: {len([j for j in unique_jobs if j['source']=='lever'])}")
    print(f"💾 Lưu vào: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
