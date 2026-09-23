"""GUI tests for CustomTkinter application instantiation and navigation."""

from pathlib import Path
import pytest
import customtkinter as ctk

from library.database import SQLiteDatabase
from ui.services.library_service import LibraryService
from ui.app import TamilMP3App


@pytest.mark.gui
def test_app_startup_and_navigation(tmp_path: Path):
    """Test full application instance creation, view mounting, and tab navigation."""
    db_path = tmp_path / "gui_test.db"
    db = SQLiteDatabase(db_path)
    db.connect()
    service = LibraryService(db=db, download_dir=str(tmp_path / "downloads"))

    # Instantiate App
    app = TamilMP3App(service=service)
    app.update()

    assert app.winfo_exists()
    assert app.current_view_name == "dashboard"

    # Navigate to Add Music view
    app.navigate_to("add_music")
    app.update()
    assert app.current_view_name == "add_music"

    # Navigate to Downloaded Songs view
    app.navigate_to("downloaded_songs")
    app.update()
    assert app.current_view_name == "downloaded_songs"

    # Navigate to Settings view
    app.navigate_to("settings")
    app.update()
    assert app.current_view_name == "settings"

    # Navigate to Help view
    app.navigate_to("help")
    app.update()
    assert app.current_view_name == "help"

    try:
        app.destroy()
    except Exception:
        pass
