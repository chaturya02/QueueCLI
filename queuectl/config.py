"""Configuration management"""

import json
import os
from pathlib import Path
from typing import Any, Dict


class ConfigManager:
    """Manages queuectl configuration"""

    DEFAULT_CONFIG = {
        "max_retries": 3,
        "backoff_base": 2,
        "db_path": "queuectl.db",
    }

    def __init__(self, config_path: str = "queuectl_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    # Merge with defaults for missing keys
                    return {**self.DEFAULT_CONFIG, **config}
            except (json.JSONDecodeError, IOError):
                return self.DEFAULT_CONFIG.copy()
        else:
            return self.DEFAULT_CONFIG.copy()

    def _save_config(self):
        """Save configuration to file"""
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value
        self._save_config()

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration"""
        return self.config.copy()

    def reset(self):
        """Reset to default configuration"""
        self.config = self.DEFAULT_CONFIG.copy()
        self._save_config()
