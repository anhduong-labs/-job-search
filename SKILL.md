---
name: job-scanner
description: "Tự động tìm kiếm việc làm web3/crypto từ nhiều nguồn, lọc theo profile của Duong, và update vào Google Sheet. Dùng khi: (1) được yêu cầu tìm việc, scan job, chạy job scanner, (2) cron job kích hoạt lúc 7h sáng, (3) nhận link job thủ công qua Telegram."
---
---
name: job-scanner
description: "Tự động tìm kiếm việc làm web3/crypto, lọc theo profile, update Google Sheet. Dùng khi được yêu cầu tìm việc, scan job, hoặc cron job kích hoạt."
---

# Job Scanner Skill

## Mô tả
Tự động tìm kiếm việc làm web3/crypto từ nhiều nguồn, lọc theo profile của Duong, và update vào Google Sheet mỗi ngày.

## Khi nào dùng skill này
- Khi được yêu cầu "tìm việc", "scan job", "chạy job scanner"
- Khi cron job kích hoạt lúc 7h sáng
- Khi nhận link job thủ công qua Telegram

---

## Files quan trọng

| File | Mục đích |
|------|----------|
| `~/.openclaw/workspace/scan_job_candidate_profile.json` | Profile tiêu chí lọc |
| `~/.openclaw/workspace/scan_job_source_registry.json` | Danh sách nguồn |
| `~/.openclaw/workspace/jobs_raw.json` | Output của crawl.py |
| `~/.openclaw/workspace/jobs_filtered.json` | Output của filter.py |
| `~/.openclaw/workspace/job_scan_last_run.json` | Summary lần chạy cuối |

---

## Workflow chính (Auto scan hàng ngày)

Chạy theo thứ tự sau, KHÔNG bỏ bước nào:

### Bước 1 — Crawl
```bash
cd ~/.openclaw/skills/job-scanner && ~/.openclaw/workspace/jobspy-env/bin/python3 scripts/crawl.py
```
- Crawl từ: web3career, cryptojobslist, LinkedIn (JobSpy)
- Output: `jobs_raw.json`
- Nếu lỗi: ghi log và tiếp tục bước 2 với data cũ nếu có

### Bước 2 — Filter & Score
```bash
cd ~/.openclaw/skills/job-scanner && python3 scripts/filter.py
```
- Đọc `jobs_raw.json` + `scan_job_candidate_profile.json`
- Score từng job từ 0-100
- Chia thành main_fit (>=60) và low_fit (>=40)
- Output: `jobs_filtered.json`

### Bước 3 — Update Sheet
```bash
cd ~/.openclaw/skills/job-scanner && python3 scripts/update_sheet.py
```
- Đọc `jobs_filtered.json`
- Gửi main_fit → tab `scan_job`
- Gửi low_fit → tab `scan_job_lowfit`
- Output: `job_scan_last_run.json`

### Bước 4 — Báo cáo Telegram
Sau khi update sheet xong, đọc `job_scan_last_run.json` và nhắn báo cáo theo format:
```
📊 Job Scan hoàn thành - [DATE]

✅ Main fit: [N] jobs → scan_job
📋 Low fit: [N] jobs → scan_job_lowfit
❌ Rejected: [N] jobs

Top 3 main fit:
1. [Title] @ [Company] — Score: [N]
2. [Title] @ [Company] — Score: [N]
3. [Title] @ [Company] — Score: [N]
```

---

## Workflow thủ công (Nhận link qua Telegram)

Khi Duong gửi link job qua Telegram:
```bash
cd ~/.openclaw/workspace && python3 job-processor.py [URL]
```

---

## Xử lý lỗi

| Lỗi | Cách xử lý |
|-----|-----------|
| Crawl thất bại 1 nguồn | Tiếp tục với các nguồn khác, ghi log |
| `jobs_raw.json` trống | Dừng, báo cáo lỗi qua Telegram |
| Apps Script timeout | Retry 1 lần, nếu vẫn lỗi báo cáo |
| JobSpy not installed | Bỏ qua LinkedIn, dùng 2 nguồn còn lại |

---

## Scoring logic

| Tiêu chí | Điểm tối đa |
|----------|-------------|
| Role match (preferred_roles) | 40đ |
| Domain match (web3/crypto) | 30đ |
| Location match (Remote/APAC) | 20đ |
| Seniority match | 10đ |
| Excluded role | -30đ |
| C-level (CEO/CTO/CFO) | -20đ |

Ngưỡng: main_fit >= 60, low_fit >= 40, rejected < 40
