"""
Settings Schemas for V6 API.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class DownloadSettings(BaseModel):
    """Download configuration options."""
    output_dir: str = "downloads"
    concurrent_enabled: bool = True
    max_workers: int = 3
    preferred_quality: int = 320
    retries: int = 3


class SourceConfigModel(BaseModel):
    """Source provider status configuration."""
    enabled: bool = True
    priority: int = 100


class SettingsResponse(BaseModel):
    """Full settings response model."""
    download: DownloadSettings
    sources: Dict[str, Any]
    library: Dict[str, Any]
    version: str = "6.0.0"


class SettingsUpdateRequest(BaseModel):
    """Partial settings update request."""
    output_dir: Optional[str] = None
    max_workers: Optional[int] = Field(default=None, ge=1, le=10)
    preferred_quality: Optional[int] = Field(default=None)
    concurrent_enabled: Optional[bool] = None
