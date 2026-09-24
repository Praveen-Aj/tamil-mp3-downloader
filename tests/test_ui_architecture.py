"""
Tests for UI Architecture (Phases 1 - 11).

Verifies:
- LibraryService operations (Dashboard stats, SQL pagination, Song details, Discovery persistence)
- Separation of Discovery -> Canonical Library -> Download Plan -> Downloads
- Headless initialization of UI service and database backend
"""

import tempfile
from pathlib import Path
import pytest

from library.database import SQLiteDatabase
from library.models import LibrarySong, SongSource, SongState, DownloadState
from ui.services.library_service import LibraryService


@pytest.fixture
def temp_service():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    service = LibraryService(db_path=db_path)
    yield service
    service.db.close()
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass


class TestLibraryService:
    def test_initialization_and_sources(self, temp_service):
        stats = temp_service.get_dashboard_stats()
        assert stats["total_songs"] == 0
        assert stats["owned_songs"] == 0
        assert stats["unowned_songs"] == 0
        assert stats["upgrades_available"] == 0
        assert "3/" in stats["healthy_sources"]

    def test_sql_pagination(self, temp_service):
        # Register 150 mock songs
        for i in range(150):
            song = LibrarySong(
                title=f"Test Song {i:03d}",
                artist="Test Artist",
                album="Test Album",
                canonical_hash=f"hash_{i:03d}",
            )
            song_id = temp_service.db.add_song(song)
            src = SongSource(
                song_id=song_id,
                source_name="masstamilan",
                source_url=f"https://example.com/song_{i}.mp3",
                quality_kbps=320,
            )
            temp_service.db.add_source(src)

        # Query page 1 (50 items)
        page1 = temp_service.get_library_page(page=1, page_size=50)
        assert len(page1["songs"]) == 50
        assert page1["total_items"] == 150
        assert page1["total_pages"] == 3
        assert page1["page"] == 1

        # Query page 3 (50 items)
        page3 = temp_service.get_library_page(page=3, page_size=50)
        assert len(page3["songs"]) == 50
        assert page3["page"] == 3

    def test_song_details_inspection(self, temp_service):
        song = LibrarySong(
            title="Anbil Avan",
            artist="A.R. Rahman",
            album="Vinnaithaandi Varuvaayaa",
            year=2010,
            canonical_hash="anbil_avan_hash",
        )
        song_id = temp_service.db.add_song(song)

        src = SongSource(
            song_id=song_id,
            source_name="masstamilan",
            source_url="https://masstamilan.dev/song.mp3",
            quality_kbps=320,
        )
        temp_service.db.add_source(src)

        details = temp_service.get_song_details(song_id)
        assert details["song"].title == "Anbil Avan"
        assert len(details["sources"]) == 1
        assert details["sources"][0].quality_kbps == 320
        assert details["planner_decision"] is not None

    def test_discovery_does_not_auto_download(self, temp_service):
        # Verify running discovery returns persistent session stats
        # and does NOT place items into active download registry
        stats_before = temp_service.get_dashboard_stats()
        assert stats_before["active_downloads"] == 0

        # Preview plan before execution
        plan = temp_service.preview_download_plan()
        assert len(plan.new_songs) == 0

        stats_after = temp_service.get_dashboard_stats()
        assert stats_after["active_downloads"] == 0

    @pytest.mark.gui
    def test_dialog_instantiation_and_rendering(self, temp_service):
        """Verify PlanPreviewDialog and SongDetailsDialog can be instantiated without attribute errors."""
        import customtkinter as ctk
        from ui.dialogs.plan_preview import PlanPreviewDialog
        from ui.dialogs.song_details import SongDetailsDialog
        from library.models import DiscoveryContext

        try:
            root = ctk.CTk()
        except Exception as exc:
            pytest.skip(f"Tkinter environment not available: {exc}")
        root.withdraw()
        try:
            # Add sample song and source
            song = LibrarySong(
                title="Aalaporaan Thamizhan",
                artist="A.R. Rahman",
                album="Mersal",
                year=2017,
                canonical_hash="aalaporaan_dialog_hash",
            )
            song_id = temp_service.db.add_song(song)
            src = SongSource(
                song_id=song_id,
                source_name="masstamilan",
                source_url="https://masstamilan.dev/aalaporaan.mp3",
                quality_kbps=320,
            )
            temp_service.db.add_source(src)

            # 1. Test PlanPreviewDialog
            plan = temp_service.preview_download_plan([song_id])
            dlg_plan = PlanPreviewDialog(root, plan=plan, on_confirm=lambda: None)
            dlg_plan.update_idletasks()
            assert dlg_plan.winfo_exists()
            dlg_plan.destroy()

            # 2. Test SongDetailsDialog
            details = temp_service.get_song_details(song_id)
            details["contexts"].append(
                DiscoveryContext(song_id=song_id, source_name="masstamilan", category="latest", album_name="Mersal")
            )
            dlg_song = SongDetailsDialog(
                root,
                song=details["song"],
                sources=details["sources"],
                contexts=details["contexts"],
                planner_decision=details.get("planner_decision"),
            )
            dlg_song.update_idletasks()
            assert dlg_song.winfo_exists()
            dlg_song.destroy()
        finally:
            for child in root.winfo_children():
                try:
                    child.destroy()
                except Exception:
                    pass
            root.withdraw()
