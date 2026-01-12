"""
E-Claim Core Type Definitions
Enums, dataclasses, and type aliases for the download system.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


class DownloadType(Enum):
    """Type of download operation"""
    REP = "rep"      # Representative (OP/IP/ORF)
    STM = "stm"      # Statement
    SMT = "smt"      # Budget (SMT API)


class FileType(Enum):
    """Type of downloaded file"""
    OP = "OP"
    IP = "IP"
    ORF = "ORF"
    IP_APPEAL = "IP_APPEAL"
    IP_APPEAL_NHSO = "IP_APPEAL_NHSO"
    STM_IP = "STM_IP"
    STM_OP = "STM_OP"


class Scheme(Enum):
    """Insurance scheme codes"""
    UCS = "ucs"      # Universal Coverage Scheme
    OFC = "ofc"      # Civil Servant Medical Benefit
    SSS = "sss"      # Social Security Scheme
    LGO = "lgo"      # Local Government Officers
    NHS = "nhs"      # National Health Security
    BKK = "bkk"      # Bangkok Metropolitan
    BMT = "bmt"      # Border Medical Treatment
    SRT = "srt"      # State Railway of Thailand


@dataclass
class DownloadResult:
    """Result of a single file download"""
    success: bool
    filename: str
    file_path: str
    file_size: int
    download_type: DownloadType
    file_type: Optional[FileType] = None
    scheme: Optional[Scheme] = None
    month: Optional[int] = None
    year: Optional[int] = None  # Buddhist Era
    error: Optional[str] = None
    url: Optional[str] = None
    download_date: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DownloadProgress:
    """Progress tracking for download operations"""
    total: int = 0
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    current_file: Optional[str] = None
    is_running: bool = False
    started_at: Optional[datetime] = None

    @property
    def completed(self) -> int:
        return self.downloaded + self.skipped + self.errors

    @property
    def percent(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100


@dataclass
class DownloadLink:
    """Represents a downloadable file link"""
    url: str
    filename: str
    file_type: Optional[FileType] = None
    scheme: Optional[Scheme] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
