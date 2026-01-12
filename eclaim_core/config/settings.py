"""
Settings Manager
Handles configuration loading from JSON and environment variables.
"""

import json
import os
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from .defaults import DEFAULT_SETTINGS, ENV_MAPPING, VALID_SCHEMES


class SettingsManager:
    """
    Manages application settings.
    Priority: environment variables > settings.json > defaults
    """

    def __init__(self, settings_file: str = "config/settings.json"):
        self.settings_file = Path(settings_file)
        self._settings: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load settings from file and environment."""
        # Start with defaults
        self._settings = DEFAULT_SETTINGS.copy()

        # Load from JSON file if exists
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    file_settings = json.load(f)
                    self._settings.update(file_settings)
            except (json.JSONDecodeError, IOError):
                pass

        # Override with environment variables (highest priority)
        for env_key, setting_key in ENV_MAPPING.items():
            if env_key in os.environ:
                self._settings[setting_key] = os.environ[env_key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value (in memory only)."""
        self._settings[key] = value

    def save(self) -> bool:
        """Save settings to JSON file."""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                # Don't save password to file
                save_settings = {
                    k: v for k, v in self._settings.items()
                    if k != 'eclaim_password'
                }
                json.dump(save_settings, f, indent=2, ensure_ascii=False)
            return True
        except IOError:
            return False

    def get_credentials(self) -> Tuple[str, str]:
        """Get NHSO credentials."""
        return (
            self.get("eclaim_username", ""),
            self.get("eclaim_password", "")
        )

    def has_credentials(self) -> bool:
        """Check if credentials are configured."""
        username, password = self.get_credentials()
        return bool(username and password)

    def update_credentials(self, username: str, password: str) -> bool:
        """Update E-Claim credentials."""
        self.set('eclaim_username', username)
        self.set('eclaim_password', password)
        return self.save()

    @property
    def download_dir(self) -> str:
        """Get download directory path."""
        return self.get("download_dir", "./downloads")

    @property
    def log_file(self) -> str:
        """Get log file path."""
        return self.get("log_file", "logs/realtime.log")

    @property
    def history_file(self) -> str:
        """Get REP history file path."""
        return self.get("history_file", "download_history.json")

    @property
    def stm_history_file(self) -> str:
        """Get STM history file path."""
        return self.get("stm_history_file", "stm_download_history.json")

    # Scheme settings

    def get_enabled_schemes(self) -> List[str]:
        """Get list of enabled insurance scheme codes."""
        return self.get('enabled_schemes', ['ucs', 'ofc', 'sss', 'lgo'])

    def update_enabled_schemes(self, schemes: List[str]) -> bool:
        """Update enabled insurance schemes."""
        # Validate schemes
        schemes = [s.lower() for s in schemes if s.lower() in VALID_SCHEMES]

        if not schemes:
            schemes = ['ucs']  # Default to UCS

        self.set('enabled_schemes', schemes)
        return self.save()

    def is_scheme_enabled(self, scheme: str) -> bool:
        """Check if a specific scheme is enabled."""
        enabled = self.get_enabled_schemes()
        return scheme.lower() in [s.lower() for s in enabled]

    def get_default_schemes(self) -> List[str]:
        """Get default schemes for downloads."""
        return self.get('default_schemes', ['ucs'])

    # Reload

    def reload(self) -> None:
        """Reload settings from file and environment."""
        self.load()
