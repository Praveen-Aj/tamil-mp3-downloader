"""
Artwork Delivery and Resolution Router for V6 Web API.
Serves high-resolution artwork or procedural aesthetic fallback for any library entity.
"""

import io
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.deps import get_artwork_manager, get_service
from library.artwork import ArtworkManager, ArtworkState
from library.service import LibraryService

router = APIRouter(prefix="/artwork", tags=["Artwork"])


@router.get("/system/stats")
def get_artwork_stats(
    artwork_mgr: ArtworkManager = Depends(get_artwork_manager),
) -> Dict[str, Any]:
    """Return memory and disk cache performance statistics."""
    return artwork_mgr.get_stats()


@router.get("/{category}/{entity_id}/status")
def get_artwork_status(
    category: str,
    entity_id: str,
    artwork_mgr: ArtworkManager = Depends(get_artwork_manager),
) -> Dict[str, Any]:
    """
    Check current resolution state of an entity's artwork (FOUND, PENDING, NOT_FOUND, FAILED).
    """
    cat = category.lower()
    state = artwork_mgr.resolver.get_state(cat, entity_id)
    cache_key = f"{cat}:{entity_id}"
    has_disk_cached = artwork_mgr.disk_cache.has(cache_key)

    return {
        "category": cat,
        "entity_id": entity_id,
        "state": state.value.lower(),
        "cached": has_disk_cached,
    }


@router.get("/{category}/{entity_id}")
def get_artwork(
    category: str,
    entity_id: str,
    width: int = Query(default=300, ge=32, le=1024),
    height: int = Query(default=300, ge=32, le=1024),
    service: LibraryService = Depends(get_service),
    artwork_mgr: ArtworkManager = Depends(get_artwork_manager),
) -> Response:
    """
    Serve high-resolution artwork or procedural aesthetic fallback for any library entity.
    Categories: song, movie, artist, chart, playlist.
    """
    valid_categories = {"song", "movie", "artist", "chart", "playlist"}
    cat = category.lower()
    if cat not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category: {category}. Valid: {valid_categories}",
        )

    # Use centralized ArtworkResolver
    result = artwork_mgr.resolver.resolve(
        category=cat,
        entity_id=entity_id,
        service=service,
        size=(width, height),
        allow_async_enrich=True,
    )

    pil_image = result.image
    buf = io.BytesIO()
    if pil_image.mode in ("RGBA", "P", "LA"):
        pil_image = pil_image.convert("RGB")
    pil_image.save(buf, format="JPEG", quality=88, optimize=True)
    image_bytes = buf.getvalue()

    cache_control = (
        "public, max-age=86400, immutable"
        if result.state == ArtworkState.FOUND
        else "public, max-age=60"
    )

    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": cache_control,
            "Content-Length": str(len(image_bytes)),
            "X-Artwork-State": result.state.value,
            "X-Artwork-Source": result.source_type,
            "X-Artwork-Confidence": f"{result.confidence:.2f}",
        },
    )
