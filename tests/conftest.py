"""
Pytest configuration and shared deterministic fixtures.
"""

from pathlib import Path
import os
import sys
import pytest

# Ensure tcl/tk library environment is set for Windows
if sys.platform == "win32":
    tcl_dir = Path(sys.base_prefix) / "tcl" / "tcl8.6"
    tk_dir = Path(sys.base_prefix) / "tcl" / "tk8.6"
    if tcl_dir.exists():
        os.environ["TCL_LIBRARY"] = str(tcl_dir)
    if tk_dir.exists():
        os.environ["TK_LIBRARY"] = str(tk_dir)

from library.database import SQLiteDatabase
from tests.fixtures_helper import LocalTestServer, generate_valid_mp3_bytes


@pytest.fixture
def valid_mp3_bytes() -> bytes:
    """Deterministic valid MP3 stream bytes with ID3 tag and MPEG audio frames."""
    return generate_valid_mp3_bytes(10)


@pytest.fixture(scope="module")
def http_server():
    """Deterministic local HTTP audio socket server."""
    server = LocalTestServer()
    base_url = server.start()
    yield base_url
    server.shutdown()


@pytest.fixture
def temp_downloads_dir(tmp_path: Path) -> Path:
    """Clean temporary download directory."""
    dl = tmp_path / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    return dl


@pytest.fixture
def test_db(tmp_path: Path) -> SQLiteDatabase:
    """Fresh isolated SQLiteDatabase in tmp_path."""
    db_file = tmp_path / "test_library.db"
    db = SQLiteDatabase(db_file)
    db.connect()
    yield db
    db.close()
