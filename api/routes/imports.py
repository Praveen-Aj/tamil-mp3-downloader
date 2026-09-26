"""
Universal URL and Playlist Import Router for V6 Web API.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_service
from api.schemas.common import ApiResponse
from api.schemas.import_job import (
    ImportAnalyzeRequest, ImportAnalyzeResponse, ImportCandidateItem, ImportExecuteRequest
)
from library.service import LibraryService

from pydantic import BaseModel

router = APIRouter(prefix="/imports", tags=["Imports"])


class UrlImportPayload(BaseModel):
    url: str


@router.post("/url", response_model=ApiResponse[Dict[str, Any]])
def start_url_import(
    payload: UrlImportPayload,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Initiate URL analysis and auto-import job for Spotify, YouTube, or web link."""
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL cannot be empty",
        )
    job, items = service.analyze_music_url(url)
    if not job:
        job = service.execute_import_job(url=url, auto_download=False)
        items = []

    if not job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported URL or failure analyzing source",
        )

    matched = len([it for it in items if getattr(it, "matched_song_id", None)]) if items else 0
    return ApiResponse(
        success=True,
        message=f"Import analysis initiated for {job.url}",
        data={
            "id": job.id,
            "url": job.url,
            "platform": getattr(job.platform, "value", str(job.platform)).lower() if hasattr(job, "platform") else "spotify",
            "status": getattr(job.status, "value", str(job.status)).lower() if hasattr(job, "status") else "ready",
            "total_tracks": job.total_items,
            "matched_tracks": matched,
            "downloaded_tracks": 0,
            "items": [
                {
                    "id": it.id,
                    "title": it.title,
                    "artist": it.artist,
                    "album": it.album,
                    "duration_sec": it.duration_seconds,
                    "state": it.state.value if hasattr(it.state, "value") else str(it.state),
                    "matched_song_id": it.matched_song_id,
                }
                for it in items
            ],
        },
    )


@router.post("/analyze", response_model=ApiResponse[Dict[str, Any]])
def analyze_url(
    payload: ImportAnalyzeRequest,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Analyze a music URL (Spotify, YouTube, or Direct URL) and preview tracks."""
    job, items = service.analyze_music_url(payload.url)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported URL or failure analyzing source",
        )

    candidate_items = [
        {
            "id": it.id,
            "title": it.title,
            "artist": it.artist,
            "album": it.album,
            "duration_sec": it.duration_seconds,
            "state": it.state.value if hasattr(it.state, "value") else str(it.state),
            "matched_song_id": it.matched_song_id,
        }
        for it in items
    ]

    return ApiResponse(
        success=True,
        data={
            "job_id": job.id,
            "url": job.url,
            "platform": job.platform,
            "title": job.title or "Imported Music",
            "total_items": job.total_items,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "items": candidate_items,
        },
    )


@router.post("/execute", response_model=ApiResponse[Dict[str, Any]])
def execute_import(
    payload: ImportExecuteRequest,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Execute import job and optionally start automatic downloading."""
    job = service.execute_import_job(
        url=payload.url,
        playlist_name=payload.playlist_name,
        auto_download=payload.auto_download,
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to initiate import job",
        )

    return ApiResponse(
        success=True,
        message=f"Import job initiated ({job.id})",
        data={
            "job_id": job.id,
            "platform": job.platform,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "total_items": job.total_items,
        },
    )


@router.get("", response_model=ApiResponse[List[Dict[str, Any]]])
def list_import_jobs(
    limit: int = Query(default=15, ge=1, le=50),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[List[Dict[str, Any]]]:
    """Fetch history of recent import jobs."""
    jobs = service.get_recent_import_jobs(limit=limit)
    items = [
        {
            "id": j.id,
            "url": j.url,
            "platform": j.platform,
            "title": j.title,
            "status": j.status.value if hasattr(j.status, "value") else str(j.status),
            "total_items": j.total_items,
            "processed_items": j.processed_items,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]
    return ApiResponse(success=True, data=items)


@router.get("/{job_id}", response_model=ApiResponse[Dict[str, Any]])
@router.get("/jobs/{job_id}", response_model=ApiResponse[Dict[str, Any]])
def get_import_job(
    job_id: str,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Get full status and items of a specific import job."""
    job = service.get_import_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import job {job_id} not found",
        )

    items = service.get_import_job_items(job_id)
    return ApiResponse(
        success=True,
        data={
            "id": job.id,
            "url": job.url,
            "platform": job.platform,
            "title": job.title,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "total_items": job.total_items,
            "processed_items": job.processed_items,
            "items": [
                {
                    "id": it.id,
                    "title": it.title,
                    "artist": it.artist,
                    "state": it.state.value if hasattr(it.state, "value") else str(it.state),
                    "matched_song_id": it.matched_song_id,
                }
                for it in items
            ],
        },
    )
