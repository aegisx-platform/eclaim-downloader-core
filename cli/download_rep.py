#!/usr/bin/env python3
"""
REP Download CLI Tool
Download OP/IP/ORF files from NHSO E-Claim portal.

Usage:
    python -m cli.download_rep --month 1 --year 2569 --schemes ucs ofc
    python -m cli.download_rep --help

Insurance Schemes:
    ucs  - Universal Coverage Scheme (บัตรทอง)
    ofc  - Government Officer (ข้าราชการ)
    sss  - Social Security Scheme (ประกันสังคม)
    lgo  - Local Government Organization (อปท.)
    nhs  - NHSO Staff (สปสช.)
    bkk  - Bangkok Metropolitan Staff (กทม.)
    bmt  - BMTA Staff (ขสมก.)
    srt  - State Railway of Thailand Staff (รฟท.)
"""

import argparse
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eclaim_core.downloaders import REPDownloader
from eclaim_core.config import SettingsManager
from eclaim_core.history import HistoryManager
from eclaim_core.logging import LogStreamer
from eclaim_core.types import Scheme


VALID_SCHEMES = ['ucs', 'ofc', 'sss', 'lgo', 'nhs', 'bkk', 'bmt', 'srt']


def parse_args():
    """Parse command line arguments."""
    current_month = datetime.now().month
    current_year = datetime.now().year + 543  # Buddhist Era

    parser = argparse.ArgumentParser(
        description="Download REP (OP/IP/ORF) files from NHSO E-Claim portal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download current month (default scheme: UCS)
  python -m cli.download_rep

  # Download specific month and year (Buddhist Era)
  python -m cli.download_rep --month 12 --year 2568

  # Download from multiple insurance schemes
  python -m cli.download_rep --schemes ucs ofc sss

  # Download with explicit credentials
  python -m cli.download_rep --username USER --password PASS
        """
    )

    # Date options
    parser.add_argument(
        '--month', '-m',
        type=int,
        choices=range(1, 13),
        default=current_month,
        metavar='N',
        help=f"Month (1-12), default: {current_month}"
    )
    parser.add_argument(
        '--year', '-y',
        type=int,
        default=current_year,
        help=f"Year in Buddhist Era, default: {current_year}"
    )

    # Scheme options
    parser.add_argument(
        '--schemes', '-s',
        nargs='+',
        default=['ucs'],
        choices=VALID_SCHEMES,
        metavar='SCHEME',
        help="Insurance schemes to download (default: ucs)"
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

    # Initialize history (optional)
    history = None if args.no_history else HistoryManager()

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

    # Convert scheme strings to enums
    schemes = [Scheme(s) for s in args.schemes]

    # Create downloader
    downloader = REPDownloader(
        month=args.month,
        year=args.year,
        schemes=schemes,
        download_dir=args.download_dir,
        history_manager=history,
        logger=logger
    )

    # Print header
    if not args.quiet:
        print("=" * 60)
        print("E-Claim REP File Downloader")
        print("=" * 60)
        print(f"Month/Year: {args.month}/{args.year} BE")
        print(f"Schemes: {', '.join(s.upper() for s in args.schemes)}")
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
        history.save()

    # Exit with error code if there were failures
    if result['errors'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
