"""
Configuration settings for Tamil MP3 Downloader.
"""

from pathlib import Path
from typing import Any, Dict, Optional


class Settings:
    """Application settings and configuration."""

    # Default settings
    DEFAULT_CONFIG = {
        "sources": {
            "isaimini": {
                "base_url": "https://www.isaiminihq.com",
                "enabled": True,
                "categories": ["latest", "2026", "2025", "old"]
            },
            "masstamilan": {
                "base_url": "https://www.masstamilan.dev",
                "enabled": True,
                "categories": ["latest", "2026", "2025", "old"]
            },
            "friendstamilmp3": {
                "base_url": "https://www.friendstamilmp3.in",
                "enabled": True,
                "categories": ["latest", "2026", "2025", "old"]
            }
        },
        "download": {
            "output_dir": "output",
            "chunk_size": 65536,
            "timeout": 90,
            "max_workers": 3,
            "retries": 3,
            "preferred_quality": "320kbps"
        },
        "ui": {
            "page_size": 10,
            "show_progress": True,
            "color_output": True
        },
        "logging": {
            "level": "INFO",
            "file_logging": True
        }
    }

    def __init__(self, config_file: Optional[Path] = None) -> None:
        self.config_file = config_file or Path("config/settings.json")
        self._config: Dict[str, Any] = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self) -> None:
        """Load settings from file."""
        if self.config_file.exists():
            try:
                import json
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    self._deep_update(self._config, loaded_config)
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")

    def save(self) -> None:
        """Save settings to file."""
        try:
            import json
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save config file: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except KeyError:
            return default

    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value
        self.save()

    def _deep_update(self, base_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> None:
        """Deep update a dictionary."""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    @property
    def output_dir(self) -> Path:
        """Get output directory."""
        return Path(self.get("download.output_dir", "output"))

    @property
    def isaimini_url(self) -> str:
        """Get IsaiminiHQ base URL."""
        return self.get("sources.isaimini.base_url")

    @property
    def page_size(self) -> int:
        """Get page size for menus."""
        return self.get("ui.page_size", 10)


# Global settings instance
settings = Settings()
