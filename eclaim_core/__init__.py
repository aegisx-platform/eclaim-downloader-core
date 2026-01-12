"""
E-Claim Download Core Module
Standalone download system for NHSO E-Claim data.
"""

from .types import (
    DownloadType,
    FileType,
    Scheme,
    DownloadResult,
    DownloadProgress,
    DownloadLink,
)

__version__ = "0.1.0"
__all__ = [
    "DownloadType",
    "FileType",
    "Scheme",
    "DownloadResult",
    "DownloadProgress",
    "DownloadLink",
]
