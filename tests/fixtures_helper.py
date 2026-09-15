"""
Helper utilities and deterministic mock HTTP server for integration and E2E testing.
Provides valid MP3 binary frames and local HTTP handlers.
"""

import http.server
import socketserver
import threading
from pathlib import Path
from typing import Generator, Tuple

# Minimal valid MP3 frame byte header (MPEG-1 Layer 3, 128 kbps, 44.1 kHz, padded)
# Frame sync (11 bits 1s) + MPEG-1 (11) + Layer III (01) + no CRC (1) -> 0xFF 0xFB
# Bitrate 128 kbps (1001) + Sample rate 44.1kHz (00) + Pad (1) + Priv (0) -> 0x92 (or 0x90)
# Channel Joint Stereo (01) + Ext (00) + Copy (0) + Orig (1) + Emph (00) -> 0x41
MINIMAL_VALID_MP3_FRAME = b"\xff\xfb\x90\x44" + b"\x00" * 413  # 417 bytes frame size for 128kbps/44.1kHz


def generate_valid_mp3_bytes(num_frames: int = 10) -> bytes:
    """Generate deterministic byte sequence representing valid MP3 frames with ID3v2 tag."""
    # ID3v2.3 header: "ID3" (3) + version (2) + flags (1) + size (4 synchsafe) = 10 bytes
    id3_tag = b"ID3\x03\x00\x00\x00\x00\x00\x20" + b"\x00" * 32
    audio_frames = MINIMAL_VALID_MP3_FRAME * num_frames
    return id3_tag + audio_frames


class TestAudioHTTPHandler(http.server.BaseHTTPRequestHandler):
    """Local HTTP Server handler for serving deterministic test audio and simulating failure modes."""

    def do_GET(self) -> None:
        if self.path == "/valid-song.mp3" or self.path == "/track1.mp3" or self.path == "/track2.mp3":
            content = generate_valid_mp3_bytes(15)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/html-masquerade.mp3":
            # Simulates an anti-bot or 404 HTML page returned with 200 OK
            content = b"<html><head><title>Cloudflare DDoS Protection</title></head><body>Please verify</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/empty.mp3":
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", "0")
            self.end_headers()
            self.wfile.write(b"")
        elif self.path == "/not-found.mp3":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")
        elif self.path == "/flaky-song.mp3":
            # Fails first 2 times, succeeds on 3rd attempt
            if not hasattr(self.server, "flaky_count"):
                self.server.flaky_count = 0  # type: ignore[attr-defined]
            self.server.flaky_count += 1  # type: ignore[attr-defined]
            if self.server.flaky_count < 3:  # type: ignore[attr-defined]
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"Service Temporarily Unavailable")
            else:
                content = generate_valid_mp3_bytes(10)
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        # Silence HTTP server logs during test execution
        pass


class LocalTestServer:
    """Context manager / helper for launching a local test HTTP server on an ephemeral port."""

    def __init__(self) -> None:
        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), TestAudioHTTPHandler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> str:
        self.thread.start()
        return f"http://127.0.0.1:{self.port}"

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
