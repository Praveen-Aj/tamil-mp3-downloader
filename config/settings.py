"""
Configuration settings for Tamil MP3 Downloader.
"""

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Settings:
    """Application settings and configuration."""

    # Default settings
    DEFAULT_CONFIG: Dict[str, Any] = {
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
            },
            "kollysongs": {
                "base_url": "https://www.kollysongs.com",
                "enabled": True,
                "categories": ["latest", "2026", "2025", "old", "music-directors"]
            }
        },
        "download": {
            "output_dir": "downloads",
            "chunk_size": 65536,
            "timeout": 90,
            "concurrent_enabled": True,
            "max_workers": 3,
            "retries": 3,
            "preferred_quality": 320,
            "external_downloader": {
                "enabled": False,
                "aria2_path": "aria2c.exe",
                "detached": True,
                "queue_mode": True,
                "max_concurrent": 3
            }
        },
        "ui": {
            "page_size": 10,
            "show_progress": True,
            "color_output": True,
            "preferred_source": "",
            "cache": {
                "enabled": True,
                "ttl_seconds": 21600
            },
            "dedupe": {
                "strategy": "smaller-size"
            },
            "top_loading": {
                "adaptive_enabled": True,
                "min_albums": 24,
                "large_cutoff": 40,
                "window_small": 6,
                "window_large": 10,
                "plateau_growth": 1,
                "plateau_streak": 2
            }
        },
        "logging": {
            "level": "INFO",
            "file_logging": True
        },
        "library": {
            "enabled": True,
            "database_path": "",
            "canonicalization": {
                "strip_variants": True,
                "case_insensitive": True,
                "normalize_whitespace": True
            },
            "upgrade_policy": "auto",  # auto, manual, never
            "upgrade_quality_threshold": 64,  # Only upgrade if quality difference >= 64kbps
            "multiple_locations": False
        }
    }

    def __init__(self, config_file: Optional[Path] = None) -> None:
        self.config_file = config_file or Path("config/settings.json")
        self._config: Dict[str, Any] = copy.deepcopy(self.DEFAULT_CONFIG)
        self.load()
        if not self.config_file.exists():
            self.save()

    def load(self) -> None:
        """Load settings from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                self._deep_update(self._config, loaded_config)
            except Exception:
                logger.warning(
                    "Could not load config file at %s; using defaults.",
                    self.config_file,
                    exc_info=True,
                )

    def save(self) -> None:
        """Save settings to file."""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except Exception:
            logger.warning(
                "Could not save config file at %s.",
                self.config_file,
                exc_info=True,
            )

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
        """Get authoritative absolute output directory."""
        val = self.get("download.output_dir", "downloads")
        p = Path(val) if val else Path("downloads")
        if "pytest" in str(p).lower() and not p.exists():
            p = Path("downloads")
        if not p.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            p = (project_root / p).resolve()
        return p

    @property
    def isaimini_url(self) -> str:
        """Get IsaiminiHQ base URL."""
        return self.get("sources.isaimini.base_url")

    @property
    def page_size(self) -> int:
        """Get page size for menus."""
        return self.get("ui.page_size", 10)

    @property
    def concurrent_enabled(self) -> bool:
        """Return whether concurrent downloads are enabled."""
        return bool(self.get("download.concurrent_enabled", True))

    @property
    def show_progress(self) -> bool:
        """Return whether progress bars are enabled."""
        return bool(self.get("ui.show_progress", True))

    @property
    def user_data_dir(self) -> Path:
        """Get OS-specific user data directory."""
        if os.name == 'nt':  # Windows
            data_dir = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
        else:  # Linux/Mac
            data_dir = Path.home() / '.local' / 'share'
        app_dir = data_dir / 'tamil-mp3-downloader'
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir

    @property
    def library_db_path(self) -> Path:
        """Get path to library database."""
        custom_path = self.get("library.database_path", "")
        if custom_path:
            return Path(custom_path)
        return self.user_data_dir / 'library.db'

    @property
    def library_enabled(self) -> bool:
        """Check if library system is enabled."""
        return bool(self.get("library.enabled", True))

    @property
    def upgrade_policy(self) -> str:
        """Get quality upgrade policy."""
        return self.get("library.upgrade_policy", "auto")

    @property
    def upgrade_quality_threshold(self) -> int:
        """Get quality upgrade threshold in kbps."""
        return self.get("library.upgrade_quality_threshold", 64)

    @property
    def preferred_quality_kbps(self) -> int:
        """Get canonical integer preferred quality in kbps (e.g. 320 or 128)."""
        val = self.get("download.preferred_quality", 320)
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            import re
            m = re.search(r"\d+", val)
            if m:
                return int(m.group(0))
        return 320


# Global settings instance
settings = Settings()
