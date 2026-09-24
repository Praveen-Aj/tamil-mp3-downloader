"""
Main FastAPI Web Application Entry Point for V6 Web Platform.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import get_service
from api.routes import all_routers
from api.websocket import ws_manager
from library.service import DownloadProgressEvent

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Connects thread-safe WebSocket bridge to LibraryService progress listeners.
    """
    loop = asyncio.get_running_loop()
    ws_manager.set_loop(loop)

    service = get_service()

    def progress_listener(event: DownloadProgressEvent) -> None:
        """Listener invoked by background download workers."""
        try:
            ws_manager.dispatch_from_thread(
                event_type="download.progress",
                data={
                    "download_id": event.download_id,
                    "song_id": event.song_id,
                    "track_title": event.track_title,
                    "artist": event.artist,
                    "status": event.status,
                    "progress_percent": round(event.progress_percent, 1),
                    "bytes_downloaded": event.bytes_downloaded,
                    "total_bytes": event.total_bytes,
                    "speed_kbps": round(event.speed_kbps, 1),
                    "eta_seconds": event.eta_seconds,
                    "error": event.error,
                },
            )
        except Exception:
            logger.debug("Failed dispatching progress event", exc_info=True)

    service.add_progress_listener(progress_listener)
    logger.info("FastAPI V6 application started with WebSocket progress listener.")

    yield

    service.remove_progress_listener(progress_listener)
    logger.info("FastAPI V6 application shutting down.")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="Tamil MP3 Downloader API",
        description="REST and WebSocket API backend for personal Tamil music discovery, library management, and streaming.",
        version="6.0.0",
        lifespan=lifespan,
    )

    # 1. Enable CORS for local web dev and LAN devices
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. WebSocket live event endpoint
    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket) -> None:
        await ws_manager.connect(websocket)
        try:
            while True:
                # Keepalive / ping reception
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text('{"event":"pong"}')
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
        except Exception:
            ws_manager.disconnect(websocket)

    # 3. Mount all API route modules
    for router in all_routers:
        app.include_router(router, prefix="/api")

    # 4. Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error processing %s: %s", request.url.path, str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error occurred",
                "message": str(exc),
            },
        )

    return app


# Default ASGI app instance
app = create_app()
