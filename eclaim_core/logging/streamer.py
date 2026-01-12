"""
Real-time Log Streamer
JSON-based logging with SSE streaming support.
"""

import json
import os
import time
import threading
from datetime import datetime
from typing import Generator, Optional, List, Dict, Any
from pathlib import Path


class LogStreamer:
    """
    Real-time logging with JSON format.
    Supports SSE streaming for web UI.
    """

    def __init__(self, log_file: str = "logs/realtime.log"):
        self.log_file = Path(log_file)
        self._lock = threading.Lock()

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        message: str,
        level: str = 'info',
        source: str = 'system'
    ) -> None:
        """
        Write log entry as JSON line.

        Args:
            message: Log message
            level: Log level (info, success, error, warning)
            source: Source of log (download, import, system, rep, stm, smt)
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "source": source,
            "message": message
        }

        with self._lock:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            except Exception as e:
                print(f"Error writing log: {e}")

    def stream(self, tail: int = 100) -> Generator[str, None, None]:
        """
        Generator for SSE streaming.

        Args:
            tail: Number of recent log lines to send first

        Yields:
            SSE formatted log entries
        """
        # Send initial logs (last N lines)
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    recent_lines = lines[-tail:] if len(lines) > tail else lines

                    for line in recent_lines:
                        if line.strip():
                            yield f"data: {line}\n\n"
            except Exception as e:
                error_msg = json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'level': 'error',
                    'source': 'system',
                    'message': f'Error reading logs: {str(e)}'
                })
                yield f"data: {error_msg}\n\n"

        # Stream new logs in real-time
        last_position = self.log_file.stat().st_size if self.log_file.exists() else 0

        while True:
            try:
                if self.log_file.exists():
                    current_size = self.log_file.stat().st_size

                    if current_size > last_position:
                        with open(self.log_file, 'r', encoding='utf-8') as f:
                            f.seek(last_position)
                            new_content = f.read()

                            for line in new_content.strip().split('\n'):
                                if line.strip():
                                    yield f"data: {line}\n\n"

                            last_position = current_size

                # Send heartbeat every 15 seconds to keep connection alive
                heartbeat = json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'type': 'heartbeat'
                })
                yield f": {heartbeat}\n\n"

                time.sleep(1)

            except GeneratorExit:
                break
            except Exception as e:
                error_msg = json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'level': 'error',
                    'source': 'system',
                    'message': f'Stream error: {str(e)}'
                })
                yield f"data: {error_msg}\n\n"
                time.sleep(1)

    def clear(self) -> None:
        """Clear the log file."""
        with self._lock:
            try:
                if self.log_file.exists():
                    self.log_file.unlink()
                self.log_file.touch()
            except Exception as e:
                print(f"Error clearing logs: {e}")

    def get_recent(self, lines: int = 100, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent log entries.

        Args:
            lines: Number of lines to return
            level: Optional level filter (info, success, error, warning)

        Returns:
            List of log entry dicts
        """
        try:
            if not self.log_file.exists():
                return []

            with open(self.log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()[-lines:]

            entries = []
            for line in all_lines:
                try:
                    entry = json.loads(line.strip())
                    if level is None or entry.get('level') == level:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue

            return entries
        except FileNotFoundError:
            return []

    def get_errors(self, lines: int = 50) -> List[Dict[str, Any]]:
        """Get recent error log entries."""
        return self.get_recent(lines=lines, level='error')

    def info(self, message: str, source: str = 'system') -> None:
        """Write info level log."""
        self.write(message, level='info', source=source)

    def success(self, message: str, source: str = 'system') -> None:
        """Write success level log."""
        self.write(message, level='success', source=source)

    def warning(self, message: str, source: str = 'system') -> None:
        """Write warning level log."""
        self.write(message, level='warning', source=source)

    def error(self, message: str, source: str = 'system') -> None:
        """Write error level log."""
        self.write(message, level='error', source=source)
