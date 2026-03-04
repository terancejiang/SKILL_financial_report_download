# Financial Report Download (财报下载)

A Claude Code skill that searches and downloads A-share/HK stock financial report PDFs from `stockn.xueqiu.com` (雪球) with `notice.10jqka.com.cn` (同花顺) as fallback.

## Quick Start

Use the slash command:
```
/download-report 600887 2024 年报
```

Arguments: `<stock_code> [year] [report_type]`

## Two Usage Paths

1. **Slash command** (`/download-report`): `.claude/commands/download-report.md` → `scripts/download_report.py`
2. **Plugin**: `commands/download-report.md` → `skills/report-download/SKILL.md` → `skills/report-download/scripts/download_report.py`

## Project Structure

```
.
├── .claude/
│   └── commands/
│       └── download-report.md           # Slash command (standalone)
├── commands/
│   └── download-report.md              # Plugin entry point
├── skills/
│   └── report-download/
│       ├── SKILL.md                     # Plugin full workflow
│       └── scripts/
│           └── download_report.py       # Python download script (plugin)
├── scripts/
│   └── download_report.py              # Python download script (slash command)
├── requirements.txt
├── CLAUDE.md
└── README.md
```

## Notes

- Primary source: `stockn.xueqiu.com` (no anti-crawl); fallback: `notice.10jqka.com.cn` (同花顺)
- The Python script validates PDF magic bytes and retries with backoff on failure
- Supported markets: A-share (SH/SZ), Hong Kong
- Supported report types: 年报, 中报, 一季报, 三季报 (A-share); annual, interim (HK)
