#!/usr/bin/env python3
"""
雪球财报PDF下载工具 (Snowball Financial Report PDF Downloader)

从 stockn.xueqiu.com 下载A股/港股财报PDF文件。
支持年报、中报、一季报、三季报。

Usage:
    python3 scripts/download_report.py \
        --url "https://stockn.xueqiu.com/.../report.pdf" \
        --stock-code SH600887 \
        --report-type 年报 \
        --year 2024 \
        --save-dir .
"""

import argparse
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://xueqiu.com/",
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

URL_PATTERN = re.compile(
    r"^https://stockn\.xueqiu\.com/.+\.pdf$", re.IGNORECASE
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Download financial report PDF from stockn.xueqiu.com"
    )
    parser.add_argument(
        "--url", required=True, help="PDF URL from stockn.xueqiu.com"
    )
    parser.add_argument(
        "--stock-code", required=True, help="Stock code (e.g. SH600887, 00700)"
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
    """Validate that the URL points to stockn.xueqiu.com and ends with .pdf."""
    if not URL_PATTERN.match(url):
        return False, (
            f"Invalid URL: {url}\n"
            "URL must match https://stockn.xueqiu.com/.../*.pdf"
        )
    return True, ""


def build_filename(stock_code, report_type, year):
    """Build output filename: {stock_code}_{report_type}_{year}.pdf"""
    # Normalize report type for filename
    type_map = {
        "annual": "年报",
        "interim": "中报",
        "q1": "一季报",
        "q3": "三季报",
    }
    normalized = type_map.get(report_type.lower(), report_type)
    return f"{stock_code}_{normalized}_{year}.pdf"


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
                headers=HEADERS,
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
                 report_type="", year="", message=""):
    """Print structured result block for Claude to parse."""
    status = "SUCCESS" if success else "FAILED"
    print("\n---RESULT---")
    print(f"status: {status}")
    print(f"filepath: {filepath}")
    print(f"filesize: {filesize}")
    print(f"url: {url}")
    print(f"stock_code: {stock_code}")
    print(f"report_type: {report_type}")
    print(f"year: {year}")
    print(f"message: {message}")
    print("---END---")


def main(argv=None):
    args = parse_args(argv)

    # Validate URL
    valid, err_msg = validate_url(args.url)
    if not valid:
        print(f"Error: {err_msg}", file=sys.stderr)
        print_result(
            success=False,
            url=args.url,
            stock_code=args.stock_code,
            report_type=args.report_type,
            year=args.year,
            message=err_msg,
        )
        sys.exit(EXIT_BAD_ARGUMENTS)

    # Ensure save directory exists
    os.makedirs(args.save_dir, exist_ok=True)

    # Build filename and full path
    filename = build_filename(args.stock_code, args.report_type, args.year)
    save_path = os.path.join(args.save_dir, filename)

    # Download
    success, message, filesize = download_annual_report(
        url=args.url,
        save_path=save_path,
        max_retries=args.max_retries,
    )

    # Print result
    print_result(
        success=success,
        filepath=os.path.abspath(save_path) if success else "",
        filesize=filesize,
        url=args.url,
        stock_code=args.stock_code,
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
