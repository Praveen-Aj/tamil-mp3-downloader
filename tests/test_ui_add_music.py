"""
Unit tests for modernized UI views: AddMusicView, HelpView, DashboardView, DownloadsView.
"""

from pathlib import Path
import pytest
import customtkinter as ctk

from library.database import SQLiteDatabase
from ui.services.library_service import LibraryService
from ui.views.add_music import AddMusicView
from ui.views.help_view import HelpView
from ui.views.dashboard import DashboardView
from ui.views.downloads import DownloadsView


@pytest.fixture
def service(tmp_path):
    db_file = tmp_path / "test_ui_views.db"
    svc = LibraryService(db_path=db_file)
    yield svc
    svc.db.close()


@pytest.fixture
def tk_root():
    try:
        root = ctk.CTk()
        root.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter GUI environment not available: {e}")
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_add_music_view_instantiation(tk_root, service):
    view = AddMusicView(tk_root, service=service)
    assert view.url_entry is not None
    assert view.analyze_btn is not None
    assert view.tree is not None


def test_help_view_instantiation(tk_root):
    view = HelpView(tk_root)
    assert len(view.HELP_SECTIONS) >= 5


def test_dashboard_view_instantiation(tk_root, service):
    view = DashboardView(tk_root, service=service, on_navigate=lambda _: None)
    assert "total_songs" in view._card_vars
    assert "owned_songs" in view._card_vars
    assert "failed_downloads" in view._card_vars


def test_downloads_view_instantiation(tk_root, service):
    view = DownloadsView(tk_root, service=service)
    assert view.scroll is not None
    assert view.progress_bar is not None


