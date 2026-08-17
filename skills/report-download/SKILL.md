---
name: report-download
description: >
  **Financial Report Downloader**: Auto-search and download A-share/HK/NEEQ stock financial report PDFs from Xueqiu (stockn.xueqiu.com), 同花顺 (notice.10jqka.com.cn), or 股转系统 (neeq.com.cn).
  - MANDATORY TRIGGERS: download report, 下载财报, 下载年报, 下载中报, annual report download, financial report PDF, 雪球财报, 同花顺财报

version: 0.2.0
---

# Financial Report PDF Downloader

Download A-share, Hong Kong, and NEEQ (新三板) stock financial report PDFs from `stockn.xueqiu.com` (雪球) with `notice.10jqka.com.cn` (同花顺) as fallback, plus `neeq.com.cn` (股转系统) for NEEQ stocks.

## Workflow

```
Input (stock code or company name, year, report type)
  → Step 0: Parse & detect market (resolve name → code via WebSearch if needed)
  → Step 1: NEEQ → script auto-searches neeq.com.cn API (no WebSearch)
            A-share/HK → WebSearch for PDF on stockn.xueqiu.com
  → Step 2: Extract matching PDF URLs
  → Step 3: Identify correct report (filter out summaries, audit reports, etc.)
  → Step 4: Python script downloads PDF to local disk
  → Output: local PDF file path
```

## Step 0: Parse Input

Parse user input into three parts:
- **stock_code** (required): stock ticker **or company name** — if a name is given, resolve it to a code first via WebSearch (e.g. `江苏铁科` → `833442`)
- **year** (optional): defaults to latest available
- **report_type** (optional): defaults to 年报

### Market Detection

| Pattern | Market | Formatting | Example |
|---------|--------|-----------|---------|
| 6-digit starting with `6` | Shanghai A-share | Prefix `SH` | `600887` → `SH600887` |
| 6-digit starting with `0` or `3` | Shenzhen A-share | Prefix `SZ` | `300750` → `SZ300750` |
| 1-5 digits | Hong Kong | Zero-pad to 5 digits | `700` → `00700` |
| 6-digit starting with `4`/`8`/`92` | NEEQ (新三板) | Use as-is (no prefix) | `833442` |
| Already has `SH`/`SZ` prefix | Use as-is | — | `SH600887` |

### Report Type Mapping

| User Input | report_type | A-share Search Keyword | HK Search Keyword | Publish Time |
|-----------|-------------|----------------------|-------------------|-------------|
| 年报 / annual | 年报 | 年度报告 | annual report | Next year Mar-Apr |
| 中报 / interim | 中报 | 半年度报告 | interim report | Same year Aug-Sep |
| 一季报 / Q1 | 一季报 | 第一季度报告 | *(A-share only)* | Same year Apr |
| 三季报 / Q3 | 三季报 | 第三季度报告 | *(A-share only)* | Same year Oct |

**Note:** NEEQ (新三板) stocks only support 年报 and 中报 (年度报告/半年度报告).

## Step 1: Search for the Report

### NEEQ (新三板) stocks — no WebSearch needed

For NEEQ codes, **skip WebSearch** and let the script auto-search the neeq.com.cn disclosure API (it handles the anti-bot cookie challenge and finds the exact PDF). Run Step 4 **without** `--url`. If it fails, fall back to WebSearch as a last resort.

### A-share / HK stocks — use WebSearch

Use **WebSearch** with this query pattern:

**A-share:** `site:stockn.xueqiu.com {formatted_code} {search_keyword} {year}`
**HK:** `site:stockn.xueqiu.com {formatted_code} {hk_search_keyword} {year}`

If no year specified: try current year first, then previous year.
If no results from Xueqiu:
1. Retry with **同花顺**: `site:notice.10jqka.com.cn {formatted_code} {search_keyword} {year}`
   - Can also try with company name, e.g.: `site:notice.10jqka.com.cn 伊利股份 2024 年度报告`
2. If still no results: retry without any `site:` prefix as a last resort.

## Step 2: Extract PDF Links

Filter search results for PDF URLs from supported sources:
- `https://stockn.xueqiu.com/.../*.pdf`
- `https://notice.10jqka.com.cn/.../*.pdf`

## Step 3: Identify Correct Report

**Exclude** results with titles containing:
摘要, 审计报告, 公告, 利润分配, 可持续发展, 股东大会, ESG, summary, auditor, dividend, 更正, 补充, 意见, 内部控制

**Prefer** results where:
1. Title contains the report keyword (e.g. "年度报告") WITHOUT "摘要"
2. URL date closest to expected publish date
3. If tied, pick first result

If no candidates remain: inform user and suggest verifying stock code/year/report type.

## Step 4: Download the PDF

Install dependency if needed:
```bash
pip install requests --break-system-packages
```

Run the download script (located at `${CLAUDE_PLUGIN_ROOT}/skills/report-download/scripts/download_report.py`). **For NEEQ stocks, `--url` is optional** — the script auto-searches neeq.com.cn:

```bash
# A股/港股：提供 URL
python3 ${CLAUDE_PLUGIN_ROOT}/skills/report-download/scripts/download_report.py \
  --url "<PDF_URL>" \
  --stock-code "<formatted_stock_code>" \
  --stock-name "<股票名称>" \
  --report-type "<report_type>" \
  --year "<year>" \
  --save-dir "."

# 新三板：无需 --url，自动搜索+下载（股票名称自动识别）
python3 ${CLAUDE_PLUGIN_ROOT}/skills/report-download/scripts/download_report.py \
  --stock-code "<formatted_stock_code>" \
  --report-type "<report_type>" \
  --year "<year>" \
  --save-dir "."
```

**文件名命名：** `{股票代码}_{股票名称}_{报告类型}_{年份}.pdf`（如 `833442_江苏铁科_年报_2018.pdf`）。A股/港股请在命令中传 `--stock-name`；新三板自动识别，无需手动指定。

### Parse Output

The script prints a structured block between `---RESULT---` and `---END---`:
- `status`: SUCCESS or FAILED
- `filepath`: absolute path to downloaded file
- `filesize`: file size in bytes
- `message`: status message

### Report to User

**On success:** Report file path, size (human-readable MB), stock code, year, report type.
**On failure:** Report error message. Suggest checking URL accessibility, retrying, or verifying inputs.
