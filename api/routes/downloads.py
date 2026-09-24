"""
Downloads Management Router for V6 Web API.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_service
from api.schemas.common import ApiResponse
from api.schemas.download import (
    DownloadPlanRequest, DownloadPlanResponse, DownloadPlanItemResponse,
    DownloadExecuteRequest, DownloadItemResponse, format_download_plan
)
from library.service import LibraryService

router = APIRouter(prefix="/downloads", tags=["Downloads"])


@router.get("", response_model=ApiResponse[List[Dict[str, Any]]])
def list_downloads(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[List[Dict[str, Any]]]:
    """Fetch all download jobs (queued, running, completed, failed)."""
    downloads = service.get_all_downloads(dedup_by_song=True)
    items = []
    for d in downloads:
        song = service.db.get_song(d.song_id) if d.song_id else None
        items.append({
            "id": d.id,
            "song_id": d.song_id,
            "title": song.title if song else "Unknown Track",
            "artist": song.artist if song else None,
            "source_name": d.source_name,
            "target_quality": d.target_quality,
            "status": d.state.value if hasattr(d.state, "value") else str(d.state),
            "bytes_downloaded": d.bytes_downloaded,
            "total_bytes": d.total_bytes,
            "progress_percent": round(d.progress_percent, 1) if d.progress_percent else 0.0,
            "speed_kbps": 0.0,
            "error_message": d.error_message,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "completed_at": d.completed_at.isoformat() if d.completed_at else None,
        })
    return ApiResponse(success=True, data=items)


@router.post("/plan", response_model=ApiResponse[DownloadPlanResponse])
def plan_downloads(
    payload: DownloadPlanRequest,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[DownloadPlanResponse]:
    """Preview download plan for a selected batch of songs."""
    plan = service.preview_download_plan(payload.song_ids)
    return ApiResponse(
        success=True,
        data=format_download_plan(plan),
    )



@router.post("/execute", response_model=ApiResponse[Dict[str, Any]])
def execute_downloads(
    payload: DownloadExecuteRequest,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Execute background downloads for selected songs."""
    plan = service.preview_download_plan(payload.song_ids)
    queued_count = service.execute_download_plan(plan)
    return ApiResponse(
        success=True,
        message=f"Queued {queued_count} downloads",
        data={"queued_count": queued_count},
    )


@router.post("/retry", response_model=ApiResponse[Dict[str, Any]])
def retry_failed(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Retry all failed download jobs using fallback sources."""
    queued_count = service.retry_failed_downloads()
    return ApiResponse(
        success=True,
        message=f"Retrying {queued_count} failed downloads",
        data={"retried_count": queued_count},
    )


@router.post("/pause", response_model=ApiResponse[Dict[str, Any]])
def pause_downloads(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Pause the background download queue."""
    service.pause_downloads()
    return ApiResponse(success=True, message="Downloads paused")


@router.post("/resume", response_model=ApiResponse[Dict[str, Any]])
def resume_downloads(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Resume the background download queue."""
    service.resume_downloads()
    return ApiResponse(success=True, message="Downloads resumed")
