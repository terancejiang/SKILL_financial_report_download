#!/usr/bin/env python3
"""
财报PDF下载工具 (Financial Report PDF Downloader)

从 stockn.xueqiu.com、notice.10jqka.com.cn 下载 A股/港股财报PDF；
新三板（NEEQ）股票可省略 --url，脚本自动搜索 neeq.com.cn 公告 API 后下载。
支持年报、中报、一季报、三季报（NEEQ 仅支持年报、中报）。

Usage:
    # A股/港股：提供 URL
    python3 scripts/download_report.py \
        --url "https://stockn.xueqiu.com/.../report.pdf" \
        --stock-code SH600887 \
        --report-type 年报 \
        --year 2024 \
        --save-dir .

    # 新三板（NEEQ）：无需 --url，自动搜索+下载
    python3 scripts/download_report.py \
        --stock-code 833442 \
        --report-type 年报 \
        --year 2018 \
        --save-dir .
"""

import argparse
import json
import os
import re
import sys
import time

import requests

# Exit codes
EXIT_SUCCESS = 0
EXIT_NETWORK_FAILURE = 1
EXIT_PDF_VALIDATION_FAILURE = 2
EXIT_BAD_ARGUMENTS = 3

# Constants
PDF_MAGIC_BYTES = b"%PDF-"
MIN_FILE_SIZE_WARNING = 100 * 1024  # 100KB
DOWNLOAD_TIMEOUT = 120
DEFAULT_MAX_RETRIES = 3
BACKOFF_BASE = 3  # seconds

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

URL_PATTERN = re.compile(
    r"^https?://(stockn\.xueqiu\.com|[\w.-]*10jqka\.com\.cn|(www\.)?neeq\.com\.cn|[\w.-]*szse\.cn)/.+\.pdf$",
    re.IGNORECASE,
)


def get_headers(url):
    """Return headers with Referer matching the URL domain.

    neeq.com.cn 需要 Referer/Origin 指向本站且 Accept 为 PDF，否则返回 403。
    """
    headers = dict(BASE_HEADERS)
    if "neeq.com.cn" in url:
        headers["Referer"] = "https://www.neeq.com.cn/"
        headers["Origin"] = "https://www.neeq.com.cn"
        headers["Accept"] = "application/pdf,*/*"
    elif "szse.cn" in url:
        headers["Referer"] = "https://www.szse.cn/"
    elif "10jqka.com.cn" in url:
        headers["Referer"] = "https://10jqka.com.cn/"
    else:
        headers["Referer"] = "https://xueqiu.com/"
    return headers


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Download financial report PDF from stockn.xueqiu.com or 10jqka.com.cn"
    )
    parser.add_argument(
        "--url",
        default=None,
        help="PDF URL from stockn.xueqiu.com, 10jqka.com.cn or neeq.com.cn "
        "(optional for NEEQ/新三板 stocks: auto-search neeq.com.cn)",
    )
    parser.add_argument(
        "--stock-code", required=True, help="Stock code (e.g. SH600887, 00700)"
    )
    parser.add_argument(
        "--stock-name",
        default="",
        help="Stock name (e.g. 伊利股份) to include in the filename; "
        "auto-detected for NEEQ/新三板 stocks",
    )
    parser.add_argument(
        "--report-type",
        required=True,
        help="Report type (年报/中报/一季报/三季报/annual/interim)",
    )
    parser.add_argument(
        "--year", required=True, help="Report year (e.g. 2024)"
    )
    parser.add_argument(
        "--save-dir", default=".", help="Directory to save the PDF (default: .)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Max download retries (default: {DEFAULT_MAX_RETRIES})",
    )
    return parser.parse_args(argv)


def validate_url(url):
    """Validate that the URL points to a supported source and ends with .pdf."""
    if not URL_PATTERN.match(url):
        return False, (
            f"Invalid URL: {url}\n"
            "URL must be a .pdf link from stockn.xueqiu.com, "
            "10jqka.com.cn or neeq.com.cn"
        )
    return True, ""


def build_filename(stock_code, stock_name, report_type, year):
    """Build output filename: {stock_code}_{stock_name}_{report_type}_{year}.pdf"""
    # Normalize report type for filename
    type_map = {
        "annual": "年报",
        "interim": "中报",
        "q1": "一季报",
        "q3": "三季报",
    }
    normalized = type_map.get(report_type.lower(), report_type)
    parts = [stock_code]
    if stock_name:
        parts.append(stock_name)
    parts.extend([normalized, str(year)])
    return "_".join(parts) + ".pdf"


