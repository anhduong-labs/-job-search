#!/usr/bin/env python3
"""
update_sheet.py - Đẩy jobs_filtered.json lên Google Sheet qua Service Account (không expire)
"""
import json
import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
INPUT_FILE = os.path.join(WORKSPACE, "jobs_filtered.json")
SUMMARY_FILE = os.path.join(WORKSPACE, "job_scan_last_run.json")
SERVICE_ACCOUNT_FILE = os.path.join(WORKSPACE, "google_service_account.json")

SHEET_ID = os.getenv("JOB_SHEET_ID", "")
TAB_MAIN = "scan_job"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_sheets_service():
    """Authenticate với Google Sheets API via Service Account (không expire)"""
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        print("    ✅ Service Account authenticated!")
        return service
    except Exception as e:
        print(f"    ❌ Error loading service account: {e}")
        return None


def get_existing_urls(service):
    """Đọc toàn bộ Job URL ở cột D (D2:D) để dedup"""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=f"{TAB_MAIN}!D2:D"
        ).execute()
        values = result.get('values', [])
        urls = set()
        for row in values:
            if row and len(row) > 0:
                urls.add(row[0].strip())
        return urls
    except Exception as e:
        print(f"    ⚠️  Không đọc được existing URLs: {e}")
        return set()


def clean(s):
    """Clean string để tránh lỗi format"""
    return str(s).replace('|', ' ').replace('\n', ' ').replace('\r', ' ')


def job_to_row(job):
    """Convert job dict thành row values theo schema"""
    desc = job.get("description", "")
    prefixes = [
        'Responsibilities: ', 'Responsibilities:',
        'Requirements: ', 'Requirements:',
        'What you will do: ', 'What you will do:',
        'What You Will Do: ', 'What You Will Do:',
        "What you'll do: ", "What you'll do:",
        "What You'll Do: ", "What You'll Do:",
        'The role: ', 'The role:',
        'The Role: ', 'The Role:',
        'About the role: ', 'About the role:',
        'About the Role: ', 'About the Role:',
        'Job Description: ', 'Job Description:',
        'Role Overview: ', 'Role Overview:',
        'Position Overview: ', 'Position Overview:',
        'Overview: ', 'Overview:',
        'Your responsibilities: ', 'Your responsibilities:',
        'Key responsibilities: ', 'Key responsibilities:',
        'Resposibilities: ', 'Resposibilities:',
    ]
    for prefix in prefixes:
        if desc.startswith(prefix):
            desc = desc[len(prefix):]
            break

    return [
        job.get("date_added", datetime.now().strftime("%Y-%m-%d")),  # A Date Added
        job.get("title", ""),                                       # B Position
        job.get("company", ""),                                     # C Company
        job.get("url", ""),                                         # D Job URL
        job.get("location", ""),                                    # E Location
        job.get("remote", ""),                                      # F Remote
        desc[:300],                                                    # G Job Summary
        job.get("salary", ""),                                      # H Salary
        job.get("status", "New"),                                   # I Status
        job.get("notes", "")                                        # J Notes
    ]


def append_jobs(service, jobs, existing_urls):
    """Append jobs vào sheet"""
    sent = 0
    errors = 0
    skipped_duplicates = 0
    rows_to_append = []

    for job in jobs:
        job_url = (job.get("url") or "").strip()
        if job_url and job_url in existing_urls:
            skipped_duplicates += 1
            print(f"    ↩️  Skip duplicate: {job.get('title','?')} @ {job.get('company','?')}")
            continue

        row = job_to_row(job)
        rows_to_append.append(row)
        if job_url:
            existing_urls.add(job_url)
        print(f"    ✅ {job.get('title','?')} @ {job.get('company','?')} (score: {job.get('fit_score',0)})")
        sent += 1

    # Batch append (50 rows at a time)
    if rows_to_append:
        try:
            service.spreadsheets().values().append(
                spreadsheetId=SHEET_ID,
                range=f"{TAB_MAIN}!A:J",
                valueInputOption="USER_ENTERED",
                body={"values": rows_to_append}
            ).execute()
        except Exception as e:
            print(f"    ❌ Error appending to sheet: {e}")
            errors = len(rows_to_append)
            sent = 0

    return {"sent": sent, "errors": errors, "skipped_duplicates": skipped_duplicates}


def main():
    print("📤 Bắt đầu update Google Sheet qua Google Sheets API...")
    print()

    # Load jobs (flat list, đã sort theo score từ filter.py)
    with open(INPUT_FILE) as f:
        data = json.load(f)

    # Support cả flat list (new) và old dict format
    if isinstance(data, list):
        all_jobs = data
    else:
        all_jobs = data.get("main_fit", []) + data.get("low_fit", [])
    
    # Đảm bảo sort theo score cao → thấp
    all_jobs.sort(key=lambda x: x.get("fit_score", 0), reverse=True)

    # Authenticate
    service = get_sheets_service()
    if not service:
        print("    ❌ Failed to authenticate with Google Sheets")
        return

    # Get existing URLs
    existing_urls = get_existing_urls(service)

    print(f"   Total jobs to send: {len(all_jobs)} → {TAB_MAIN}")
    print(f"   Existing URLs in sheet: {len(existing_urls)}")
    print()

    print(f"  📋 Gửi vào tab '{TAB_MAIN}'...")
    result = append_jobs(service, all_jobs, existing_urls)

    total_sent = result["sent"]
    total_errors = result["errors"]
    total_skipped = result["skipped_duplicates"]

    print()
    print(f"✅ Update Sheet xong: {total_sent} jobs gửi, {total_skipped} duplicate skip, {total_errors} lỗi")

    summary = {
        "status": "success" if total_errors == 0 else "partial",
        "total_sent": total_sent,
        "skipped_duplicates": total_skipped,
        "errors": total_errors,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "top_jobs": [
            {"title": j.get("title"), "company": j.get("company"), "score": j.get("fit_score")}
            for j in all_jobs[:3]
        ]
    }

    with open(SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"💾 Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
