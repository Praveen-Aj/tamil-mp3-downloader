"""
Downloads Management Router for V6 Web API.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.deps import get_service
from api.schemas.common import ApiResponse
from api.schemas.download import (
    DownloadPlanRequest, DownloadPlanResponse, DownloadPlanItemResponse,
    DownloadExecuteRequest, DownloadItemResponse, format_download_plan
)
from library.models import Download
from library.service import LibraryService

router = APIRouter(prefix="/downloads", tags=["Downloads"])


class DownloadQueueRequest(BaseModel):
    song_ids: List[int]
    preferred_quality: Optional[int] = 320


def format_download_task(d: Download, service: LibraryService) -> Dict[str, Any]:
    """Helper to convert core Download model to API DownloadTask format."""
    song = service.db.get_song(d.song_id) if d.song_id else None
    source = service.db.get_source_by_id(d.song_source_id) if d.song_source_id else None

    st_raw = d.state.value if hasattr(d.state, "value") else str(d.state)
    st_norm = st_raw.lower()
    if st_norm in ("queued", "planned"):
        status_str = "pending"
    elif st_norm in ("downloading", "in_progress"):
        status_str = "downloading"
    elif st_norm in ("completed",):
        status_str = "completed"
    elif st_norm in ("failed",):
        status_str = "failed"
    elif st_norm in ("cancelled", "canceled"):
        status_str = "cancelled"
    else:
        status_str = st_norm

    quality = getattr(d, "target_quality", None)
    if not quality and source and getattr(source, "quality_kbps", None):
        quality = source.quality_kbps
    if not quality and song and getattr(song, "quality_kbps", None):
        quality = song.quality_kbps
    if not quality and getattr(d, "previous_quality_kbps", None):
        quality = d.previous_quality_kbps
    if not quality:
        quality = 320

    is_complete = status_str == "completed" or (hasattr(d, "is_complete") and d.is_complete)
    file_size = d.file_size_bytes or 0
    bytes_dl = getattr(d, "bytes_downloaded", file_size if is_complete else 0)
    total_bytes = getattr(d, "total_bytes", file_size if file_size > 0 else None)

    if hasattr(d, "progress_percent") and d.progress_percent:
        progress_val = d.progress_percent
    elif is_complete:
        progress_val = 100.0
    else:
        progress_val = 0.0

    active_ev = service.get_active_download_progress(d.id) if hasattr(service, "get_active_download_progress") else None
    if active_ev:
        raw_pct = getattr(active_ev, "percent", None)
        if raw_pct is not None:
            progress_val = round(raw_pct * 100.0 if raw_pct <= 1.0 else raw_pct, 1)
        else:
            progress_val = getattr(active_ev, "progress_percent", progress_val)

        bytes_dl = getattr(active_ev, "bytes_downloaded", bytes_dl)
        total_bytes = getattr(active_ev, "total_bytes", total_bytes)

        raw_speed = getattr(active_ev, "speed_bps", None)
        if raw_speed is not None:
            speed_kbps = round(raw_speed / 1024.0, 1)
        else:
            speed_kbps = getattr(active_ev, "speed_kbps", 0.0)

        eta = getattr(active_ev, "eta_seconds", None)
        if getattr(active_ev, "status", None):
            status_str = active_ev.status.lower()
    else:
        speed_kbps = 0.0
        eta = None

    source_name = getattr(d, "source_name", None)
    if not source_name and source and getattr(source, "source_name", None):
        source_name = source.source_name
    if not source_name:
        source_name = "Regional Tamil"

    created_iso = d.planned_at.isoformat() if getattr(d, "planned_at", None) else (
        d.queued_at.isoformat() if getattr(d, "queued_at", None) else None
    )
    completed_iso = d.completed_at.isoformat() if getattr(d, "completed_at", None) else None

    return {
        "id": d.id,
        "song_id": d.song_id,
        "title": song.title if song else "Unknown Track",
        "artist": song.artist if song else None,
        "album": song.album if song else None,
        "source_name": source_name,
        "target_quality": quality,
        "quality": quality,
        "status": status_str,
        "progress": round(progress_val, 1),
        "progress_percent": round(progress_val, 1),
        "bytes_downloaded": bytes_dl,
        "total_bytes": total_bytes,
        "speed_kbps": speed_kbps,
        "speed": speed_kbps,
        "eta_seconds": eta,
        "eta": eta,
        "error_message": d.error_message,
        "error": d.error_message,
        "created_at": created_iso,
        "completed_at": completed_iso,
    }


@router.get("", response_model=ApiResponse[List[Dict[str, Any]]])
def list_downloads(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[List[Dict[str, Any]]]:
    """Fetch all download jobs (queued, running, completed, failed)."""
    downloads = service.get_all_downloads(dedup_by_song=True)
    items = [format_download_task(d, service) for d in downloads]
    return ApiResponse(success=True, data=items)


@router.get("/active", response_model=ApiResponse[Dict[str, Any]])
def get_active_downloads(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Fetch active and queued downloads."""
    downloads = service.get_all_downloads(dedup_by_song=True)
    active_items = []
    for d in downloads:
        st = d.state.value if hasattr(d.state, "value") else str(d.state)
        if st.upper() in ("DOWNLOADING", "QUEUED", "PLANNED", "IN_PROGRESS"):
            active_items.append(format_download_task(d, service))
    return ApiResponse(success=True, data={"active": active_items})


