"""
REP (Representative) Downloader
Downloads OP/IP/ORF files from NHSO E-Claim portal.
"""

import os
import re
import time
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from .base import BaseDownloader
from ..types import (
    DownloadType, FileType, Scheme,
    DownloadResult, DownloadLink
)


class REPDownloader(BaseDownloader):
    """
    Downloads REP (Representative) files from NHSO E-Claim portal.
    Supports OP, IP, and ORF file types across multiple insurance schemes.
    """

    BASE_URL = "https://eclaim.nhso.go.th"
    LOGIN_URL = f"{BASE_URL}/webComponent/login/LoginAction.do"

    # Scheme URL mappings for validation pages
    SCHEME_URLS = {
        Scheme.UCS: "/webComponent/validation/ValidationMainAction.do",
        Scheme.OFC: "/webComponent/validation/ValidationMainAction.do",
        Scheme.SSS: "/webComponent/validation/ValidationMainAction.do",
        Scheme.LGO: "/webComponent/validation/ValidationMainAction.do",
        Scheme.NHS: "/webComponent/validation/ValidationMainAction.do",
        Scheme.BKK: "/webComponent/validation/ValidationMainAction.do",
        Scheme.BMT: "/webComponent/validation/ValidationMainAction.do",
        Scheme.SRT: "/webComponent/validation/ValidationMainAction.do",
    }

    def __init__(
        self,
        month: Optional[int] = None,
        year: Optional[int] = None,  # Buddhist Era
        schemes: Optional[List[Scheme]] = None,
        **kwargs
    ):
        """
        Initialize REP Downloader.

        Args:
            month: Month (1-12). Defaults to current month.
            year: Year in Buddhist Era. Defaults to current year + 543.
            schemes: List of insurance schemes. Defaults to [Scheme.UCS].
            **kwargs: Additional arguments passed to BaseDownloader.
        """
        super().__init__(**kwargs)
        self.month = month or self._current_be_month()
        self.year = year or self._current_be_year()
        self.schemes = schemes or [Scheme.UCS]

    @property
    def download_type(self) -> DownloadType:
        return DownloadType.REP

    @staticmethod
    def _current_be_month() -> int:
        """Get current month."""
        return datetime.now().month

    @staticmethod
    def _current_be_year() -> int:
        """Get current year in Buddhist Era."""
        return datetime.now().year + 543

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
            # Get login page for cookies
            self._log("Logging in to NHSO E-Claim...")
            self.session.get(self.LOGIN_URL, timeout=30)

            # Submit login
            response = self.session.post(
                self.LOGIN_URL,
                data={'user': username, 'pass': password},
                timeout=30,
                allow_redirects=True
            )

            # Check if login successful
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
        Get download links for configured month/year/schemes.

        Returns:
            List of DownloadLink objects
        """
        links = []

        for scheme in self.schemes:
            scheme_links = self._get_scheme_links(scheme)
            links.extend(scheme_links)
            self._log(f"Found {len(scheme_links)} files for {scheme.value.upper()}")

        return links

    def _get_scheme_links(self, scheme: Scheme) -> List[DownloadLink]:
        """Get download links for a specific scheme."""
        if scheme not in self.SCHEME_URLS:
            self._log(f"Unsupported scheme: {scheme.value}", level='warning')
            return []

        # Build validation URL with parameters
        url = f"{self.BASE_URL}{self.SCHEME_URLS[scheme]}"
        params = {
            'mo': str(self.month),
            'ye': str(self.year),
            'maininscl': scheme.value
        }

        try:
            self._log(f"Fetching validation page for {scheme.value.upper()}...")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return self._parse_download_links(response.text, scheme)
        except requests.RequestException as e:
            self._log(f"Error fetching links for {scheme.value}: {e}", level='error')
            return []

    def _parse_download_links(self, html: str, scheme: Scheme) -> List[DownloadLink]:
        """Parse HTML to extract download links."""
        soup = BeautifulSoup(html, 'lxml')
        links = []
        seen_filenames = set()

        # Find all tables and look for download links
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')

            for row in rows:
                # Look for download excel link
                excel_links = row.find_all('a', string=re.compile(r'download excel', re.IGNORECASE))

                for excel_link in excel_links:
                    href = excel_link.get('href')
                    if not href:
                        continue

                    filename = self._extract_filename(href, excel_link.text, row)
                    if not filename or filename in seen_filenames:
                        continue

                    seen_filenames.add(filename)
                    full_url = urljoin(self.BASE_URL, href)
                    file_type = self._detect_file_type(filename)

                    links.append(DownloadLink(
                        url=full_url,
                        filename=filename,
                        file_type=file_type,
                        scheme=scheme
                    ))

        return links

    def _extract_filename(self, href: str, link_text: str, row=None) -> Optional[str]:
        """Extract filename from URL or link text."""
        # Parse URL parameters
        parsed = urlparse(href)
        params = parse_qs(parsed.query)

        # Try various parameter names
        if 'fn' in params:
            return params['fn'][0]
        if 'filename' in params:
            # Replace .ecd with .xls
            return params['filename'][0].replace('.ecd', '.xls')
        if 'file' in params:
            return params['file'][0]

        # Try to find rep link in the same row
        if row:
            rep_links = row.find_all('a', string=re.compile(r'rep_eclaim', re.IGNORECASE))
            if rep_links:
                rep_href = rep_links[0].get('href')
                if rep_href:
                    return rep_href.split('/')[-1].replace('.ecd', '.xls')

        # Try link text
        text = link_text.strip()
        if text and '.xls' in text.lower():
            return text

        return None

    def _detect_file_type(self, filename: str) -> Optional[FileType]:
        """Detect file type from filename."""
        filename_upper = filename.upper()

        if '_OP_' in filename_upper:
            return FileType.OP
        elif '_IP_' in filename_upper:
            if 'APPEAL' in filename_upper:
                if 'NHSO' in filename_upper:
                    return FileType.IP_APPEAL_NHSO
                return FileType.IP_APPEAL
            return FileType.IP
        elif '_ORF_' in filename_upper:
            return FileType.ORF

        return None

    def download_file(self, link: DownloadLink) -> DownloadResult:
        """
        Download a single file.

        Args:
            link: DownloadLink object with URL and filename

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
                month=self.month,
                year=self.year,
                error="skipped"
            )

        # Download with retry
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    self._log(f"Retry {attempt}/{max_retries} for {link.filename}...", level='warning')
                    time.sleep(2)

                response = self.session.get(link.url, stream=True, timeout=120)
                response.raise_for_status()

                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                file_size = os.path.getsize(file_path)

                # Check if file is valid
                if file_size < 100:
                    raise ValueError(f"File too small ({file_size} bytes), likely error page")

                return DownloadResult(
                    success=True,
                    filename=link.filename,
                    file_path=file_path,
                    file_size=file_size,
                    download_type=self.download_type,
                    file_type=link.file_type,
                    scheme=link.scheme,
                    month=self.month,
                    year=self.year,
                    url=link.url
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
                        month=self.month,
                        year=self.year,
                        error=str(e)
                    )

        # Should not reach here, but just in case
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
        Execute full download workflow.

        Args:
            username: NHSO username
            password: NHSO password

        Returns:
            Dict with success status and download counts
        """
        self._log(f"Starting REP download for {self.month}/{self.year}")
        self._log(f"Schemes: {', '.join(s.value.upper() for s in self.schemes)}")

        if not self.login(username, password):
            return {'success': False, 'error': 'Login failed'}

        links = self.get_download_links()
        if not links:
            self._log("No download links found", level='warning')
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
