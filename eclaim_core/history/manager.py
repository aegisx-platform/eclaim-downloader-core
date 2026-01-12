"""
Download History Manager
Manages download history using JSON files with atomic writes.
"""

import json
import os
import shutil
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from ..types import DownloadResult, DownloadType, Scheme


class HistoryManager:
    """
    Manages download history using JSON files.
    Thread-safe with atomic writes and backup.
    """

    def __init__(
        self,
        rep_history_file: str = "download_history.json",
        stm_history_file: str = "stm_download_history.json"
    ):
        self.rep_history_file = Path(rep_history_file)
        self.stm_history_file = Path(stm_history_file)
        self._lock = threading.Lock()
        self._rep_history: Optional[Dict] = None
        self._stm_history: Optional[Dict] = None

    def _get_history_file(self, download_type: DownloadType) -> Path:
        """Get appropriate history file for download type."""
        if download_type == DownloadType.STM:
            return self.stm_history_file
        return self.rep_history_file

    def load(self, download_type: DownloadType = DownloadType.REP) -> Dict:
        """Load download history from JSON file."""
        history_file = self._get_history_file(download_type)

        if not history_file.exists():
            return {'last_run': None, 'downloads': []}

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {'last_run': None, 'downloads': []}

    def save(self, data: Optional[Dict] = None, download_type: DownloadType = DownloadType.REP) -> None:
        """Save history with atomic write (backup first)."""
        history_file = self._get_history_file(download_type)

        if data is None:
            data = self.load(download_type)

        with self._lock:
            # Create backup if file exists
            if history_file.exists():
                backup_file = history_file.with_suffix('.json.backup')
                shutil.copy2(history_file, backup_file)

            # Write to temp file first
            temp_file = history_file.with_suffix('.json.tmp')
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                # Atomic rename
                temp_file.replace(history_file)
            except Exception:
                if temp_file.exists():
                    temp_file.unlink()
                raise

    def add_record(self, result: DownloadResult) -> None:
        """Add a download record from DownloadResult."""
        download_type = result.download_type
        history = self.load(download_type)

        record = {
            'filename': result.filename,
            'file_path': result.file_path,
            'file_size': result.file_size,
            'file_type': result.file_type.value if result.file_type else None,
            'scheme': result.scheme.value if result.scheme else None,
            'month': result.month,
            'year': result.year,
            'download_date': result.download_date.isoformat(),
            'url': result.url,
            'metadata': result.metadata
        }

        history['downloads'].append(record)
        history['last_run'] = datetime.now().isoformat()

        self.save(history, download_type)

    def exists(self, filename: str, download_type: DownloadType = DownloadType.REP) -> bool:
        """Check if a file has already been downloaded."""
        history = self.load(download_type)
        downloads = history.get('downloads', [])
        return any(d['filename'] == filename for d in downloads)

    def get_all(self, download_type: DownloadType = DownloadType.REP) -> List[Dict]:
        """Get all download records."""
        history = self.load(download_type)
        return history.get('downloads', [])

    def get_record(self, filename: str, download_type: DownloadType = DownloadType.REP) -> Optional[Dict]:
        """Get single download record by filename."""
        downloads = self.get_all(download_type)
        for download in downloads:
            if download['filename'] == filename:
                return download
        return None

    def delete_record(self, filename: str, download_type: DownloadType = DownloadType.REP) -> bool:
        """Remove download record from history."""
        history = self.load(download_type)
        downloads = history.get('downloads', [])

        original_count = len(downloads)
        history['downloads'] = [d for d in downloads if d['filename'] != filename]

        if len(history['downloads']) < original_count:
            self.save(history, download_type)
            return True
        return False

    def get_statistics(self, download_type: DownloadType = DownloadType.REP) -> Dict[str, Any]:
        """Calculate statistics for downloads."""
        history = self.load(download_type)
        downloads = history.get('downloads', [])

        total_files = len(downloads)
        total_size = sum(d.get('file_size', 0) for d in downloads)
        last_run = history.get('last_run')

        # Get file type breakdown
        file_types: Dict[str, int] = {}
        for download in downloads:
            file_type = download.get('file_type')
            if file_type:
                file_types[file_type] = file_types.get(file_type, 0) + 1

        # Get scheme breakdown
        schemes: Dict[str, int] = {}
        for download in downloads:
            scheme = download.get('scheme', 'ucs')
            schemes[scheme] = schemes.get(scheme, 0) + 1

        return {
            'total_files': total_files,
            'total_size': total_size,
            'total_size_formatted': self._format_size(total_size),
            'last_run': last_run,
            'file_types': file_types,
            'schemes': schemes
        }

    def get_by_date(
        self,
        month: int,
        year: int,
        scheme: Optional[str] = None,
        download_type: DownloadType = DownloadType.REP
    ) -> List[Dict]:
        """Get downloads for specific month/year."""
        downloads = self.get_all(download_type)

        filtered = [
            d for d in downloads
            if d.get('month') == month and d.get('year') == year
        ]

        if scheme:
            filtered = [d for d in filtered if d.get('scheme', 'ucs') == scheme]

        # Sort by download date (most recent first)
        filtered.sort(key=lambda d: d.get('download_date', ''), reverse=True)
        return filtered

    def get_by_scheme(
        self,
        scheme: str,
        download_type: DownloadType = DownloadType.REP
    ) -> List[Dict]:
        """Get all downloads for a specific scheme."""
        downloads = self.get_all(download_type)

        filtered = [d for d in downloads if d.get('scheme', 'ucs') == scheme]
        filtered.sort(key=lambda d: d.get('download_date', ''), reverse=True)
        return filtered

    def get_latest(self, n: int = 5, download_type: DownloadType = DownloadType.REP) -> List[Dict]:
        """Get n most recent downloads."""
        downloads = self.get_all(download_type)
        sorted_downloads = sorted(
            downloads,
            key=lambda d: d.get('download_date', ''),
            reverse=True
        )
        return sorted_downloads[:n]

    def get_available_dates(self, download_type: DownloadType = DownloadType.REP) -> List[Dict]:
        """Get list of available month/year combinations."""
        downloads = self.get_all(download_type)
        date_counts: Dict[tuple, int] = {}

        month_names = {
            1: 'January', 2: 'February', 3: 'March', 4: 'April',
            5: 'May', 6: 'June', 7: 'July', 8: 'August',
            9: 'September', 10: 'October', 11: 'November', 12: 'December'
        }

        for download in downloads:
            month = download.get('month')
            year = download.get('year')

            if month and year:
                key = (year, month)
                date_counts[key] = date_counts.get(key, 0) + 1

        available_dates = [
            {
                'month': month,
                'year': year,
                'count': count,
                'label': f"{month_names.get(month, month)} {year}"
            }
            for (year, month), count in date_counts.items()
        ]

        available_dates.sort(key=lambda d: (d['year'], d['month']), reverse=True)
        return available_dates

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
