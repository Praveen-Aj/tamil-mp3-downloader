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


def _format_import_item(it, idx: int = 1, service: Optional[LibraryService] = None) -> Dict[str, Any]:
    it_id = getattr(it, "id", None) or getattr(it, "track_index", None) or idx
    state_val = it.state.value if hasattr(it.state, "value") else str(it.state)
    canonical_song_id = getattr(it, "canonical_song_id", None) or getattr(it, "matched_song_id", None)

    is_owned = False
    if state_val == "OWNED":
        is_owned = True
    elif canonical_song_id and service:
        s = service.db.get_song(canonical_song_id)
        if s and (getattr(s.state, "value", str(s.state)) == "OWNED" or s.file_path):
            is_owned = True

    is_matched = state_val in ["READY", "OWNED", "COMPLETED"] or bool(getattr(it, "selected_source_url", None))

    return {
        "id": it_id,
        "track_index": getattr(it, "track_index", idx),
        "title": it.title,
        "artist": it.artist or "Unknown Artist",
        "album": it.album or "",
        "duration_sec": getattr(it, "duration_seconds", None),
        "state": "OWNED" if is_owned else state_val,
        "is_owned": is_owned,
        "is_matched": is_matched,
        "matched_song_id": canonical_song_id,
        "provider": getattr(it, "selected_provider", "Web Audio"),
        "source_url": getattr(it, "selected_source_url", None),
        "match_explanation": getattr(it, "match_explanation", ""),
    }


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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported URL or failure analyzing source",
        )

    formatted_items = [_format_import_item(it, idx, service) for idx, it in enumerate(items, start=1)]
    matched_count = sum(1 for it in formatted_items if it["is_matched"])
    owned_count = sum(1 for it in formatted_items if it["is_owned"])

    return ApiResponse(
        success=True,
        message=f"Import analysis completed for {job.url}",
        data={
            "id": job.id,
            "url": job.url,
            "title": getattr(job, "title", "Imported Playlist") or "Imported Playlist",
            "platform": getattr(job.platform, "value", str(job.platform)).lower() if hasattr(job, "platform") else "spotify",
            "status": getattr(job.status, "value", str(job.status)).lower() if hasattr(job, "status") else "ready",
            "total_tracks": len(formatted_items),
            "matched_tracks": matched_count,
            "downloaded_tracks": owned_count,
            "items": formatted_items,
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

    formatted_items = [_format_import_item(it, idx, service) for idx, it in enumerate(items, start=1)]
    matched_count = sum(1 for it in formatted_items if it["is_matched"])
    owned_count = sum(1 for it in formatted_items if it["is_owned"])

    return ApiResponse(
        success=True,
        data={
            "job_id": job.id,
            "id": job.id,
            "url": job.url,
            "platform": getattr(job.platform, "value", str(job.platform)).lower() if hasattr(job, "platform") else "spotify",
            "title": job.title or "Imported Music",
            "total_items": len(formatted_items),
            "total_tracks": len(formatted_items),
            "matched_tracks": matched_count,
            "downloaded_tracks": owned_count,
            "status": getattr(job.status, "value", str(job.status)).lower() if hasattr(job, "status") else "ready",
            "items": formatted_items,
        },
    )


@router.post("/execute", response_model=ApiResponse[Dict[str, Any]])
def execute_import(
    payload: ImportExecuteRequest,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Execute import job and start downloading selected or all matched tracks."""
    job_id = payload.job_id
    if not job_id and payload.url:
        job, _ = service.analyze_music_url(payload.url)
        if job:
            job_id = job.id

    if not job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid job_id or url is required",
        )

    job = service.get_import_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import job {job_id} not found",
        )

    # 1. Optionally create/update logical playlist without duplicating physical files
    created_pl_id = None
    if payload.create_playlist:
        items = service.get_import_job_items(job_id)
        pl_name = (payload.playlist_name or job.title or "Imported Playlist").strip()
        pl_desc = f"Imported from {getattr(job.platform, 'value', str(job.platform))} ({job.url})"
        from library.models import Playlist as DBPlaylist
        pl_obj = DBPlaylist(name=pl_name, description=pl_desc)
        created_pl_id = service.db.create_playlist(pl_obj)
        if created_pl_id and items:
            for it in items:
                if payload.item_ids is None or it.id in payload.item_ids:
                    s_id = it.canonical_song_id
                    if not s_id:
                        from library.models import LibrarySong
                        s_obj = LibrarySong(
                            title=it.title,
                            artist=it.artist or "",
                            album=it.album or pl_name,
                            duration_seconds=it.duration_seconds,
                        )
                        s_id = service.db.add_song(s_obj)
                    if s_id:
                        service.db.add_playlist_item(created_pl_id, s_id)

    # 2. Trigger asynchronous execution of download job
    service.execute_import_job(
        job_id=job_id,
        item_ids=payload.item_ids,
        run_async=True,
    )

    return ApiResponse(
        success=True,
        message=f"Queued download for import job {job_id}",
        data={
            "job_id": job_id,
            "playlist_id": created_pl_id,
            "queued": True,
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
