#!/usr/bin/env python3
"""
job_link_handler.py - Xử lý job URL từ Telegram
Crawl page → lấy title + company → thêm vào Applications sheet
"""
import sys
import json
import os
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
TOKEN_FILE = os.path.join(WORKSPACE, "google_token.json")
CREDENTIALS_FILE = os.path.join(WORKSPACE, "google_credentials.json")

# Sheet ID của Applications
SHEET_ID = os.getenv("JOB_LINK_SHEET_ID", "")
TAB_NAME = "Trang tính1"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def get_sheets_service():
    """Load token + build service"""
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)
    
    with open(CREDENTIALS_FILE) as f:
        cred_data = json.load(f)['installed']
    
    token_data['client_id'] = cred_data['client_id']
    token_data['client_secret'] = cred_data['client_secret']
    
    creds = Credentials.from_authorized_user_info(token_data, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)


def crawl_job_info(url):
    """Crawl page → lấy job title + company"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Cố gắng lấy title từ <title> tag
        title = ""
        company = ""
        
        # Pattern matching từ URL (nếu có)
        # LinkedIn: /jobs/view/{id}/ (title sẽ ở page <h1> hoặc meta tag)
        if 'linkedin.com' in url:
            # Try meta tags
            meta_title = soup.find('meta', {'property': 'og:title'})
            if meta_title and meta_title.get('content'):
                # Format: "Job Title at Company"
                content = meta_title.get('content')
                if ' at ' in content:
                    title, company = content.split(' at ', 1)
                    title = title.strip()
                    company = company.strip()
        
        # safary.club format: /companies/{company}/jobs/{id}-{position}
        elif 'safary.club' in url:
            parts = url.split('/')
            for i, part in enumerate(parts):
                if part == 'companies' and i+1 < len(parts):
                    company = parts[i+1].replace('-', ' ').title()
                if part == 'jobs' and i+1 < len(parts):
                    # Extract position from URL slug
                    job_slug = parts[i+1].split('#')[0]  # Remove hash
                    # Remove ID prefix (e.g., "72760142-business-development-specialist")
                    job_parts = job_slug.split('-')
                    # Skip first part (ID) if it's all digits
                    if job_parts and job_parts[0].isdigit():
                        title = ' '.join(job_parts[1:]).title()
                    else:
                        title = ' '.join(job_parts).title()
        
        # Method 1: <title> tag (Lever format: "Company - Position - Site")
        page_title = soup.title
        if page_title:
            title_text = page_title.get_text().strip()
            # Split by " - "
            parts = [p.strip() for p in title_text.split(' - ')]
            
            # Lever format: "Company - Position - Site"
            # Try to detect: if part contains "Lever Jobs" or "careers", it's likely site name
            if len(parts) >= 2:
                # Check if last part is site name
                site_keywords = ['lever', 'jobs', 'careers', 'job board']
                last_is_site = any(kw.lower() in parts[-1].lower() for kw in site_keywords)
                
                if last_is_site and len(parts) == 3:
                    company = parts[0]
                    title = parts[1]
                elif len(parts) == 2:
                    # Assume first is company, second is position
                    company = parts[0]
                    title = parts[1]
                else:
                    title = parts[0]
                    company = parts[1] if len(parts) > 1 else ""
        
        # Method 2: Nếu chưa có company, tìm từ domain
        if not company:
            domain = urlparse(url).netloc
            # Lấy phần trước .com/.org/etc
            domain_parts = domain.replace('www.', '').split('.')[0]
            company = domain_parts.capitalize()
        
        # Method 3: Cố gắng tìm <h1> tag (job title)
        if not title:
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text().strip()
        
        # Fallback: nếu vẫn không có title, dùng phần query string
        if not title:
            title = f"Job from {company}"
        
        return {
            "position": title[:100],  # Limit 100 chars
            "company": company[:50],
            "url": url,
            "success": True
        }
    
    except Exception as e:
        print(f"    ❌ Error crawling {url}: {e}")
        return {
            "position": "Unknown Position",
            "company": "Unknown Company",
            "url": url,
            "success": False
        }


def append_to_sheet(service, job_info):
    """Append job info vào sheet"""
    try:
        row = [
            job_info["position"],  # A: Position
            job_info["company"],   # B: Company
            job_info["url"],       # C: Job URL
            datetime.now().strftime("%Y-%m-%d"),  # D: Date Added
            "Not Applied",  # E: Status
            ""  # F: Notes
        ]
        
        service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range=f"{TAB_NAME}!A:F",
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()
        
        return True
    except Exception as e:
        print(f"    ❌ Error appending to sheet: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 job_link_handler.py <URL>")
        sys.exit(1)
    
    url = sys.argv[1].strip()
    
    # Validate URL
    if not url.startswith(('http://', 'https://')):
        print(f"❌ Invalid URL: {url}")
        sys.exit(1)
    
    print(f"📝 Processing: {url}")
    print()
    
    # Crawl job info
    print("  🔍 Crawling job info...")
    job_info = crawl_job_info(url)
    
    if not job_info["success"]:
        print(f"    ⚠️  Could not extract all info, using defaults")
    
    print(f"    Position: {job_info['position']}")
    print(f"    Company: {job_info['company']}")
    print()
    
    # Append to sheet
    print("  📋 Adding to Applications sheet...")
    service = get_sheets_service()
    
    if append_to_sheet(service, job_info):
        print(f"    ✅ Added!")
    else:
        print(f"    ❌ Failed to add")
        sys.exit(1)


if __name__ == "__main__":
    main()
