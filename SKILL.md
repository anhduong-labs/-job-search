---
name: job-scanner
description: "Tự động tìm kiếm việc làm web3/crypto từ nhiều nguồn, lọc theo profile của Duong, và update vào Google Sheet. Dùng khi: (1) được yêu cầu tìm việc, scan job, chạy job scanner, (2) cron job kích hoạt lúc 9h sáng (UTC+7), (3) nhận link job thủ công qua Telegram."
---

# Job Scanner Skill

## Mô tả
Tự động tìm kiếm việc làm web3/crypto từ nhiều nguồn, filter theo role + location, score và sort rồi update vào Google Sheet.

## Khi nào dùng skill này
- Khi được yêu cầu "tìm việc", "scan job", "chạy job scanner", "update job lên sheet"
- Khi cron job kích hoạt lúc 9h sáng (UTC+7)

---

## Scripts (chỉ 3 file đang dùng)

| Script | Mục đích |
|--------|----------|
| `scripts/crawl.py` | Crawl jobs từ LinkedIn + Indeed + Lever |
| `scripts/filter.py` | Filter theo role/location + scoring 0-100 |
| `scripts/update_sheet.py` | Push lên Google Sheet, sort theo score |
| `scripts/validate_output.py` | Debug utility (optional) |

## Output files

| File | Mục đích |
|------|----------|
| `~/.openclaw/workspace/jobs_raw.json` | Output của crawl.py |
| `~/.openclaw/workspace/jobs_filtered.json` | Output của filter.py (flat list, sorted) |
| `~/.openclaw/workspace/job_scan_last_run.json` | Summary lần chạy cuối |

---

## Workflow chính

Chạy theo thứ tự sau, KHÔNG bỏ bước nào:

### Bước 1 — Crawl
```bash
cd ~/.openclaw/skills/job-scanner && ~/.openclaw/workspace/jobspy-env/bin/python3 scripts/crawl.py
```
- Keywords: `web3`, `crypto`, `blockchain`
- Locations: Remote, Ho Chi Minh City, Hanoi, Singapore, Bangkok, Hong Kong
- Nguồn: LinkedIn + Indeed (JobSpy) + Lever (Binance, Immutable)
- Output: `jobs_raw.json` (~250-320 jobs)

### Bước 2 — Filter & Score
```bash
cd ~/.openclaw/skills/job-scanner && ~/.openclaw/workspace/jobspy-env/bin/python3 scripts/filter.py
```
- ✅ Giữ: role Product/Growth/Research/Analyst/BD/Marketing
- ✅ Giữ: location Remote (không gắn US/EU) hoặc APAC
- ❌ Loại: Engineering/HR/Legal/C-level
- ❌ Loại: "Remote, US" / "Remote, UK" / Non-APAC
- Score 0-100, sort cao → thấp
- Output: `jobs_filtered.json` (~60-90 jobs)

### Bước 3 — Update Sheet
```bash
cd ~/.openclaw/skills/job-scanner && JOB_SHEET_ID=1NHXD3e4TZYhEcdaEhx1tJZYVlUfhQMpBze_vy5SesJ8 ~/.openclaw/workspace/jobspy-env/bin/python3 scripts/update_sheet.py
```
- Push vào 1 tab duy nhất: `scan_job`
- Skip duplicate theo URL
- Thứ tự trên sheet = score cao nhất lên đầu
- Output: `job_scan_last_run.json`

### Bước 4 — Báo cáo Telegram
Sau khi xong, đọc `job_scan_last_run.json` và báo cáo:
```
📊 Job Scan hoàn thành - [DATE]

✅ [N] jobs mới đã push lên sheet
↩️ [N] duplicates skip
❌ [N] lỗi

🏆 Top 3:
1. [Title] @ [Company]
2. [Title] @ [Company]
3. [Title] @ [Company]
```

---

## Xử lý lỗi

| Lỗi | Cách xử lý |
|-----|-----------|
| Crawl thất bại 1 nguồn | Tiếp tục với nguồn khác, ghi log |
| `jobs_raw.json` trống | Dừng, báo lỗi qua Telegram |
| Lever timeout | Bỏ qua, LinkedIn/Indeed vẫn chạy |
| `JOB_SHEET_ID` trống | Đọc từ `~/.openclaw/workspace/.env` |

---

## Scoring logic

| Tiêu chí | Điểm tối đa |
|----------|-------------|
| Role match (research/analyst/product/growth) | 30đ |
| Location match (Remote/APAC city) | 30đ |
| Web3/crypto relevance trong description | 20đ |
| Seniority (senior/lead/head) | +10đ |
| Junior/intern | -10đ |

Tất cả jobs pass filter đều lên sheet, sort theo score.
