"""
System and Diagnostic Endpoints.
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends
from api.deps import get_service, get_settings
from api.schemas.common import ApiResponse
from library.service import LibraryService
from config.settings import Settings

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health", response_model=ApiResponse[Dict[str, Any]])
def get_health() -> ApiResponse[Dict[str, Any]]:
    """Healthcheck endpoint for monitoring and frontend connectivity."""
    return ApiResponse(
        success=True,
        data={
            "status": "healthy",
            "version": "6.0.0",
            "mode": "standalone_local",
        }
    )


@router.get("/stats", response_model=ApiResponse[Dict[str, Any]])
def get_system_stats(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Return library high-level counts and statistics."""
    stats = service.get_dashboard_stats()
    stats["total_owned"] = stats.get("owned_songs", 0)
    stats["total_storage_bytes"] = stats.get("storage_bytes", 0)
    stats["queued_downloads"] = len(service.registry.get_queued_downloads()) if hasattr(service.registry, "get_queued_downloads") else 0
    stats["active_downloads"] = len(service.registry.get_active_downloads()) if hasattr(service.registry, "get_active_downloads") else stats.get("active_downloads", 0)

    try:
        stats["total_movies"] = len(service.db.list_movies(limit=10000))
    except Exception:
        stats["total_movies"] = 0
    try:
        stats["total_artists"] = len(service.db.list_artists(limit=10000))
    except Exception:
        stats["total_artists"] = 0
    try:
        stats["total_charts"] = len(service.get_all_charts())
    except Exception:
        stats["total_charts"] = 0
    try:
        _, total_pl = service.get_playlists_page(page=1, page_size=1)
        stats["total_playlists"] = total_pl
    except Exception:
        stats["total_playlists"] = 0

    return ApiResponse(success=True, data=stats)


@router.get("/sources", response_model=ApiResponse[Dict[str, Any]])
def get_registered_sources(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Return status and health of all registered scraper providers."""
    sources = [
        {
            "name": s.name,
            "display_name": getattr(s, "display_name", s.name),
            "enabled": s.enabled,
            "priority": getattr(s, "priority", 100),
            "is_usable": getattr(s, "is_usable", True),
        }
        for s in service.source_registry.get_all_sources()
    ]
    return ApiResponse(success=True, data={"sources": sources})
