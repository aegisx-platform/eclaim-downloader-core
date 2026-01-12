"""
Base Downloader Abstract Class
All downloaders inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import requests
import os

from ..types import DownloadType, DownloadResult, DownloadProgress, DownloadLink


class BaseDownloader(ABC):
    """
    Abstract base class for all downloaders.
    Provides common functionality for authentication, session management,
    and progress tracking.
    """

    def __init__(
        self,
        download_dir: str = "./downloads",
        history_manager: Optional[Any] = None,
        logger: Optional[Any] = None
    ):
        self.download_dir = download_dir
        self.history = history_manager
        self.logger = logger
        self.session: Optional[requests.Session] = None
        self._progress = DownloadProgress()

        # Ensure download directory exists
        os.makedirs(self.download_dir, exist_ok=True)

    @property
    @abstractmethod
    def download_type(self) -> DownloadType:
        """Return the type of downloader"""
        pass

    @abstractmethod
    def login(self, username: str, password: str) -> bool:
        """
        Authenticate with the remote system.

        Args:
            username: Login username
            password: Login password

        Returns:
            True if login successful, False otherwise
        """
        pass

    @abstractmethod
    def get_download_links(self, **kwargs) -> List[DownloadLink]:
        """
        Get list of available downloads.

        Returns:
            List of DownloadLink objects
        """
        pass

    @abstractmethod
    def download_file(self, link: DownloadLink) -> DownloadResult:
        """
        Download a single file.

        Args:
            link: DownloadLink object with URL and filename

        Returns:
            DownloadResult with success status and details
        """
        pass

    def download_all(self, links: List[DownloadLink]) -> List[DownloadResult]:
        """
        Download all files from links.

        Args:
            links: List of DownloadLink objects

        Returns:
            List of DownloadResult objects
        """
        from datetime import datetime

        results = []
        self._progress = DownloadProgress(
            total=len(links),
            is_running=True,
            started_at=datetime.now()
        )

        for link in links:
            self._progress.current_file = link.filename
            result = self.download_file(link)
            results.append(result)

            if result.success:
                self._progress.downloaded += 1
                if self.history:
                    self.history.add_record(result)
            elif result.error == "skipped":
                self._progress.skipped += 1
            else:
                self._progress.errors += 1

            self._log(
                f"{'Downloaded' if result.success else 'Failed'}: {link.filename}",
                level='success' if result.success else 'error'
            )

        self._progress.is_running = False
        self._progress.current_file = None
        return results

    @property
    def progress(self) -> DownloadProgress:
        """Get current download progress"""
        return self._progress

    def _log(self, message: str, level: str = 'info') -> None:
        """Log a message using the configured logger"""
        if self.logger:
            self.logger.write(message, level=level, source=self.download_type.value)

    def _create_session(self) -> requests.Session:
        """Create a new requests session with default headers"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
            'Accept-Language': 'th-TH,th;q=0.9,en;q=0.8'
        })
        return session
