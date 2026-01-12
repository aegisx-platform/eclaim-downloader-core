"""Default configuration values for eclaim_core."""

DEFAULT_SETTINGS = {
    # Credentials
    "eclaim_username": "",
    "eclaim_password": "",

    # Paths
    "download_dir": "./downloads",
    "log_file": "logs/realtime.log",
    "history_file": "download_history.json",
    "stm_history_file": "stm_download_history.json",

    # Download defaults
    "default_schemes": ["ucs"],
    "enabled_schemes": ["ucs", "ofc", "sss", "lgo"],
}

# Valid insurance scheme codes
VALID_SCHEMES = ["ucs", "ofc", "sss", "lgo", "nhs", "bkk", "bmt", "srt"]

# Environment variable mapping
ENV_MAPPING = {
    "ECLAIM_USERNAME": "eclaim_username",
    "ECLAIM_PASSWORD": "eclaim_password",
    "DOWNLOAD_DIR": "download_dir",
    "LOG_FILE": "log_file",
}
