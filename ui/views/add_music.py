"""
Universal URL & Playlist Import View ("ADD MUSIC").

Centerpiece acquisition interface for pasting URLs, analyzing playlists,
filtering track selections, and scheduling downloads into the canonical library.
"""

import logging
import threading
from typing import Optional, Dict, Any, List, Callable, Set
import tkinter as tk
import customtkinter as ctk

from library.models import ImportJob, ImportJobItem, ItemState, JobStatus
from ui.services.library_service import LibraryService
from ui import theme

logger = logging.getLogger(__name__)


class AddMusicView(ctk.CTkFrame):
    """
    Centerpiece Acquisition View:
    - Hero URL input with platform chips
    - Step-by-step analysis progress
    - Rich Playlist Result UI with individual track cards, checkboxes, and bulk controls
    - Selection counters and Download Selected CTA
    """

    STATE_BADGES = {
        ItemState.OWNED: ("✓ Already Downloaded", theme.SUCCESS_BG, theme.SUCCESS_LIGHT),
        ItemState.READY: ("↓ Ready to Download", theme.INFO_BG, theme.INFO_LIGHT),
        ItemState.DOWNLOADING: ("⏳ Downloading...", theme.INFO_BG, theme.INFO),
        ItemState.COMPLETED: ("✓ Downloaded", theme.SUCCESS_BG, theme.SUCCESS),
        ItemState.NEEDS_REVIEW: ("↓ Ready to Download", theme.INFO_BG, theme.INFO_LIGHT),
        ItemState.NO_SOURCE: ("⚠ Couldn't download", theme.ERROR_BG, theme.ERROR_LIGHT),
        ItemState.FAILED: ("⚠ Couldn't download", theme.ERROR_BG, theme.ERROR_LIGHT),
        ItemState.AUTH_REQUIRED: ("🔒 Auth Required", theme.SURFACE_MUTED, theme.TEXT_MUTED),
        ItemState.SKIPPED: ("⏭ Skipped", theme.SURFACE_MUTED, theme.TEXT_MUTED),
    }


    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_navigate_downloads: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.service = service
        self.on_navigate_downloads = on_navigate_downloads

        self._active_job: Optional[ImportJob] = None
        self._all_items: List[ImportJobItem] = []
        self._filtered_items: List[ImportJobItem] = []
        self._selected_item_ids: Set[int] = set()
        self._is_analyzing = False

        self._item_checkbox_vars: Dict[int, tk.BooleanVar] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct view layout."""
        # ── 1. Top Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=24, pady=12)

        ctk.CTkLabel(
            hdr_box,
            text="⚡  ADD MUSIC",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text="Universal Music & Playlist Downloader",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=16, pady=(4, 0))

        # ── 2. Centerpiece Import Area ──────────────────────────────
        import_card = ctk.CTkFrame(
            self,
            corner_radius=theme.RADIUS_LG,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        import_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(16, 12))
        import_card.grid_columnconfigure(0, weight=1)

        body = ctk.CTkFrame(import_card, fg_color="transparent")
        body.pack(fill="x", padx=24, pady=20)

        ctk.CTkLabel(
            body,
            text="Paste a song, album, playlist, or direct music link",
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            body,
            text="Supports public Spotify playlists, YouTube videos & playlists, regional Tamil sources, and direct audio streams.",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(2, 14))

        # URL Input & Analyze Button Row
        input_row = ctk.CTkFrame(body, fg_color="transparent")
        input_row.pack(fill="x")
        input_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="https://open.spotify.com/playlist/... or https://www.youtube.com/watch?v=...",
            height=48,
            font=ctk.CTkFont(size=14),
            border_color=theme.BORDER,
            fg_color=theme.SURFACE_MUTED,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_MD,
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.url_entry.bind("<Return>", lambda e: self._on_analyze_clicked())

        self.analyze_btn = ctk.CTkButton(
            input_row,
            text="⚡ Analyze URL",
            height=48,
            width=160,
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_MD,
            command=self._on_analyze_clicked,
        )
        self.analyze_btn.grid(row=0, column=1)

        # Platform Chip Badges
        chips_row = ctk.CTkFrame(body, fg_color="transparent")
        chips_row.pack(fill="x", pady=(14, 0))

        ctk.CTkLabel(
            chips_row,
            text="Supported Platforms:",
            font=theme.font_badge(),
            text_color=theme.TEXT_DIM,
        ).pack(side="left", padx=(0, 8))

        platforms = [
            ("🟢 Spotify", theme.SUCCESS),
            ("🔴 YouTube", theme.ERROR),
            ("🟡 YouTube Music", theme.WARNING),
            ("🟣 Direct Audio", theme.ACCENT_CYAN),
            ("🔵 Regional Sources", theme.SECONDARY),
        ]
        for name, color in platforms:
            chip = ctk.CTkLabel(
                chips_row,
                text=name,
                font=theme.font_badge(),
                text_color=color,
                fg_color=theme.SURFACE_ELEVATED,
                corner_radius=6,
                padx=8,
                pady=2,
            )
            chip.pack(side="left", padx=4)

        # Progress / Status feedback label
        self.status_lbl = ctk.CTkLabel(
            body,
            text="",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.status_lbl.pack(anchor="w", pady=(10, 0))

        # ── 3. Content Area: Empty State OR Playlist Result UI ──────
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)
        self.tree = self.content_container

        # Initialize Default Empty State
        self._build_empty_state()

    def _build_empty_state(self) -> None:
        """Render initial empty state with visual guidance."""
        for w in self.content_container.winfo_children():
            w.destroy()

        empty_card = ctk.CTkFrame(
            self.content_container,
            corner_radius=theme.RADIUS_LG,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        empty_card.pack(fill="both", expand=True)

        center = ctk.CTkFrame(empty_card, fg_color="transparent")
        center.place(relx=0.5, rely=0.5, anchor="center")

        icon = ctk.CTkLabel(center, text="🎧", font=ctk.CTkFont(size=48))
        icon.pack(pady=(0, 12))

        ctk.CTkLabel(
            center,
            text="No Music or Playlist Analyzed Yet",
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
        ).pack()

        ctk.CTkLabel(
            center,
            text="Paste any YouTube song or Spotify playlist link into the field above to detect tracks,\nverify audio sources, and start downloading.",
            font=theme.font_body(),
            text_color=theme.TEXT_MUTED,
            justify="center",
        ).pack(pady=(6, 18))

        examples_row = ctk.CTkFrame(center, fg_color="transparent")
        examples_row.pack()

        ex_urls = [
            ("Try Sample Spotify Link", "https://open.spotify.com/playlist/37i9dQZF1DX4gzssQ6Thw3"),
            ("Try Sample YouTube Link", "https://www.youtube.com/watch?v=kJQP7kiw5Fk"),
        ]
        for label, url_text in ex_urls:
            btn = ctk.CTkButton(
                examples_row,
                text=label,
                font=theme.font_caption_bold(),
                height=32,
                fg_color=theme.SURFACE_ELEVATED,
                hover_color=theme.SURFACE_HOVER,
                text_color=theme.PRIMARY_LIGHT,
                corner_radius=theme.RADIUS_MD,
                command=lambda u=url_text: self._set_url_and_analyze(u),
            )
            btn.pack(side="left", padx=6)

    def _set_url_and_analyze(self, url: str) -> None:
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)
        self._on_analyze_clicked()

    def _on_analyze_clicked(self) -> None:
        """Trigger URL analysis in background thread."""
        url = self.url_entry.get().strip()
        if not url:
            self.status_lbl.configure(text="⚠️ Please paste a valid music or playlist URL.", text_color=theme.WARNING)
            return

        if self._is_analyzing:
            return

        self._is_analyzing = True
        self.analyze_btn.configure(state="disabled", text="⏳ Analyzing...")
        self.status_lbl.configure(
            text="Detecting source... Contacting platform and resolving metadata...",
            text_color=theme.INFO,
        )

        def _worker():
            try:
                def _prog(msg, cur, tot):
                    self.after(0, lambda m=msg: self.status_lbl.configure(text=m))

                job, items = self.service.analyze_music_url(url, progress_cb=_prog)
                self.after(0, lambda: self._render_playlist_ui(job, items))
            except Exception as e:
                logger.error(f"Error during URL analysis: {e}", exc_info=True)
                self.after(0, lambda err=str(e): self._render_error(err))
            finally:
                self.after(0, self._reset_analyze_button)

        threading.Thread(target=_worker, daemon=True).start()

    def _reset_analyze_button(self) -> None:
        self._is_analyzing = False
        self.analyze_btn.configure(state="normal", text="⚡ Analyze URL")

    def _render_error(self, err_msg: str) -> None:
        self.status_lbl.configure(
            text=f"❌ Unable to analyze URL: {err_msg}",
            text_color=theme.ERROR,
        )

    def _render_playlist_ui(self, job: ImportJob, items: List[ImportJobItem]) -> None:
        """Render the complete, interactive Playlist Result UI."""
        self._active_job = job
        self._all_items = items
        self._filtered_items = list(items)

        # Preselect tracks that are ready or need review (unowned)
        self._selected_item_ids = {
            item.id for item in items
            if item.state in [ItemState.READY, ItemState.NEEDS_REVIEW] and item.id
        }

        self.status_lbl.configure(
            text=f"✓ Analysis complete! Found {len(items)} tracks in {job.title}",
            text_color=theme.SUCCESS,
        )

        for w in self.content_container.winfo_children():
            w.destroy()

        result_card = ctk.CTkFrame(
            self.content_container,
            corner_radius=theme.RADIUS_LG,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        result_card.pack(fill="both", expand=True)
        result_card.grid_columnconfigure(0, weight=1)
        result_card.grid_rowconfigure(2, weight=1)

        # ── A. Playlist Metadata Header ─────────────────────────────
        meta_header = ctk.CTkFrame(result_card, fg_color="transparent")
        meta_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 12))
        meta_header.grid_columnconfigure(1, weight=1)

        # Art / Platform Badge
        art_box = ctk.CTkFrame(
            meta_header,
            width=58,
            height=58,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE_ELEVATED,
        )
        art_box.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="w")
        art_box.pack_propagate(False)
        p_icon = "🟢" if "spotify" in job.platform.lower() else "🔴" if "youtube" in job.platform.lower() else "🎵"
        ctk.CTkLabel(art_box, text=p_icon, font=ctk.CTkFont(size=26)).pack(expand=True)

        # Title & Counts
        title_text = f"{job.title} ({job.platform.capitalize()} {job.content_type.capitalize()})"
        ctk.CTkLabel(
            meta_header,
            text=title_text,
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        owned_cnt = sum(1 for i in items if i.state in (ItemState.OWNED, ItemState.COMPLETED))
        ready_cnt = sum(1 for i in items if i.state in (ItemState.READY, ItemState.NEEDS_REVIEW))
        failed_cnt = sum(1 for i in items if i.state in (ItemState.FAILED, ItemState.NO_SOURCE))

        stats_parts = [f"📊 {len(items)} songs found"]
        if owned_cnt > 0:
            stats_parts.append(f"✓ {owned_cnt} already downloaded")
        if ready_cnt > 0:
            stats_parts.append(f"↓ {ready_cnt} ready to download")
        if failed_cnt > 0:
            stats_parts.append(f"⚠ {failed_cnt} couldn't download")

        stats_str = "  ·  ".join(stats_parts)
        ctk.CTkLabel(
            meta_header,
            text=stats_str,
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_SECONDARY,
            anchor="w",
        ).grid(row=1, column=1, sticky="w", pady=(2, 0))


        # ── B. Selection & Filter Toolbar ───────────────────────────
        toolbar = ctk.CTkFrame(result_card, fg_color=theme.SURFACE_ELEVATED, corner_radius=theme.RADIUS_MD)
        toolbar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        tb_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        tb_inner.pack(fill="x", padx=12, pady=8)

        # Selection buttons
        ctk.CTkButton(
            tb_inner,
            text="Select All",
            font=theme.font_caption_bold(),
            height=28,
            width=80,
            fg_color=theme.SURFACE,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            command=self._select_all_items,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            tb_inner,
            text="Select None",
            font=theme.font_caption_bold(),
            height=28,
            width=85,
            fg_color=theme.SURFACE,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            command=self._select_no_items,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            tb_inner,
            text="Invert",
            font=theme.font_caption_bold(),
            height=28,
            width=65,
            fg_color=theme.SURFACE,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            command=self._invert_selection,
        ).pack(side="left", padx=4)

        # Search filter
        self.search_entry = ctk.CTkEntry(
            tb_inner,
            placeholder_text="Filter tracks by title/artist...",
            height=28,
            width=220,
            font=theme.font_caption(),
            fg_color=theme.SURFACE_MUTED,
            border_color=theme.BORDER,
        )
        self.search_entry.pack(side="left", padx=12)
        self.search_entry.bind("<KeyRelease>", lambda e: self._apply_filters())

        # State filter dropdown
        self.filter_var = tk.StringVar(value="All Tracks")
        filter_opt = ctk.CTkOptionMenu(
            tb_inner,
            values=["All Tracks", "Ready to Download", "Already Downloaded", "Couldn't Download"],
            variable=self.filter_var,
            font=theme.font_caption(),
            height=28,
            width=165,
            fg_color=theme.SURFACE,
            button_color=theme.SURFACE_HOVER,
            command=lambda e: self._apply_filters(),
        )
        filter_opt.pack(side="left", padx=4)


        # ── C. Interactive Track Rows (Scrollable) ───────────────────
        self.track_scroll = ctk.CTkScrollableFrame(
            result_card,
            fg_color="transparent",
            corner_radius=0,
        )
        self.track_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.track_scroll.grid_columnconfigure(0, weight=1)

        # ── D. Sticky Bottom Action Footer ───────────────────────────
        footer = ctk.CTkFrame(result_card, height=54, fg_color=theme.BG_HEADER, corner_radius=theme.RADIUS_MD)
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))
        footer.grid_propagate(False)

        self.selected_count_lbl = ctk.CTkLabel(
            footer,
            text="",
            font=theme.font_body_bold(),
            text_color=theme.TEXT_PRIMARY,
        )
        self.selected_count_lbl.pack(side="left", padx=20)

        self.dl_selected_btn = ctk.CTkButton(
            footer,
            text="📥 Download Selected Tracks",
            font=theme.font_body_bold(),
            height=38,
            width=220,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_BG,
            text_color=theme.TEXT_PRIMARY,
            command=self._on_download_selected,
        )
        self.dl_selected_btn.pack(side="right", padx=16, pady=8)

        self._render_track_rows()
        self._update_selection_counter()

    def _render_track_rows(self) -> None:
        """Render track row cards for filtered items."""
        for w in self.track_scroll.winfo_children():
            w.destroy()

        self._item_checkbox_vars.clear()

        for idx, item in enumerate(self._filtered_items):
            row_card = ctk.CTkFrame(
                self.track_scroll,
                fg_color=theme.SURFACE_ELEVATED,
                corner_radius=theme.RADIUS_SM,
                border_width=1,
                border_color=theme.BORDER,
            )
            row_card.pack(fill="x", pady=3)

            inner = ctk.CTkFrame(row_card, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=8)

            # Checkbox
            var = tk.BooleanVar(value=(item.id in self._selected_item_ids))
            self._item_checkbox_vars[item.id] = var

            cb = ctk.CTkCheckBox(
                inner,
                text="",
                variable=var,
                width=24,
                checkbox_width=20,
                checkbox_height=20,
                corner_radius=4,
                border_color=theme.BORDER_LIGHT,
                fg_color=theme.PRIMARY,
                command=lambda i=item.id, v=var: self._on_item_toggled(i, v),
            )
            cb.pack(side="left", padx=(0, 10))

            # Track number
            ctk.CTkLabel(
                inner,
                text=f"{item.track_index:02d}",
                font=theme.font_caption_bold(),
                text_color=theme.TEXT_DIM,
                width=24,
                anchor="center",
            ).pack(side="left", padx=(0, 10))

            # Title & Artist
            info_box = ctk.CTkFrame(inner, fg_color="transparent")
            info_box.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(
                info_box,
                text=item.title,
                font=theme.font_body_bold(),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            ).pack(anchor="w")

            dur_str = f"{item.duration_seconds // 60}:{item.duration_seconds % 60:02d}" if item.duration_seconds else "--:--"
            meta_str = f"{item.artist or 'Unknown Artist'}  ·  {dur_str}"
            ctk.CTkLabel(
                info_box,
                text=meta_str,
                font=theme.font_caption(),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w")

            # State Pill
            label, bg_col, text_col = self.STATE_BADGES.get(
                item.state,
                (item.state.value, theme.SURFACE_MUTED, theme.TEXT_MUTED)
            )
            state_pill = ctk.CTkLabel(
                inner,
                text=label,
                font=theme.font_badge(),
                fg_color=bg_col,
                text_color=text_col,
                corner_radius=8,
                padx=10,
                pady=4,
            )
            state_pill.pack(side="right", padx=(8, 0))


    def _on_item_toggled(self, item_id: int, var: tk.BooleanVar) -> None:
        if var.get():
            self._selected_item_ids.add(item_id)
        else:
            self._selected_item_ids.discard(item_id)
        self._update_selection_counter()

    def _update_selection_counter(self) -> None:
        sel_count = len(self._selected_item_ids)
        total_count = len(self._all_items)
        self.selected_count_lbl.configure(
            text=f"Selected: {sel_count} of {total_count} tracks"
        )
        self.dl_selected_btn.configure(
            text=f"📥 Download Selected ({sel_count})",
            state="normal" if sel_count > 0 else "disabled",
        )

    def _select_all_items(self) -> None:
        for item in self._all_items:
            self._selected_item_ids.add(item.id)
            if item.id in self._item_checkbox_vars:
                self._item_checkbox_vars[item.id].set(True)
        self._update_selection_counter()

    def _select_no_items(self) -> None:
        self._selected_item_ids.clear()
        for var in self._item_checkbox_vars.values():
            var.set(False)
        self._update_selection_counter()

    def _invert_selection(self) -> None:
        for item in self._all_items:
            if item.id in self._selected_item_ids:
                self._selected_item_ids.remove(item.id)
                if item.id in self._item_checkbox_vars:
                    self._item_checkbox_vars[item.id].set(False)
            else:
                self._selected_item_ids.add(item.id)
                if item.id in self._item_checkbox_vars:
                    self._item_checkbox_vars[item.id].set(True)
        self._update_selection_counter()

    def _apply_filters(self) -> None:
        query = self.search_entry.get().strip().lower()
        filter_mode = self.filter_var.get()

        filtered = []
        for item in self._all_items:
            # Query match
            if query and (query not in item.title.lower() and query not in (item.artist or "").lower()):
                continue

            # State match
            if filter_mode == "Ready to Download" and item.state not in (ItemState.READY, ItemState.NEEDS_REVIEW):
                continue
            elif filter_mode == "Already Downloaded" and item.state not in (ItemState.OWNED, ItemState.COMPLETED):
                continue
            elif filter_mode == "Couldn't Download" and item.state not in [ItemState.NO_SOURCE, ItemState.FAILED]:
                continue


            filtered.append(item)

        self._filtered_items = filtered
        self._render_track_rows()

    def _on_download_selected(self) -> None:
        """Start downloading only the checked tracks."""
        if not self._active_job or not self._selected_item_ids:
            return

        selected_ids = list(self._selected_item_ids)
        self.service.execute_import_job(
            job_id=self._active_job.id,
            item_ids=selected_ids,
            run_async=True,
        )

        self.status_lbl.configure(
            text=f"🚀 Downloading {len(selected_ids)} selected tracks into your library...",
            text_color=theme.SUCCESS,
        )

        if self.on_navigate_downloads:
            self.on_navigate_downloads()

    def refresh(self) -> None:
        """Refresh active job state if one is loaded."""
        if self._active_job:
            items = self.service.get_import_job_items(self._active_job.id)
            if items:
                self._render_playlist_ui(self._active_job, items)