@router.get("/history", response_model=ApiResponse[Dict[str, Any]])
def get_download_history(
    limit: int = Query(default=50, ge=1, le=200),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Fetch completed or failed download history."""
    downloads = service.get_all_downloads(dedup_by_song=False)
    history_items = []
    for d in downloads:
        st = d.state.value if hasattr(d.state, "value") else str(d.state)
        if st.upper() in ("COMPLETED", "FAILED", "CANCELLED"):
            history_items.append(format_download_task(d, service))
            if len(history_items) >= limit:
                break
    return ApiResponse(success=True, data={"history": history_items})


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
    queued_ids = service.execute_download_plan(plan)
    queued_count = len(queued_ids) if isinstance(queued_ids, list) else queued_ids
    return ApiResponse(
        success=True,
        message=f"Queued {queued_count} downloads",
        data={"queued_count": queued_count},
    )


@router.post("/queue", response_model=ApiResponse[Dict[str, Any]])
def queue_downloads(
    payload: DownloadQueueRequest,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Queue one or more songs for background download."""
    plan = service.preview_download_plan(payload.song_ids)
    queued_ids = service.execute_download_plan(plan)
    queued_count = len(queued_ids) if isinstance(queued_ids, list) else queued_ids
    return ApiResponse(
        success=True,
        message=f"Queued {queued_count} downloads",
        data={
            "queued_count": queued_count,
            "plan": format_download_plan(plan),
        },
    )


@router.post("/{task_id}/cancel", response_model=ApiResponse[Dict[str, Any]])
def cancel_download_task(
    task_id: int,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Cancel an active or queued download task."""
    cancelled = service.cancel_download(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Download task {task_id} not found or cannot be cancelled",
        )
    return ApiResponse(success=True, message="Download cancelled")


@router.post("/{task_id}/retry", response_model=ApiResponse[Dict[str, Any]])
def retry_download_task(
    task_id: int,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Retry a failed or cancelled download task."""
    dl = service.db.get_download(task_id)
    if not dl:
        raise HTTPException(status_code=404, detail=f"Download {task_id} not found")
    if dl.song_id:
        plan = service.preview_download_plan([dl.song_id])
        queued = service.execute_download_plan(plan)
        queued_count = len(queued) if isinstance(queued, list) else queued
        return ApiResponse(
            success=True,
            message="Download retried",
            data={"task_id": task_id, "queued_count": queued_count},
        )
    return ApiResponse(success=False, message="Cannot retry download without associated song ID")


@router.post("/retry", response_model=ApiResponse[Dict[str, Any]])
def retry_failed(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Retry all failed download jobs using fallback sources."""
    queued_ids = service.retry_failed_downloads()
    queued_count = len(queued_ids) if isinstance(queued_ids, list) else queued_ids
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
