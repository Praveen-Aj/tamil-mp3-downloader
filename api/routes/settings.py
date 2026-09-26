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
    Verifies that the target directory exists and is a directory without mutating the filesystem.
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

    if not resolved.exists():
        is_valid = False
        msg = f"Directory does not exist: {resolved}"
    elif not resolved.is_dir():
        is_valid = False
        msg = f"Path exists but is not a directory: {resolved}"
    else:
        is_valid = True
        msg = f"Valid directory: {resolved}"

    return ApiResponse(
        success=True,
        data={
            "is_valid": is_valid,
            "message": msg,
            "resolved_path": str(resolved),
        },
    )


@router.put("", response_model=ApiResponse[Dict[str, Any]])
@router.post("", response_model=ApiResponse[Dict[str, Any]])
def update_settings(
    payload: Dict[str, Any],
    settings_obj: Settings = Depends(get_settings),
) -> ApiResponse[Dict[str, Any]]:
    """Update system settings, supporting flat and nested download configurations."""
    # Check if download settings are nested under "download"
    dl_cfg = payload.get("download", {}) if isinstance(payload.get("download"), dict) else payload

    out_dir = dl_cfg.get("output_dir") or dl_cfg.get("download_dir") or payload.get("output_dir") or payload.get("download_dir")
    if out_dir:
        settings_obj.set("download.output_dir", str(out_dir))
        settings_obj.set("download.download_dir", str(out_dir))

    max_w = dl_cfg.get("max_workers") if "max_workers" in dl_cfg else payload.get("max_workers")
    if max_w is not None:
        settings_obj.set("download.max_workers", int(max_w))

    pref_q = dl_cfg.get("preferred_quality") if "preferred_quality" in dl_cfg else payload.get("preferred_quality")
    if pref_q is not None:
        settings_obj.set("download.preferred_quality", int(pref_q))

    conc = dl_cfg.get("concurrent_enabled") if "concurrent_enabled" in dl_cfg else payload.get("concurrent_enabled")
    if conc is not None:
        settings_obj.set("download.concurrent_enabled", bool(conc))

    if "sources" in payload and isinstance(payload["sources"], dict):
        settings_obj.set("sources", payload["sources"])

    if "library" in payload and isinstance(payload["library"], dict):
        settings_obj.set("library", payload["library"])

    settings_obj.save()
    return ApiResponse(success=True, message="Settings updated successfully")


