"""
Chart Detail View for Curated Charts & Top 100.

Provides:
- Hero header with chart metadata and snapshot date
- Authoritative metrics chips: Total Tracks, Downloaded, Missing
- Bulk download controls: "Download Missing" and "Download All" via canonical pipeline
- Ranked track table with trend indicators (▲, ▼, NEW, ＝)
- Clickable chips navigating to ArtistDetailView and MovieDetailView
- Per-row "Play" (for downloaded songs) or "Download" buttons
- Real-time download progress tracking
- Local in-chart search & filtering
"""

import os
import threading
from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from ui.services.library_service import LibraryService, DownloadProgressEvent
from ui import theme


class ChartDetailView(ctk.CTkFrame):
    """
    Detailed Ranked Tracklist View for a Curated Chart.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_back: Callable[[], None],
        on_open_artist: Optional[Callable[[int], None]] = None,
        on_open_movie: Optional[Callable[[int], None]] = None,
        on_start_downloads: Optional[Callable[[List[int]], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_APP, corner_radius=0, **kwargs)
        self.service = service
        self.on_back = on_back
        self.on_open_artist = on_open_artist
        self.on_open_movie = on_open_movie
        self.on_start_downloads = on_start_downloads

        self.chart_id: Optional[str] = None
        self._chart_data: Optional[Dict[str, Any]] = None
        self._current_entries: List[Dict[str, Any]] = []
        self.search_query: str = ""
        self.current_page: int = 1
        self.page_size: int = 50
        self._total_matching: int = 0
        self._search_debounce_id: Optional[str] = None

        self._progress_bars: Dict[int, ctk.CTkProgressBar] = {}
        self._status_labels: Dict[int, ctk.CTkLabel] = {}
        self._action_buttons: Dict[int, ctk.CTkButton] = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header Banner ─────────────────────────────────────
        self.header_frame = ctk.CTkFrame(self, fg_color=theme.BG_HEADER, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="ew")

        # Back button row
        top_bar = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=(12, 6))

        back_btn = ctk.CTkButton(
            top_bar,
            text="← Back to Charts",
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_CARD,
            hover_color=theme.PRIMARY_MUTED,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            width=130,
            height=30,
            command=self.on_back,
        )
        back_btn.pack(side="left")

        # Hero content row
        hero_box = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        hero_box.pack(fill="x", padx=20, pady=(6, 16))

        # Avatar Icon
        self.avatar_label = ctk.CTkLabel(
            hero_box,
            text="🏆",
            font=ctk.CTkFont(size=44),
            width=64,
            height=64,
            fg_color=theme.PRIMARY_MUTED,
            corner_radius=theme.RADIUS_MD,
        )
        self.avatar_label.pack(side="left", padx=(0, 16))

        # Title & Meta Info
        meta_box = ctk.CTkFrame(hero_box, fg_color="transparent")
        meta_box.pack(side="left", fill="both", expand=True)

        self.title_label = ctk.CTkLabel(
            meta_box,
            text="Curated Chart",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            meta_box,
            text="Provider • Snapshot",
            font=theme.font_body(),
            text_color=theme.PRIMARY_LIGHT,
            anchor="w",
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 4))

        # Action Buttons & Metric Chips Box
        actions_box = ctk.CTkFrame(hero_box, fg_color="transparent")
        actions_box.pack(side="right", padx=(10, 0))

        # Metrics Pills Frame
        self.stats_chips_box = ctk.CTkFrame(actions_box, fg_color="transparent")
        self.stats_chips_box.pack(anchor="e", pady=(0, 8))

        # Download Buttons Frame
        btn_box = ctk.CTkFrame(actions_box, fg_color="transparent")
        btn_box.pack(anchor="e")

        self.dl_missing_btn = ctk.CTkButton(
            btn_box,
            text="⬇ Download Missing",
            font=theme.font_button(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_DARK,
            height=34,
            width=150,
            command=self._on_download_missing_clicked,
        )
        self.dl_missing_btn.pack(side="right", padx=(8, 0))

        self.dl_all_btn = ctk.CTkButton(
            btn_box,
            text="⚡ Download All",
            font=theme.font_button(),
            fg_color=theme.SURFACE_CARD,
            hover_color=theme.PRIMARY_MUTED,
            text_color=theme.TEXT_PRIMARY,
            height=34,
            width=120,
            command=self._on_download_all_clicked,
        )
        self.dl_all_btn.pack(side="right")

        # ── 2. Filter & Search Toolbar ───────────────────────────────
        filter_toolbar = ctk.CTkFrame(self, height=44, fg_color=theme.BG_SIDEBAR, corner_radius=0)
        filter_toolbar.grid(row=1, column=0, sticky="ew")
        filter_toolbar.grid_propagate(False)

        self.results_count_lbl = ctk.CTkLabel(
            filter_toolbar,
            text="Showing 0 tracks",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        )
        self.results_count_lbl.pack(side="left", padx=20, pady=10)

        search_container = ctk.CTkFrame(filter_toolbar, fg_color="transparent")
        search_container.pack(side="right", padx=20, pady=6)

        self.search_entry = ctk.CTkEntry(
            search_container,
            placeholder_text="Filter tracks by title, artist, or movie...",
            font=theme.font_body(),
            width=260,
            height=30,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        # ── 3. Scrollable Tracklist Table ────────────────────────────
        self.table_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.table_scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 5))
        self.grid_rowconfigure(2, weight=1)

        # Column layout for ranked table
        self.table_scroll.grid_columnconfigure(0, weight=0, minsize=45)   # Rank
        self.table_scroll.grid_columnconfigure(1, weight=0, minsize=55)   # Trend
        self.table_scroll.grid_columnconfigure(2, weight=3, minsize=180)  # Title
        self.table_scroll.grid_columnconfigure(3, weight=2, minsize=140)  # Artist
        self.table_scroll.grid_columnconfigure(4, weight=2, minsize=130)  # Movie / Album
        self.table_scroll.grid_columnconfigure(5, weight=1, minsize=110)  # Status
        self.table_scroll.grid_columnconfigure(6, weight=0, minsize=100)  # Action

        # ── 4. Bottom Pagination Bar ─────────────────────────────────
        self.pagination_bar = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color=theme.BG_HEADER)
        self.pagination_bar.grid(row=3, column=0, sticky="ew")
        self.pagination_bar.grid_propagate(False)

        self.page_lbl = ctk.CTkLabel(
            self.pagination_bar, text="", font=theme.font_caption(), text_color=theme.TEXT_MUTED
        )
        self.page_lbl.pack(side="left", padx=20, pady=10)

        nav_box = ctk.CTkFrame(self.pagination_bar, fg_color="transparent")
        nav_box.pack(side="right", padx=20, pady=6)

        self.prev_btn = ctk.CTkButton(
            nav_box, text="‹ Prev", width=60, height=26, font=theme.font_caption(),
            fg_color=theme.SURFACE_CARD, command=lambda: self._go_page(self.current_page - 1)
        )
        self.prev_btn.pack(side="left", padx=2)

        self.page_indicator = ctk.CTkLabel(
            nav_box, text="1", font=theme.font_caption_bold(), width=40, text_color=theme.TEXT_PRIMARY
        )
        self.page_indicator.pack(side="left", padx=4)

        self.next_btn = ctk.CTkButton(
            nav_box, text="Next ›", width=60, height=26, font=theme.font_caption(),
            fg_color=theme.SURFACE_CARD, command=lambda: self._go_page(self.current_page + 1)
        )
        self.next_btn.pack(side="left", padx=2)

        # Register progress listener
        self.service.add_progress_listener(self._on_download_progress)

    def destroy(self) -> None:
        try:
            self.service.remove_progress_listener(self._on_download_progress)
        except Exception:
            pass
        super().destroy()

    def load_chart(self, chart_id: str) -> None:
        """Load chart data and populate table."""
        self.chart_id = chart_id
        self.current_page = 1
        self.search_query = ""
        self.search_entry.delete(0, "end")
        self.refresh()

    def refresh(self) -> None:
        """Fetch chart details and render."""
        if not self.chart_id:
            return
        details = self.service.get_chart_details(
            chart_id=self.chart_id,
            query=self.search_query,
            page=self.current_page,
            page_size=self.page_size,
        )
        self._apply_chart_details(details)

    def _apply_chart_details(self, details: Optional[Dict[str, Any]]) -> None:
        if not details:
            self.title_label.configure(text="Chart Not Found")
            return

        self._chart_data = details
        chart = details["chart"]
        stats = details["stats"]
        entries = details["entries"]
        total_matching = details["total_matching"]
        self._current_entries = entries
        self._total_matching = total_matching

        # 1. Update Hero Banner
        self.title_label.configure(text=chart.title)
        c_type = chart.chart_type
        icon = "🏆"
        if c_type == "trending":
            icon = "🔥"
        elif c_type == "stream_top":
            icon = "🍎"
        elif c_type == "all_time":
            icon = "📻"
        self.avatar_label.configure(text=icon)

        snap_str = str(chart.snapshot_date).split("T")[0] if chart.snapshot_date else "Recent"
        provider = chart.provider_name.replace("_", " ").title()
        self.subtitle_label.configure(text=f"{provider} • Updated: {snap_str}")

        # 2. Update Metric Chips
        for w in self.stats_chips_box.winfo_children():
            w.destroy()

        tot = stats.get("total_songs", 0)
        dl = stats.get("downloaded_songs", 0)
        miss = stats.get("missing_songs", 0)

        for label, val, color in [
            (f"{tot} Tracks", tot, theme.TEXT_PRIMARY),
            (f"✓ {dl} Downloaded", dl, theme.SUCCESS),
            (f"{miss} Missing", miss, theme.WARNING),
        ]:
            pill = ctk.CTkFrame(self.stats_chips_box, fg_color=theme.SURFACE_CARD, corner_radius=theme.RADIUS_SM)
            pill.pack(side="left", padx=4)
            ctk.CTkLabel(pill, text=label, font=theme.font_caption_bold(), text_color=color).pack(padx=8, pady=4)

        self.dl_missing_btn.configure(state="normal" if miss > 0 else "disabled")

        # 3. Update Toolbar Counter
        self.results_count_lbl.configure(text=f"Showing {len(entries)} of {total_matching} tracks")

        # 4. Render Table
        self._render_table(entries)

        # 5. Update Pagination
        self._update_pagination(total_matching)

    def _render_table(self, entries: List[Dict[str, Any]]) -> None:
        for w in self.table_scroll.winfo_children():
            w.destroy()

        self._progress_bars.clear()
        self._status_labels.clear()
        self._action_buttons.clear()

        if not entries:
            empty = ctk.CTkLabel(
                self.table_scroll,
                text="No tracks match the search query.",
                font=theme.font_body(),
                text_color=theme.TEXT_MUTED,
            )
            empty.grid(row=0, column=0, columnspan=7, pady=40)
            return

        # Render Header Row
        headers = ["#", "Trend", "Title", "Artist", "Movie / Album", "Status", "Action"]
        for col, h in enumerate(headers):
            lbl = ctk.CTkLabel(
                self.table_scroll,
                text=h,
                font=theme.font_caption_bold(),
                text_color=theme.TEXT_MUTED,
                anchor="w" if col in (2, 3, 4) else "center",
            )
            lbl.grid(row=0, column=col, sticky="ew", padx=6, pady=(4, 8))

        # Render Each Track Row
        for r_idx, item in enumerate(entries, start=1):
            rank = item["rank"]
            row_bg = theme.SURFACE_CARD if r_idx % 2 == 0 else "transparent"
            row_frame = ctk.CTkFrame(self.table_scroll, fg_color=row_bg, corner_radius=theme.RADIUS_SM)
            row_frame.grid(row=r_idx, column=0, columnspan=7, sticky="nsew", pady=2)

            # Inside row_frame configure same columns
            row_frame.grid_columnconfigure(0, weight=0, minsize=45)
            row_frame.grid_columnconfigure(1, weight=0, minsize=55)
            row_frame.grid_columnconfigure(2, weight=3, minsize=180)
            row_frame.grid_columnconfigure(3, weight=2, minsize=140)
            row_frame.grid_columnconfigure(4, weight=2, minsize=130)
            row_frame.grid_columnconfigure(5, weight=1, minsize=110)
            row_frame.grid_columnconfigure(6, weight=0, minsize=100)

            # Col 0: Rank #
            rank_color = theme.WARNING if rank == 1 else (theme.TEXT_PRIMARY if rank <= 3 else theme.TEXT_MUTED)
            rank_lbl = ctk.CTkLabel(
                row_frame,
                text=f"#{rank}",
                font=theme.font_body_bold(),
                text_color=rank_color,
                width=35,
            )
            rank_lbl.grid(row=0, column=0, padx=4, pady=6)

            # Col 1: Trend
            trend = item["trend"]
            trend_label = item["trend_label"]
            t_color = theme.SUCCESS if trend == "up" else (theme.DANGER if trend == "down" else (theme.PRIMARY_LIGHT if trend == "new" else theme.TEXT_DIM))
            trend_lbl = ctk.CTkLabel(
                row_frame,
                text=trend_label,
                font=theme.font_badge(),
                text_color=t_color,
                width=45,
            )
            trend_lbl.grid(row=0, column=1, padx=2, pady=6)

            # Col 2: Title
            title_lbl = ctk.CTkLabel(
                row_frame,
                text=item["title"],
                font=theme.font_body_bold(),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            )
            title_lbl.grid(row=0, column=2, sticky="ew", padx=6, pady=6)

            # Col 3: Artist (clickable if artist_id exists)
            art_id = item.get("artist_id")
            art_name = item.get("artist", "Unknown Artist")
            if art_id and self.on_open_artist:
                art_btn = ctk.CTkButton(
                    row_frame,
                    text=art_name[:28] + ("..." if len(art_name) > 28 else ""),
                    font=theme.font_caption(),
                    text_color=theme.PRIMARY_LIGHT,
                    fg_color="transparent",
                    hover_color=theme.PRIMARY_MUTED,
                    anchor="w",
                    command=lambda aid=art_id: self.on_open_artist(aid),
                )
                art_btn.grid(row=0, column=3, sticky="ew", padx=4, pady=4)
            else:
                art_lbl = ctk.CTkLabel(
                    row_frame,
                    text=art_name[:28] + ("..." if len(art_name) > 28 else ""),
                    font=theme.font_caption(),
                    text_color=theme.TEXT_MUTED,
                    anchor="w",
                )
                art_lbl.grid(row=0, column=3, sticky="ew", padx=6, pady=6)

            # Col 4: Movie / Album (clickable if movie_id exists)
            mov_id = item.get("movie_id")
            mov_name = item.get("movie", "Single")
            if mov_id and self.on_open_movie:
                mov_btn = ctk.CTkButton(
                    row_frame,
                    text=mov_name[:24] + ("..." if len(mov_name) > 24 else ""),
                    font=theme.font_caption(),
                    text_color=theme.PRIMARY_LIGHT,
                    fg_color="transparent",
                    hover_color=theme.PRIMARY_MUTED,
                    anchor="w",
                    command=lambda mid=mov_id: self.on_open_movie(mid),
                )
                mov_btn.grid(row=0, column=4, sticky="ew", padx=4, pady=4)
            else:
                mov_lbl = ctk.CTkLabel(
                    row_frame,
                    text=mov_name[:24] + ("..." if len(mov_name) > 24 else ""),
                    font=theme.font_caption(),
                    text_color=theme.TEXT_MUTED,
                    anchor="w",
                )
                mov_lbl.grid(row=0, column=4, sticky="ew", padx=6, pady=6)

            # Col 5: Status
            is_dl = item.get("is_downloaded", False)
            status_text = "✓ Downloaded" if is_dl else "Not Downloaded"
            status_color = theme.SUCCESS if is_dl else theme.TEXT_MUTED

            status_box = ctk.CTkFrame(row_frame, fg_color="transparent")
            status_box.grid(row=0, column=5, sticky="ew", padx=4, pady=6)

            status_lbl = ctk.CTkLabel(
                status_box,
                text=status_text,
                font=theme.font_badge(),
                text_color=status_color,
            )
            status_lbl.pack(anchor="center")

            song_id = item.get("song_id")
            if song_id:
                self._status_labels[song_id] = status_lbl

            # Col 6: Action Button
            action_btn = ctk.CTkButton(
                row_frame,
                text="▶ Play" if is_dl else "⬇ Download",
                font=theme.font_caption_bold(),
                fg_color=theme.PRIMARY_MUTED if is_dl else theme.PRIMARY,
                hover_color=theme.PRIMARY if is_dl else theme.PRIMARY_DARK,
                text_color=theme.TEXT_PRIMARY,
                height=26,
                width=85,
                command=lambda it=item: self._on_row_action_clicked(it),
            )
            action_btn.grid(row=0, column=6, padx=6, pady=4)
            if song_id:
                self._action_buttons[song_id] = action_btn

    def _on_row_action_clicked(self, item: Dict[str, Any]) -> None:
        """Handle Play or Download for a row."""
        is_dl = item.get("is_downloaded", False)
        file_path = item.get("file_path")

        if is_dl and file_path:
            ok, msg = self.service.play_audio_file(file_path)
            if not ok:
                messagebox.showwarning("Playback", msg)
        else:
            rank = item["rank"]
            self._download_single_rank(rank)

    def _download_single_rank(self, rank: int) -> None:
        def worker():
            plan = self.service.plan_chart_entry_download(self.chart_id, rank)
            if not plan.new_songs and not plan.upgrades:
                return

            enqueued_ids = self.service.execute_download_plan(plan, run_async=True)
            if self.on_start_downloads and enqueued_ids:
                try:
                    self.after(0, lambda: self.on_start_downloads(enqueued_ids))
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_missing_clicked(self) -> None:
        if not self.chart_id:
            return
        self.dl_missing_btn.configure(state="disabled", text="Planning...")

        def worker():
            plan = self.service.plan_chart_download_missing(self.chart_id)
            if not plan.new_songs:
                try:
                    self.after(0, lambda: self.dl_missing_btn.configure(state="normal", text="⬇ Download Missing"))
                except Exception:
                    pass
                return

            enqueued_ids = self.service.execute_download_plan(plan, run_async=True)
            try:
                self.after(0, lambda: self.dl_missing_btn.configure(state="disabled", text="Downloading..."))
                if self.on_start_downloads and enqueued_ids:
                    self.after(0, lambda: self.on_start_downloads(enqueued_ids))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_all_clicked(self) -> None:
        if not self.chart_id:
            return
        self.dl_all_btn.configure(state="disabled", text="Planning...")

        def worker():
            plan = self.service.plan_chart_download_all(self.chart_id)
            if not plan.new_songs and not plan.upgrades:
                try:
                    self.after(0, lambda: self.dl_all_btn.configure(state="normal", text="⚡ Download All"))
                except Exception:
                    pass
                return

            enqueued_ids = self.service.execute_download_plan(plan, run_async=True)
            try:
                self.after(0, lambda: self.dl_all_btn.configure(state="disabled", text="Downloading..."))
                if self.on_start_downloads and enqueued_ids:
                    self.after(0, lambda: self.on_start_downloads(enqueued_ids))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_progress(self, event: DownloadProgressEvent) -> None:
        """Update live UI on download progress events."""
        if not event.song_id:
            return

        def update():
            song_id = event.song_id
            if song_id in self._status_labels:
                lbl = self._status_labels[song_id]
                btn = self._action_buttons.get(song_id)

                if event.status == "DOWNLOADING":
                    pct = int(event.percent * 100)
                    lbl.configure(text=f"⬇ {pct}%", text_color=theme.WARNING)
                elif event.status == "COMPLETED":
                    lbl.configure(text="✓ Downloaded", text_color=theme.SUCCESS)
                    if btn:
                        btn.configure(
                            text="▶ Play",
                            fg_color=theme.PRIMARY_MUTED,
                            hover_color=theme.PRIMARY,
                        )
                    # Refresh statistics
                    if self.chart_id:
                        stats = self.service.db.get_chart_statistics(self.chart_id)
                        self._update_stats_chips(stats)
                elif event.status == "FAILED":
                    lbl.configure(text="Failed", text_color=theme.DANGER)

        self.after(0, update)

    def _update_stats_chips(self, stats: Dict[str, int]) -> None:
        tot = stats.get("total_songs", 0)
        dl = stats.get("downloaded_songs", 0)
        miss = stats.get("missing_songs", 0)

        for w in self.stats_chips_box.winfo_children():
            w.destroy()

        for label, val, color in [
            (f"{tot} Tracks", tot, theme.TEXT_PRIMARY),
            (f"✓ {dl} Downloaded", dl, theme.SUCCESS),
            (f"{miss} Missing", miss, theme.WARNING),
        ]:
            pill = ctk.CTkFrame(self.stats_chips_box, fg_color=theme.SURFACE_CARD, corner_radius=theme.RADIUS_SM)
            pill.pack(side="left", padx=4)
            ctk.CTkLabel(pill, text=label, font=theme.font_caption_bold(), text_color=color).pack(padx=8, pady=4)

        self.dl_missing_btn.configure(state="normal" if miss > 0 else "disabled", text="⬇ Download Missing")
        self.dl_all_btn.configure(state="normal", text="⚡ Download All")

    def _on_search_key(self, event=None) -> None:
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
        self._search_debounce_id = self.after(300, self._apply_search)

    def _apply_search(self) -> None:
        self.search_query = self.search_entry.get().strip()
        self.current_page = 1
        self.refresh()

    def _update_pagination(self, total: int) -> None:
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        start = (self.current_page - 1) * self.page_size + 1 if total > 0 else 0
        end = min(self.current_page * self.page_size, total)

        self.page_lbl.configure(text=f"Showing {start}–{end} of {total} tracks")
        self.page_indicator.configure(text=f"{self.current_page} / {total_pages}")

        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < total_pages else "disabled")

    def _go_page(self, p: int) -> None:
        total_pages = max(1, (self._total_matching + self.page_size - 1) // self.page_size)
        if 1 <= p <= total_pages:
            self.current_page = p
            self.refresh()