def detect_market(stock_code):
    """Detect market and return (market, formatted_code).

    - SH/SZ prefix → as-is
    - 6-digit starting 6 → Shanghai A-share (SH prefix)
    - 6-digit starting 0/3 → Shenzhen A-share (SZ prefix)
    - 1-5 digits → Hong Kong (zero-padded to 5)
    - 6-digit starting 4/8/92 → NEEQ (新三板, no prefix)
    """
    code = stock_code.strip().upper()
    if code.startswith(("SH", "SZ")):
        return code[:2], code
    if code.startswith("NEEQ"):
        return "NEEQ", code[4:]
    if code.isdigit():
        if len(code) == 6 and code.startswith("6"):
            return "SH", "SH" + code
        if len(code) == 6 and code.startswith(("0", "3")):
            return "SZ", "SZ" + code
        if len(code) == 6 and code.startswith(("4", "8", "92")):
            return "NEEQ", code
        if len(code) <= 5:
            return "HK", code.zfill(5)
    return "UNKNOWN", stock_code


# ---- NEEQ (新三板) report search ----
NEEQ_HOME = "https://www.neeq.com.cn/"
NEEQ_API = "https://www.neeq.com.cn/disclosureInfoController/infoResult.do"
NEEQ_PDF_PREFIX = "https://www.neeq.com.cn"
NEEQ_TIMEOUT = 30
NEEQ_PAGE_SIZE = 30
# disclosureType=1 定期报告（含年报、半年报）
NEEQ_DISCLOSURE_TYPE = "1"
NEEQ_C3VK_RE = re.compile(r"C3VK=([a-f0-9]+)")
# NEEQ 只发布 年度报告 / 半年度报告
NEEQ_TYPE_KEYWORDS = {
    "年报": "年度报告",
    "annual": "年度报告",
    "中报": "半年度报告",
    "interim": "半年度报告",
}
NEEQ_EXCLUDE_KEYWORDS = ("摘要", "审计报告", "公告", "更正", "补充", "意见")


def get_neeq_cookie(session):
    """Bypass the NEEQ anti-bot JS challenge and return the C3VK cookie."""
    try:
        resp = session.get(NEEQ_HOME, timeout=NEEQ_TIMEOUT)
        m = NEEQ_C3VK_RE.search(resp.text)
        if m:
            return f"C3VK={m.group(1)}"
    except requests.exceptions.RequestException:
        pass
    return ""


