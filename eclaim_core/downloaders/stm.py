"""
STM (Statement) Downloader
Downloads payment statement files from NHSO E-Claim portal.

Note: Statement downloads are only available for UCS (Universal Coverage Scheme).
"""

import os
import re
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseDownloader
from ..types import (
    DownloadType, FileType, Scheme,
    DownloadResult, DownloadLink
)


class STMDownloader(BaseDownloader):
    """
    Downloads STM (Statement) files from NHSO E-Claim portal.

    Statement downloads are only available for UCS scheme.
    Supports filtering by fiscal year, month, and person type (IP/OP).
    """

    BASE_URL = "https://eclaim.nhso.go.th"
    LOGIN_URL = f"{BASE_URL}/webComponent/login/LoginAction.do"

    # Statement URLs - UCS only
    LIST_URL = f"{BASE_URL}/webComponent/ucs/statementUCSAction.do"
    VIEW_URL = f"{BASE_URL}/webComponent/ucs/statementUCSViewAction.do"
    DOWNLOAD_URL = f"{BASE_URL}/webComponent/ucs/statementUCSDownloadAction.do"

    # Person type codes
    PERSON_TYPES = {
        'IP': '2',   # ผู้ป่วยใน
        'OP': '1',   # ผู้ป่วยนอก
        'All': ''    # ทั้งหมด
    }

    def __init__(
        self,
        fiscal_year: Optional[int] = None,  # Buddhist Era
        month: Optional[int] = None,        # None = all months
        person_type: str = "All",           # IP, OP, or All
        **kwargs
    ):
        """
        Initialize STM Downloader.

        Args:
            fiscal_year: Fiscal year in Buddhist Era. Defaults to current fiscal year.
            month: Month (1-12). None means all months in fiscal year.
            person_type: Patient type filter - 'IP', 'OP', or 'All'. Defaults to 'All'.
            **kwargs: Additional arguments passed to BaseDownloader.
        """
        super().__init__(**kwargs)
        self.fiscal_year = fiscal_year or self._current_fiscal_year()
        self.month = month
        self.person_type = person_type if person_type in self.PERSON_TYPES else 'All'

    @property
    def download_type(self) -> DownloadType:
        return DownloadType.STM

    @staticmethod
    def _current_fiscal_year() -> int:
        """
        Get current fiscal year in Buddhist Era.
        Fiscal year runs October to September.
        """
        now = datetime.now()
        year_be = now.year + 543
        # If before October, we're in the fiscal year that started last October
        if now.month < 10:
            return year_be
        # October onwards is next fiscal year
        return year_be + 1

    def login(self, username: str, password: str) -> bool:
        """
        Authenticate with NHSO E-Claim portal.

        Args:
            username: NHSO username
            password: NHSO password

        Returns:
            True if login successful, False otherwise
        """
        self.session = self._create_session()

        try:
            self._log("Logging in to NHSO E-Claim...")
            self.session.get(self.LOGIN_URL, timeout=30)

            response = self.session.post(
                self.LOGIN_URL,
                data={'user': username, 'pass': password},
                timeout=30,
                allow_redirects=True
            )

            if 'login' in response.url.lower() and 'error' in response.text.lower():
                self._log("Login failed - invalid credentials", level='error')
                return False

            self._log("Login successful", level='success')
            return True

        except requests.RequestException as e:
            self._log(f"Login error: {e}", level='error')
            return False

    def get_download_links(self, **kwargs) -> List[DownloadLink]:
        """
        Get download links for configured fiscal year/month/person_type.

        Returns:
            List of DownloadLink objects
        """
        self._log(f"Fetching STM statement list for fiscal year {self.fiscal_year}...")
        if self.month:
            self._log(f"Month: {self.month}")
        self._log(f"Person type: {self.person_type}")

        try:
            # First access the main page to establish session
            self.session.get(self.LIST_URL, timeout=30)

            # Convert Buddhist year to Gregorian for API
            gregorian_year = self.fiscal_year - 543

            # Build AJAX request parameters
            params = {
                'PAGE_HEAD': '',
                'year': str(gregorian_year),
                'month': str(self.month) if self.month else '',
                'person_type': self.PERSON_TYPES.get(self.person_type, ''),
                'period_no': ''
            }

            # Set AJAX headers
            self.session.headers.update({
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'text/html, */*; q=0.01'
            })

            response = self.session.get(self.VIEW_URL, params=params, timeout=30)
            response.raise_for_status()

            links = self._parse_statement_list(response.text)
            self._log(f"Found {len(links)} STM files")
            return links

        except requests.RequestException as e:
            self._log(f"Error fetching STM links: {e}", level='error')
            return []

    def _parse_statement_list(self, html: str) -> List[DownloadLink]:
        """Parse AJAX response to extract statement download info."""
        soup = BeautifulSoup(html, 'lxml')
        links = []

        # Find table with id="table-detail" or fallback to first table
        table = soup.find('table', id='table-detail')
        if not table:
            table = soup.find('table')

        if not table:
            return links

        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')

        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 9:
                continue

            try:
                # Extract statement info
                stmt_no = cells[6].get_text(strip=True)  # e.g., 10670_IPUCS256710_01
                stmt_type = cells[3].get_text(strip=True)  # ผู้ป่วยใน / ผู้ป่วยนอก
                service_month = cells[2].get_text(strip=True)

                # Find download link and extract parameters from onclick
                download_cell = cells[8] if len(cells) > 8 else None
                if not download_cell:
                    continue

                link = download_cell.find('a')
                if not link:
                    continue

                onclick = link.get('onclick', '')
                # Parse: downloadBill('10670_IPUCS256710_01', '2', '10670', ...)
                match = re.search(
                    r"downloadBill\('([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'\)",
                    onclick
                )

                if not match:
                    continue

                download_params = {
                    'document_no': match.group(1),
                    'person_type': match.group(2),
                    'hcode': match.group(3),
                    'hname': match.group(4),
                    'province_name': match.group(5),
                    'datesend_from': match.group(6),
                    'datesend_to': match.group(7)
                }

                filename = f"STM_{download_params['document_no']}.xls"

                # Detect file type from statement type text
                file_type = None
                if 'ผู้ป่วยใน' in stmt_type or 'IP' in stmt_type.upper():
                    file_type = FileType.STM_IP
                elif 'ผู้ป่วยนอก' in stmt_type or 'OP' in stmt_type.upper():
                    file_type = FileType.STM_OP

                links.append(DownloadLink(
                    url=self.DOWNLOAD_URL,  # Will use POST
                    filename=filename,
                    file_type=file_type,
                    scheme=Scheme.UCS,
                    metadata={
                        'download_params': download_params,
                        'stmt_no': stmt_no,
                        'service_month': service_month,
                        'stmt_type': stmt_type
                    }
                ))

            except Exception as e:
                self._log(f"Warning: Error parsing row: {e}", level='warning')
                continue

        return links

    def download_file(self, link: DownloadLink) -> DownloadResult:
        """
        Download a single STM file via POST form submission.

        Args:
            link: DownloadLink object with download parameters in metadata

        Returns:
            DownloadResult with success status and details
        """
        file_path = os.path.join(self.download_dir, link.filename)

        # Check if already downloaded
        if self.history and self.history.exists(link.filename, self.download_type):
            self._log(f"Skipping {link.filename} (already downloaded)")
            return DownloadResult(
                success=False,
                filename=link.filename,
                file_path=file_path,
                file_size=0,
                download_type=self.download_type,
                file_type=link.file_type,
                scheme=link.scheme,
                year=self.fiscal_year,
                month=self.month,
                error="skipped"
            )

        # Get download parameters from metadata
        download_params = link.metadata.get('download_params', {})
        if not download_params:
            return DownloadResult(
                success=False,
                filename=link.filename,
                file_path=file_path,
                file_size=0,
                download_type=self.download_type,
                error="No download parameters"
            )

        # Download with retry
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    self._log(f"Retry {attempt}/{max_retries} for {link.filename}...", level='warning')
                    time.sleep(2)

                # POST form data to download
                form_data = {
                    'document_no': download_params['document_no'],
                    'person_type': download_params['person_type'],
                    'hcode': download_params['hcode'],
                    'hname': download_params['hname'],
                    'province_name': download_params['province_name'],
                    'datesend_from': download_params.get('datesend_from', ''),
                    'datesend_to': download_params.get('datesend_to', '')
                }

                response = self.session.post(
                    self.DOWNLOAD_URL,
                    data=form_data,
                    timeout=300
                )
                response.raise_for_status()

                # Check if response is actually a file
                content_type = response.headers.get('Content-Type', '')
                if 'html' in content_type.lower() and len(response.content) < 1000:
                    raise ValueError("Received HTML instead of file, might be error page")

                # Save file
                with open(file_path, 'wb') as f:
                    f.write(response.content)

                file_size = len(response.content)

                if file_size < 100:
                    raise ValueError(f"File too small ({file_size} bytes)")

                return DownloadResult(
                    success=True,
                    filename=link.filename,
                    file_path=file_path,
                    file_size=file_size,
                    download_type=self.download_type,
                    file_type=link.file_type,
                    scheme=link.scheme,
                    year=self.fiscal_year,
                    month=self.month,
                    url=link.url,
                    metadata=link.metadata
                )

            except Exception as e:
                if attempt >= max_retries:
                    self._log(f"Failed after {max_retries} retries: {link.filename}", level='error')
                    return DownloadResult(
                        success=False,
                        filename=link.filename,
                        file_path=file_path,
                        file_size=0,
                        download_type=self.download_type,
                        file_type=link.file_type,
                        scheme=link.scheme,
                        year=self.fiscal_year,
                        error=str(e)
                    )

        return DownloadResult(
            success=False,
            filename=link.filename,
            file_path=file_path,
            file_size=0,
            download_type=self.download_type,
            error="Unknown error"
        )

    def run(self, username: str, password: str) -> Dict[str, Any]:
        """
        Execute full STM download workflow.

        Args:
            username: NHSO username
            password: NHSO password

        Returns:
            Dict with success status and download counts
        """
        self._log(f"Starting STM download for fiscal year {self.fiscal_year}")
        if self.month:
            self._log(f"Month: {self.month}")
        self._log(f"Person type: {self.person_type}")
        self._log("Scheme: UCS (Statement only available for UCS)")

        if not self.login(username, password):
            return {'success': False, 'error': 'Login failed'}

        links = self.get_download_links()
        if not links:
            self._log("No STM files found", level='warning')
            return {'success': True, 'downloaded': 0, 'skipped': 0, 'errors': 0, 'total': 0}

        self._log(f"Found {len(links)} total files to process")
        results = self.download_all(links)

        downloaded = sum(1 for r in results if r.success)
        skipped = sum(1 for r in results if r.error == 'skipped')
        errors = sum(1 for r in results if r.error and r.error != 'skipped')

        self._log(f"Download complete: {downloaded} downloaded, {skipped} skipped, {errors} errors", level='success')

        return {
            'success': True,
            'downloaded': downloaded,
            'skipped': skipped,
            'errors': errors,
            'total': len(results)
        }
