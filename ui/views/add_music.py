"""
Universal URL & Playlist Import View ("ADD MUSIC").
Primary acquisition interface for pasting URLs, analyzing playlists,
evaluating match confidence, and planning downloads.
"""

import logging
import threading
from tkinter import ttk
from typing import Optional, Dict, Any, List, Callable
import customtkinter as ctk

from library.models import ImportJob, ImportJobItem, ItemState, JobStatus
from ui.services.library_service import LibraryService

logger = logging.getLogger(__name__)


class AddMusicView(ctk.CTkFrame):
    """
    Primary Add Music view providing Universal URL analysis,
    multi-factor candidate matching, and playlist plan review.
    """

    STATE_COLORS = {
        ItemState.OWNED: ("#065f46", "#34d399"),          # Green
        ItemState.READY: ("#1e3a8a", "#60a5fa"),          # Blue
        ItemState.DOWNLOADING: ("#075985", "#38bdf8"),    # Sky
        ItemState.COMPLETED: ("#065f46", "#10b981"),      # Emerald
        ItemState.NEEDS_REVIEW: ("#78350f", "#fbbf24"),   # Amber
        ItemState.NO_SOURCE: ("#881337", "#f87171"),      # Red
        ItemState.FAILED: ("#7f1d1d", "#ef4444"),         # Rose
        ItemState.AUTH_REQUIRED: ("#581c87", "#c084fc"),  # Purple
        ItemState.SKIPPED: ("#374151", "#9ca3af"),        # Gray
    }

    def __init__(
        self,
        master: ctk.CTkFrame,
        service: LibraryService,
        on_navigate_downloads: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.service = service
        self.on_navigate_downloads = on_navigate_downloads

        self._active_job: Optional[ImportJob] = None
        self._active_items: List[ImportJobItem] = []
        self._is_analyzing = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct view layout."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── 1. Top Header ───────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=25, pady=(20, 10))

        title = ctk.CTkLabel(
            header_frame,
            text="➕ ADD MUSIC",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=("gray10", "#f3f4f6"),
        )
        title.pack(side="left")

        subtitle = ctk.CTkLabel(
            header_frame,
            text="Paste a song, album, or playlist URL to analyze and download.",
            font=ctk.CTkFont(size=13),
            text_color=("gray50", "#9ca3af"),
        )
        subtitle.pack(side="left", padx=15, pady=(4, 0))

        # ── 2. URL Input Card ────────────────────────────────────────
        input_card = ctk.CTkFrame(self, fg_color=("gray90", "#181824"), corner_radius=12)
        input_card.grid(row=1, column=0, sticky="ew", padx=25, pady=10)
        input_card.grid_columnconfigure(0, weight=1)

        input_row = ctk.CTkFrame(input_card, fg_color="transparent")
        input_row.pack(fill="x", padx=20, pady=(18, 12))
        input_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="Paste a song, album, playlist, or supported music URL...",
            height=44,
            font=ctk.CTkFont(size=14),
            border_color=("gray70", "#2d2d3f"),
            fg_color=("white", "#1e1e2d"),
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.url_entry.bind("<Return>", lambda e: self._on_analyze_clicked())

        self.analyze_btn = ctk.CTkButton(
            input_row,
            text="⚡ Analyze URL",
            height=44,
            width=150,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#6366f1",
            hover_color="#4f46e5",
            command=self._on_analyze_clicked,
        )
        self.analyze_btn.grid(row=0, column=1)

        # Platform badges pill row
        badge_row = ctk.CTkFrame(input_card, fg_color="transparent")
        badge_row.pack(fill="x", padx=20, pady=(0, 15))

        lbl_sup = ctk.CTkLabel(
            badge_row,
            text="Supported Platforms:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray50", "#9ca3af"),
        )
        lbl_sup.pack(side="left", padx=(0, 8))

        platforms = [
            ("🟢 Spotify", "#10b981"),
            ("🟢 YouTube", "#ef4444"),
            ("🟢 YouTube Music", "#f59e0b"),
            ("🟢 Tamil Music Sources", "#6366f1"),
            ("🟢 Direct Audio Links", "#06b6d4"),
        ]
        for name, color in platforms:
            pill = ctk.CTkLabel(
                badge_row,
                text=name,
                font=ctk.CTkFont(size=11),
                text_color=color,
            )
            pill.pack(side="left", padx=6)

        # Progress / Status label
        self.status_lbl = ctk.CTkLabel(
            input_card,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "#a1a1aa"),
        )
        self.status_lbl.pack(anchor="w", padx=20, pady=(0, 12))

        # ── 3. Content / Analysis Body ──────────────────────────────
        self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.body_frame.grid(row=2, column=0, sticky="nsew", padx=25, pady=(10, 20))
        self.body_frame.grid_columnconfigure(0, weight=1)
        self.body_frame.grid_rowconfigure(1, weight=1)

        # Overview Analysis Card
        self.overview_card = ctk.CTkFrame(self.body_frame, fg_color=("gray90", "#181824"), corner_radius=12)
        self.overview_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.overview_card.grid_columnconfigure(1, weight=1)
        self.overview_card.grid_remove()  # Hidden until analysis finishes

        # Thumbnail / Icon
        self.art_label = ctk.CTkLabel(
            self.overview_card,
            text="🎵",
            font=ctk.CTkFont(size=40),
            width=70,
            height=70,
            fg_color=("gray80", "#262638"),
            corner_radius=8,
        )
        self.art_label.grid(row=0, column=0, rowspan=2, padx=15, pady=15)

        # Info column
        self.info_title = ctk.CTkLabel(
            self.overview_card,
            text="",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        )
        self.info_title.grid(row=0, column=1, sticky="w", padx=10, pady=(15, 2))

        self.info_stats = ctk.CTkLabel(
            self.overview_card,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=("gray50", "#9ca3af"),
            anchor="w",
        )
        self.info_stats.grid(row=1, column=1, sticky="w", padx=10, pady=(0, 15))

        # Actions column
        self.actions_box = ctk.CTkFrame(self.overview_card, fg_color="transparent")
        self.actions_box.grid(row=0, column=2, rowspan=2, padx=15, pady=15, sticky="e")

        self.dl_ready_btn = ctk.CTkButton(
            self.actions_box,
            text="📥 Download Ready Tracks",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=38,
            command=self._on_download_ready,
        )
        self.dl_ready_btn.pack(side="top", pady=2)

        self.retry_btn = ctk.CTkButton(
            self.actions_box,
            text="🔄 Retry Failed Only",
            font=ctk.CTkFont(size=12),
            fg_color=("gray75", "#2a2a3c"),
            hover_color=("gray65", "#3f3f5a"),
            height=32,
            command=self._on_retry_failed,
        )
        self.retry_btn.pack(side="top", pady=4)

        # ── 4. Track List Table ──────────────────────────────────────
        table_container = ctk.CTkFrame(self.body_frame, fg_color=("gray95", "#181824"), corner_radius=12)
        table_container.grid(row=1, column=0, sticky="nsew")
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        columns = ("#", "title", "artist", "duration", "provider", "match", "status")
        self.tree = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("#", text="#")
        self.tree.heading("title", text="Track Title")
        self.tree.heading("artist", text="Artist / Uploader")
        self.tree.heading("duration", text="Duration")
        self.tree.heading("provider", text="Audio Source")
        self.tree.heading("match", text="Confidence")
        self.tree.heading("status", text="Status")

        self.tree.column("#", width=45, anchor="center")
        self.tree.column("title", width=280, anchor="w")
        self.tree.column("artist", width=180, anchor="w")
        self.tree.column("duration", width=80, anchor="center")
        self.tree.column("provider", width=140, anchor="center")
        self.tree.column("match", width=110, anchor="center")
        self.tree.column("status", width=120, anchor="center")

        scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=10)

        # Configure style
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#1e1e2d",
            foreground="#e4e4e7",
            fieldbackground="#1e1e2d",
            rowheight=32,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background="#181824",
            foreground="#a1a1aa",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#3b82f6")])

    def _on_analyze_clicked(self) -> None:
        """Trigger URL analysis in background thread."""
        url = self.url_entry.get().strip()
        if not url:
            self.status_lbl.configure(text="⚠️ Please paste a valid URL.", text_color="#fbbf24")
            return

        if self._is_analyzing:
            return

        self._is_analyzing = True
        self.analyze_btn.configure(state="disabled", text="⏳ Analyzing...")
        self.status_lbl.configure(text="Connecting to platform and resolving tracklist...", text_color="#60a5fa")

        def _worker():
            try:
                def _prog(msg, cur, tot):
                    self.after(0, lambda m=msg: self.status_lbl.configure(text=m))

                job, items = self.service.analyze_music_url(url, progress_cb=_prog)
                self.after(0, lambda: self._render_analysis(job, items))
            except Exception as e:
                logger.error(f"Error during analysis: {e}", exc_info=True)
                self.after(0, lambda err=str(e): self._render_error(err))
            finally:
                self.after(0, self._reset_analyze_button)

        threading.Thread(target=_worker, daemon=True).start()

    def _reset_analyze_button(self) -> None:
        self._is_analyzing = False
        self.analyze_btn.configure(state="normal", text="⚡ Analyze URL")

    def _render_error(self, err_msg: str) -> None:
        self.status_lbl.configure(
            text=f"❌ Analysis failed: {err_msg}",
            text_color="#ef4444",
        )

    def _render_analysis(self, job: ImportJob, items: List[ImportJobItem]) -> None:
        """Render resolved playlist and track breakdown."""
        self._active_job = job
        self._active_items = items

        # Populate summary card
        self.overview_card.grid()
        self.info_title.configure(text=f"{job.platform} {job.content_type}: {job.title}")

        owned_cnt = sum(1 for i in items if i.state == ItemState.OWNED)
        ready_cnt = sum(1 for i in items if i.state == ItemState.READY)
        review_cnt = sum(1 for i in items if i.state == ItemState.NEEDS_REVIEW)
        no_src_cnt = sum(1 for i in items if i.state == ItemState.NO_SOURCE)
        failed_cnt = sum(1 for i in items if i.state == ItemState.FAILED)

        summary_text = (
            f"📊 {len(items)} tracks total  •  "
            f"✓ {owned_cnt} in library  •  "
            f"✓ {ready_cnt} ready to download  •  "
            f"⚠ {review_cnt} need review  •  "
            f"✕ {no_src_cnt + failed_cnt} unavailable"
        )
        self.info_stats.configure(text=summary_text)
        self.status_lbl.configure(text=f"Analysis complete for: {job.title}", text_color="#10b981")

        # Update button text
        self.dl_ready_btn.configure(text=f"📥 Download {ready_cnt} Ready Tracks")

        # Populate table
        for r in self.tree.get_children():
            self.tree.delete(r)

        for item in items:
            dur_str = f"{item.duration_seconds // 60}:{item.duration_seconds % 60:02d}" if item.duration_seconds else "--:--"
            conf_str = f"{int(item.match_confidence * 100)}%" if item.match_confidence else "--"
            self.tree.insert(
                "",
                "end",
                iid=str(item.id or item.track_index),
                values=(
                    item.track_index,
                    item.title,
                    item.artist or "--",
                    dur_str,
                    item.selected_provider or "--",
                    conf_str,
                    item.state.value,
                ),
            )

    def _on_download_ready(self) -> None:
        """Start downloading ready tracks."""
        if not self._active_job or not self._active_items:
            return

        ready_ids = [i.id for i in self._active_items if i.state in [ItemState.READY, ItemState.NEEDS_REVIEW] and i.id]
        if not ready_ids:
            self.status_lbl.configure(text="No tracks ready for download.", text_color="#fbbf24")
            return

        self.service.execute_import_job(
            job_id=self._active_job.id,
            item_ids=ready_ids,
            run_async=True,
        )

        self.status_lbl.configure(
            text=f"🚀 Started downloading {len(ready_ids)} tracks into your library.",
            text_color="#10b981",
        )

        if self.on_navigate_downloads:
            self.on_navigate_downloads()

    def _on_retry_failed(self) -> None:
        """Re-attempt downloading only failed tracks."""
        if not self._active_job:
            return

        failed_items = [i for i in self._active_items if i.state == ItemState.FAILED and i.id]
        if not failed_items:
            self.status_lbl.configure(text="No failed tracks to retry.", text_color="#60a5fa")
            return

        self.service.execute_import_job(
            job_id=self._active_job.id,
            item_ids=[i.id for i in failed_items],
            run_async=True,
        )
        self.status_lbl.configure(
            text=f"🔄 Retrying {len(failed_items)} failed tracks...",
            text_color="#60a5fa",
        )

    def refresh(self) -> None:
        """Refresh active job status if one is currently active."""
        if self._active_job:
            items = self.service.get_import_job_items(self._active_job.id)
            if items:
                self._render_analysis(self._active_job, items)