def fetch_neeq_page(session, company_cd, page):
    """Fetch one page of a company's periodic reports from the NEEQ API."""
    resp = session.post(
        NEEQ_API,
        data={
            "companyCd": company_cd,
            "disclosureType": NEEQ_DISCLOSURE_TYPE,
            "keyword": "",
            "page": str(page),
            "pageSize": str(NEEQ_PAGE_SIZE),
        },
        timeout=NEEQ_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.text.strip()
    # JSONP wrapper: null([...])
    if text.startswith("null(") and text.endswith(")"):
        text = text[len("null("):-1]
    data = json.loads(text)
    for item in data:
        if isinstance(item, dict) and item.get("listInfo"):
            return item["listInfo"]
    return None


def search_neeq_report(stock_code, year, report_type):
    """Search NEEQ (neeq.com.cn) for a report PDF URL.

    Returns (url, error_message, company_name). url is None on failure.
    company_name is the matched company's name (e.g. 江苏铁科), may be "".
    """
    keyword = NEEQ_TYPE_KEYWORDS.get(report_type.lower())
    if not keyword:
        return None, (
            f"NEEQ (新三板) only supports 年报/中报 (annual/interim), "
            f"got report_type='{report_type}'"
        ), ""

    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    cookie = get_neeq_cookie(session)
    if cookie:
        session.headers["Cookie"] = cookie

    expected = f"{year}年{keyword}"
    checked = 0
    try:
        info = fetch_neeq_page(session, stock_code, page=0)
        if not info or not info.get("content"):
            return None, (
                f"No periodic reports returned for {stock_code} "
                "(check whether it is a valid NEEQ stock code)"
            ), ""
        total_pages = info.get("totalPages") or 1
        for page in range(total_pages):
            if page != 0:
                info = fetch_neeq_page(session, stock_code, page=page)
                if not info:
                    break
            for entry in info.get("content", []):
                checked += 1
                title = entry.get("disclosureTitle") or ""
                if expected in title and not any(
                    ex in title for ex in NEEQ_EXCLUDE_KEYWORDS
                ):
                    path = entry.get("destFilePath") or ""
                    if path:
                        return (
                            NEEQ_PDF_PREFIX + path,
                            "",
                            entry.get("companyName") or "",
                        )
    except (requests.exceptions.RequestException, ValueError) as e:
        return None, f"NEEQ search failed: {e}", ""

    return None, (
        f"No matching report found: {stock_code} {year} {report_type} "
        f"(searched {checked} periodic report entries)"
    ), ""


def download_annual_report(url, save_path, max_retries=DEFAULT_MAX_RETRIES):
    """
    Download PDF with retry and validation.

    Returns:
        tuple: (success: bool, message: str, filesize: int)
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            print(
                f"Downloading (attempt {attempt}/{max_retries}): {url}",
                file=sys.stderr,
            )

            response = requests.get(
                url,
                headers=get_headers(url),
                timeout=DOWNLOAD_TIMEOUT,
                stream=True,
            )
            response.raise_for_status()

            # Check Content-Type
            content_type = response.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
                print(
                    f"Warning: Content-Type is '{content_type}', expected PDF",
                    file=sys.stderr,
                )

            # Download to temporary path first, then rename
            tmp_path = save_path + ".tmp"
            total_size = 0
            first_chunk = True

            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        # Validate PDF magic bytes on first chunk
                        if first_chunk:
                            if not chunk[:5].startswith(PDF_MAGIC_BYTES):
                                os.remove(tmp_path)
                                return (
                                    False,
                                    "PDF validation failed: file does not start with %PDF- magic bytes",
                                    0,
                                )
                            first_chunk = False
                        f.write(chunk)
                        total_size += len(chunk)

            # Rename tmp to final
            if os.path.exists(save_path):
                os.remove(save_path)
            os.rename(tmp_path, save_path)

            # Size warning
            if total_size < MIN_FILE_SIZE_WARNING:
                print(
                    f"Warning: file size ({total_size} bytes) is smaller than expected (<100KB)",
                    file=sys.stderr,
                )

            return True, "Download successful", total_size

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            print(
                f"Attempt {attempt} failed: {last_error}", file=sys.stderr
            )
            # Clean up partial download
            tmp_path = save_path + ".tmp"
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

            if attempt < max_retries:
                wait_time = BACKOFF_BASE * attempt  # 3s, 6s, 9s
                print(f"Retrying in {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)

    return False, f"Download failed after {max_retries} attempts: {last_error}", 0


def print_result(success, filepath="", filesize=0, url="", stock_code="",
                 stock_name="", report_type="", year="", message=""):
    """Print structured result block for Claude to parse."""
    status = "SUCCESS" if success else "FAILED"
    print("\n---RESULT---")
    print(f"status: {status}")
    print(f"filepath: {filepath}")
    print(f"filesize: {filesize}")
    print(f"url: {url}")
    print(f"stock_code: {stock_code}")
    print(f"stock_name: {stock_name}")
    print(f"report_type: {report_type}")
    print(f"year: {year}")
    print(f"message: {message}")
    print("---END---")


def main(argv=None):
    args = parse_args(argv)

    market, formatted_code = detect_market(args.stock_code)
    stock_name = args.stock_name
    url = args.url

    # If no URL given, auto-search (NEEQ only)
    if not url:
        if market == "NEEQ":
            url, search_err, auto_name = search_neeq_report(
                formatted_code, args.year, args.report_type
            )
            if not stock_name:
                stock_name = auto_name
            if not url:
                print(f"Error: {search_err}", file=sys.stderr)
                print_result(
                    success=False,
                    url="",
                    stock_code=formatted_code,
                    stock_name=stock_name,
                    report_type=args.report_type,
                    year=args.year,
                    message=search_err,
                )
                sys.exit(EXIT_NETWORK_FAILURE)
            print(f"Found NEEQ report: {url}", file=sys.stderr)
        else:
            err_msg = (
                f"--url is required for {market} stocks. "
                "Only NEEQ (新三板) stocks support automatic report search."
            )
            print(f"Error: {err_msg}", file=sys.stderr)
            print_result(
                success=False,
                url="",
                stock_code=formatted_code,
                stock_name=stock_name,
                report_type=args.report_type,
                year=args.year,
                message=err_msg,
            )
            sys.exit(EXIT_BAD_ARGUMENTS)

    # Validate URL
    valid, err_msg = validate_url(url)
    if not valid:
        print(f"Error: {err_msg}", file=sys.stderr)
        print_result(
            success=False,
            url=url,
            stock_code=formatted_code,
            stock_name=stock_name,
            report_type=args.report_type,
            year=args.year,
            message=err_msg,
        )
        sys.exit(EXIT_BAD_ARGUMENTS)

    # Ensure save directory exists
    os.makedirs(args.save_dir, exist_ok=True)

    # Build filename and full path
    filename = build_filename(formatted_code, stock_name, args.report_type, args.year)
    save_path = os.path.join(args.save_dir, filename)

    # Download
    success, message, filesize = download_annual_report(
        url=url,
        save_path=save_path,
        max_retries=args.max_retries,
    )

    # Print result
    print_result(
        success=success,
        filepath=os.path.abspath(save_path) if success else "",
        filesize=filesize,
        url=url,
        stock_code=formatted_code,
        stock_name=stock_name,
        report_type=args.report_type,
        year=args.year,
        message=message,
    )

    if not success:
        if "validation" in message.lower():
            sys.exit(EXIT_PDF_VALIDATION_FAILURE)
        else:
            sys.exit(EXIT_NETWORK_FAILURE)

    sys.exit(EXIT_SUCCESS)


if __name__ == "__main__":
    main()
