from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.deps import get_settings
from api.schemas.common import ApiResponse
from api.schemas.settings import SettingsResponse, SettingsUpdateRequest, DownloadSettings
from config.settings import Settings

router = APIRouter(prefix="/settings", tags=["Settings"])


class ValidatePathRequest(BaseModel):
    path: str


@router.get("", response_model=ApiResponse[Dict[str, Any]])
def get_current_settings(
    settings_obj: Settings = Depends(get_settings),
) -> ApiResponse[Dict[str, Any]]:
    """Fetch current system configuration."""
    authoritative_dir = str(settings_obj.download_dir)
    return ApiResponse(
        success=True,
        data={
            "download": {
                "output_dir": authoritative_dir,
                "download_dir": authoritative_dir,
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


@router.post("/validate-path", response_model=ApiResponse[Dict[str, Any]])
def validate_download_path(
    payload: ValidatePathRequest,
    settings_obj: Settings = Depends(get_settings),
) -> ApiResponse[Dict[str, Any]]:
    """
    Validate and resolve download directory path.
    Resolves relative paths to the authoritative project location and verifies filesystem access.
    """
    raw_path = (payload.path or "").strip()
    if not raw_path:
        raw_path = "downloads"

    p = Path(raw_path)
    if not p.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent
        resolved = (project_root / p).resolve()
    else:
        resolved = p.resolve()

    try:
        resolved.mkdir(parents=True, exist_ok=True)
        is_valid = resolved.is_dir()
        msg = f"Authoritative directory: {resolved}" if is_valid else "Path exists but is not a directory"
    except Exception as exc:
        is_valid = False
        msg = f"Cannot access path: {exc}"

    return ApiResponse(
        success=True,
        data={
            "is_valid": is_valid,
            "message": msg,
            "resolved_path": str(resolved),
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

