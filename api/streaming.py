"""
Audio Streaming Utility Supporting HTTP 206 Partial Content (Byte-Range Requests).
"""

import os
from pathlib import Path
from typing import Generator, Optional, Tuple
from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse


def parse_byte_range(range_header: str, file_size: int) -> Tuple[int, int]:
    """Parse HTTP Range header into start and end byte offsets."""
    if not range_header.startswith("bytes="):
        raise ValueError("Invalid range header format")

    range_spec = range_header[6:].strip()
    parts = range_spec.split("-")
    if len(parts) != 2:
        raise ValueError("Invalid range header parts")

    start_str, end_str = parts[0].strip(), parts[1].strip()

    if start_str and end_str:
        start = int(start_str)
        end = int(end_str)
    elif start_str:
        start = int(start_str)
        end = file_size - 1
    elif end_str:
        # Suffix range (last N bytes)
        length = int(end_str)
        start = max(0, file_size - length)
        end = file_size - 1
    else:
        raise ValueError("Empty range bounds")

    if start < 0 or start >= file_size or end < start:
        raise ValueError("Range bounds out of limits")

    end = min(end, file_size - 1)
    return start, end


def stream_file_chunk(
    file_path: Path,
    start: int,
    end: int,
    chunk_size: int = 65536,
) -> Generator[bytes, None, None]:
    """Yield file chunks between start and end byte positions."""
    bytes_remaining = (end - start) + 1
    with open(file_path, "rb") as f:
        f.seek(start)
        while bytes_remaining > 0:
            read_size = min(chunk_size, bytes_remaining)
            chunk = f.read(read_size)
            if not chunk:
                break
            bytes_remaining -= len(chunk)
            yield chunk


def create_audio_stream_response(file_path: Path, request: Request) -> StreamingResponse:
    """
    Create a streaming HTTP response for audio files with 206 Partial Content support.
    """
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio file not found: {file_path.name}",
        )

    file_size = file_path.stat().st_size
    range_header = request.headers.get("Range")

    content_type = "audio/mpeg"
    if file_path.suffix.lower() == ".m4a":
        content_type = "audio/mp4"
    elif file_path.suffix.lower() == ".flac":
        content_type = "audio/flac"

    if not range_header:
        # Full content stream (HTTP 200)
        return StreamingResponse(
            stream_file_chunk(file_path, 0, file_size - 1),
            media_type=content_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Disposition": f'inline; filename="{file_path.name}"',
            },
            status_code=status.HTTP_200_OK,
        )

    try:
        start, end = parse_byte_range(range_header, file_size)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    content_length = (end - start) + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Disposition": f'inline; filename="{file_path.name}"',
    }

    return StreamingResponse(
        stream_file_chunk(file_path, start, end),
        media_type=content_type,
        headers=headers,
        status_code=status.HTTP_206_PARTIAL_CONTENT,
    )
