"""
Settings Router for V6 Web API.
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_settings
from api.schemas.common import ApiResponse
from api.schemas.settings import SettingsResponse, SettingsUpdateRequest, DownloadSettings
from config.settings import Settings

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=ApiResponse[Dict[str, Any]])
def get_current_settings(
    settings_obj: Settings = Depends(get_settings),
) -> ApiResponse[Dict[str, Any]]:
    """Fetch current system configuration."""
    return ApiResponse(
        success=True,
        data={
            "download": {
                "output_dir": settings_obj.download_dir,
                "concurrent_enabled": settings_obj.get("download.concurrent_enabled", True),
                "max_workers": settings_obj.get("download.max_workers", 3),
                "preferred_quality": settings_obj.get("download.preferred_quality", 320),
                "retries": settings_obj.get("download.retries", 3),
            },
            "sources": settings_obj.get("sources", {}),
            "library": settings_obj.get("library", {}),
            "version": "6.0.0",
        },
    )


@router.put("", response_model=ApiResponse[Dict[str, Any]])
def update_settings(
    payload: SettingsUpdateRequest,
    settings_obj: Settings = Depends(get_settings),
) -> ApiResponse[Dict[str, Any]]:
    """Update system settings."""
    if payload.output_dir is not None:
        settings_obj.set("download.output_dir", payload.output_dir)
    if payload.max_workers is not None:
        settings_obj.set("download.max_workers", payload.max_workers)
    if payload.preferred_quality is not None:
        settings_obj.set("download.preferred_quality", payload.preferred_quality)
    if payload.concurrent_enabled is not None:
        settings_obj.set("download.concurrent_enabled", payload.concurrent_enabled)

    settings_obj.save()
    return ApiResponse(success=True, message="Settings updated successfully")
