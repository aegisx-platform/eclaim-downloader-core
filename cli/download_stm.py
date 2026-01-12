#!/usr/bin/env python3
"""
STM Download CLI Tool
Download statement files from NHSO E-Claim portal.

Note: Statement downloads are only available for UCS (Universal Coverage Scheme).

Usage:
    python -m cli.download_stm --fiscal-year 2569
    python -m cli.download_stm --month 1 --person-type IP
    python -m cli.download_stm --help

Person Types:
    IP  - ผู้ป่วยใน (Inpatient)
    OP  - ผู้ป่วยนอก (Outpatient)
    All - ทั้งหมด (All types, default)
"""

import argparse
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eclaim_core.downloaders import STMDownloader
from eclaim_core.config import SettingsManager
from eclaim_core.history import HistoryManager
from eclaim_core.logging import LogStreamer


def parse_args():
    """Parse command line arguments."""
    # Calculate current fiscal year
    now = datetime.now()
    current_fiscal_year = now.year + 543 if now.month >= 10 else now.year + 542

    parser = argparse.ArgumentParser(
        description="Download STM (Statement) files from NHSO E-Claim portal (UCS only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Note: Statement downloads are only available for UCS scheme.

Examples:
  # Download current fiscal year (all months, all types)
  python -m cli.download_stm

  # Download specific fiscal year
  python -m cli.download_stm --fiscal-year 2568

  # Download specific month
  python -m cli.download_stm --month 10

  # Download only IP (inpatient) statements
  python -m cli.download_stm --person-type IP

  # Download OP statements for October 2568
  python -m cli.download_stm --fiscal-year 2568 --month 10 --person-type OP

Fiscal Year:
  Thai fiscal year runs October to September.
  Example: Fiscal year 2569 = October 2025 to September 2026
        """
    )

    # Date options
    parser.add_argument(
        '--fiscal-year', '-y',
        type=int,
        default=current_fiscal_year,
        help=f"Fiscal year in Buddhist Era (default: {current_fiscal_year})"
    )
    parser.add_argument(
        '--month', '-m',
        type=int,
        choices=range(1, 13),
        metavar='N',
        help="Specific month (1-12), omit for entire fiscal year"
    )

    # Person type
    parser.add_argument(
        '--person-type', '-t',
        default='All',
        choices=['IP', 'OP', 'All'],
        help="Person type filter: IP (inpatient), OP (outpatient), All (default)"
    )

    # Credential options
    parser.add_argument(
        '--username', '-u',
        help="NHSO username (or set ECLAIM_USERNAME env var)"
    )
    parser.add_argument(
        '--password', '-p',
        help="NHSO password (or set ECLAIM_PASSWORD env var)"
    )

    # Output options
    parser.add_argument(
        '--download-dir', '-d',
        default='./downloads',
        help="Download directory (default: ./downloads)"
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help="Suppress output"
    )
    parser.add_argument(
        '--no-history',
        action='store_true',
        help="Don't track download history (re-download all files)"
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Initialize settings
    settings = SettingsManager()

    # Initialize history (optional) - use STM history file
    history = None
    if not args.no_history:
        history = HistoryManager(stm_history_file="stm_download_history.json")

    # Initialize logger (optional)
    logger = None if args.quiet else LogStreamer()

    # Get credentials
    username = args.username or settings.get('eclaim_username')
    password = args.password or settings.get('eclaim_password')

    if not username or not password:
        print("Error: Username and password required")
        print("")
        print("Set credentials via one of:")
        print("  1. Command line: --username USER --password PASS")
        print("  2. Environment: ECLAIM_USERNAME and ECLAIM_PASSWORD")
        print("  3. Config file: config/settings.json")
        sys.exit(1)

    # Create downloader
    downloader = STMDownloader(
        fiscal_year=args.fiscal_year,
        month=args.month,
        person_type=args.person_type,
        download_dir=args.download_dir,
        history_manager=history,
        logger=logger
    )

    # Print header
    if not args.quiet:
        print("=" * 60)
        print("E-Claim STM (Statement) File Downloader")
        print("=" * 60)
        print(f"Fiscal Year: {args.fiscal_year} BE")
        print(f"Month: {args.month if args.month else 'All months'}")
        print(f"Person Type: {args.person_type}")
        print(f"Scheme: UCS (Statement only available for UCS)")
        print(f"Download directory: {args.download_dir}")
        print("-" * 60)

    # Run download
    result = downloader.run(username, password)

    # Print results
    if not args.quiet:
        print("-" * 60)

    if not result.get('success'):
        print(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)

    if not args.quiet:
        print("Download Summary")
        print("-" * 60)
        print(f"Downloaded: {result['downloaded']}")
        print(f"Skipped:    {result['skipped']}")
        print(f"Errors:     {result['errors']}")
        print(f"Total:      {result['total']}")
        print("=" * 60)

    # Save history if tracking
    if history:
        history.save(download_type=downloader.download_type)

    # Exit with error code if there were failures
    if result['errors'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
