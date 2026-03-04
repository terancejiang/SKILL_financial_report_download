# Snowball Report Download (雪球财报下载)

A Claude Code skill that searches and downloads A-share/HK stock financial report PDFs from `stockn.xueqiu.com`.

## Quick Start

Use the slash command:
```
/download-report 600887 2024 年报
```

Arguments: `<stock_code> [year] [report_type]`

## Project Structure

- `.claude/commands/download-report.md` — Slash command skill prompt
- `scripts/download_report.py` — Python PDF download helper (streaming, retry, validation)
- `requirements.txt` — Python dependencies (`requests`)

## Notes

- `stockn.xueqiu.com` serves PDFs without anti-crawl restrictions
- The Python script validates PDF magic bytes and retries with backoff on failure
- Supported markets: A-share (SH/SZ), Hong Kong
- Supported report types: 年报, 中报, 一季报, 三季报 (A-share); annual, interim (HK)
