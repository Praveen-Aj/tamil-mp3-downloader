"""
Charts Router for V6 Web API.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_service
from api.schemas.common import ApiResponse
from api.schemas.download import DownloadPlanResponse, format_download_plan
from library.service import LibraryService

router = APIRouter(prefix="/charts", tags=["Charts"])


@router.get("", response_model=ApiResponse[List[Dict[str, Any]]])
def list_charts(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[List[Dict[str, Any]]]:
    """Fetch all music discovery charts with entry counts and download stats."""
    charts = service.db.list_charts()
    chart_list = [
        {
            "id": c.id,
            "name": getattr(c, "title", getattr(c, "name", "")),
            "description": getattr(c, "chart_type", getattr(c, "description", None)),
            "source_url": getattr(c, "source_url", None),
            "frequency": getattr(c, "frequency", "weekly"),
            "total_entries": getattr(c, "total_entries", 0),
            "downloaded_entries": getattr(c, "downloaded_entries", 0),
            "last_synced_at": c.snapshot_date.isoformat() if getattr(c, "snapshot_date", None) else None,
        }
        for c in charts
    ]
    return ApiResponse(success=True, data=chart_list)


@router.get("/{chart_id}", response_model=ApiResponse[Dict[str, Any]])
def get_chart(
    chart_id: str,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Get full details of a specific chart including ranked tracklist and trends."""
    details = service.get_chart_details(chart_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart ID {chart_id} not found",
        )

    chart_obj = details.get("chart")
    chart_dict = {
        "id": chart_obj.id,
        "name": getattr(chart_obj, "title", getattr(chart_obj, "name", "")),
        "title": getattr(chart_obj, "title", getattr(chart_obj, "name", "")),
        "chart_type": getattr(chart_obj, "chart_type", "top_songs"),
        "provider_name": getattr(chart_obj, "provider_name", "regional"),
    }
    return ApiResponse(
        success=True,
        data={
            "chart": chart_dict,
            "stats": details.get("stats", {}),
            "entries": details.get("entries", []),
            "total_matching": details.get("total_matching", len(details.get("entries", []))),
        },
    )


@router.post("/sync", response_model=ApiResponse[List[str]])
def sync_charts(
    service: LibraryService = Depends(get_service),
) -> ApiResponse[List[str]]:
    """Synchronize music charts from authoritative regional and streaming sources."""
    synced = service.sync_charts()
    return ApiResponse(
        success=True,
        message=f"Synchronized {len(synced)} charts successfully",
        data=synced,
    )


@router.post("/{chart_id}/plan", response_model=ApiResponse[DownloadPlanResponse])
def plan_chart_download(
    chart_id: str,
    mode: str = Query(default="missing", pattern="^(all|missing)$"),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[DownloadPlanResponse]:
    """Generate download plan for all or missing songs in a chart."""
    if mode == "all":
        plan = service.plan_chart_download_all(chart_id)
    else:
        plan = service.plan_chart_download_missing(chart_id)

    return ApiResponse(
        success=True,
        data=format_download_plan(plan),
    )


@router.post("/{chart_id}/download", response_model=ApiResponse[Dict[str, Any]])
def execute_chart_download(
    chart_id: str,
    mode: str = Query(default="missing", pattern="^(all|missing)$"),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Execute background downloads for all or missing songs in a chart."""
    if mode == "all":
        plan = service.plan_chart_download_all(chart_id)
    else:
        plan = service.plan_chart_download_missing(chart_id)

    queued_ids = service.execute_download_plan(plan)
    queued_count = len(queued_ids) if isinstance(queued_ids, list) else queued_ids
    return ApiResponse(
        success=True,
        message=f"Queued {queued_count} downloads for chart",
        data={"chart_id": chart_id, "queued_count": queued_count},
    )
