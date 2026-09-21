"""
Movie Detail View.

Displays comprehensive movie metadata, verified download metrics,
and detailed tracklist.
Provides:
- One-click [Download All] and [Download Missing] actions
- Live progress synchronization with DownloadJobManager
- Safe filesystem reconciliation
- Play action for downloaded audio tracks
"""

import threading
from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from ui.services.library_service import LibraryService, DownloadProgressEvent
from ui import theme


class MovieDetailView(ctk.CTkFrame):
    """
    Detailed Movie view showing metadata, tracklist, and download actions.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_back: Callable[[], None],
        on_start_downloads: Optional[Callable[[List[int]], None]] = None,
        on_open_artist: Optional[Callable[[int], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_APP, corner_radius=0, **kwargs)
        self.service = service
        self.on_back = on_back
        self.on_start_downloads = on_start_downloads
        self.on_open_artist = on_open_artist

        self.movie_id: Optional[int] = None
        self._movie_data: Optional[Dict[str, Any]] = None
        self._active_downloads: Dict[int, str] = {}  # song_id -> status

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Register progress listener for real-time status updates
        self.service.add_progress_listener(self._on_download_progress)

        # ── 1. Top Navigation Bar ────────────────────────────────────
        nav_bar = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=theme.BG_HEADER)
        nav_bar.grid(row=0, column=0, sticky="ew")
        nav_bar.grid_propagate(False)

        btn_back = ctk.CTkButton(
            nav_bar,
            text="← Back to Movies",
            width=130,
            height=32,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self.on_back,
        )
        btn_back.pack(side="left", padx=20, pady=10)

        self.nav_title_lbl = ctk.CTkLabel(
            nav_bar,
            text="Movie Details",
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
        )
        self.nav_title_lbl.pack(side="left", padx=10)

        # Refresh button on right
        ctk.CTkButton(
            nav_bar,
            text="🔄  Refresh State",
            width=140,
            height=32,
            font=theme.font_caption(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self.refresh,
        ).pack(side="right", padx=20, pady=10)

        # ── 2. Movie Hero & Metadata Banner ──────────────────────────
        self.hero_card = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_LG, border_color=theme.BORDER, border_width=1)
        self.hero_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(14, 10))

        # Internal Layout: Left icon box, Middle metadata, Right download actions
        self.hero_card.grid_columnconfigure(1, weight=1)

        # Left: Visual icon box
        hero_left = ctk.CTkFrame(self.hero_card, width=72, height=72, corner_radius=theme.RADIUS_MD, fg_color=theme.SURFACE_ELEVATED)
        hero_left.grid(row=0, column=0, rowspan=2, padx=18, pady=18)
        hero_left.pack_propagate(False)
        ctk.CTkLabel(hero_left, text="🎬", font=ctk.CTkFont(size=34)).pack(expand=True)

        # Middle: Title and metadata
        meta_box = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        meta_box.grid(row=0, column=1, sticky="w", padx=(0, 20), pady=(18, 6))

        self.movie_title_lbl = ctk.CTkLabel(
            meta_box,
            text="Movie Title",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.movie_title_lbl.pack(anchor="w")

        self.movie_subtitle_lbl = ctk.CTkLabel(
            meta_box,
            text="Director • Year • Composers",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.movie_subtitle_lbl.pack(anchor="w", pady=(3, 0))

        self.credits_box = ctk.CTkFrame(meta_box, fg_color="transparent")
        self.credits_box.pack(anchor="w", pady=(4, 0))

        # Metrics chips below title
        self.metrics_box = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        self.metrics_box.grid(row=1, column=1, sticky="w", padx=(0, 20), pady=(0, 18))

        self.chip_total = self._create_metric_chip(self.metrics_box, "🎵 Total Songs: 0", theme.SURFACE_ELEVATED, theme.TEXT_SECONDARY)
        self.chip_downloaded = self._create_metric_chip(self.metrics_box, "✓ Downloaded: 0", theme.SUCCESS_BG, theme.SUCCESS_LIGHT)
        self.chip_missing = self._create_metric_chip(self.metrics_box, "⏳ Missing: 0", theme.WARNING_BG, theme.WARNING_LIGHT)

        # Right: Bulk Download Actions
        actions_box = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        actions_box.grid(row=0, column=2, rowspan=2, padx=20, pady=18, sticky="e")

        self.btn_dl_all = ctk.CTkButton(
            actions_box,
            text="⬇  Download All",
            width=150,
            height=36,
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._on_download_all,
        )
        self.btn_dl_all.pack(pady=(0, 8))

        self.btn_dl_missing = ctk.CTkButton(
            actions_box,
            text="⬇  Download Missing",
            width=150,
            height=36,
            font=theme.font_body_bold(),
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._on_download_missing,
        )
        self.btn_dl_missing.pack()

        # ── 3. Songs Table Area ──────────────────────────────────────
        table_container = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_LG, border_color=theme.BORDER, border_width=1)
        table_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 14))
        table_container.grid_rowconfigure(1, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Table Header
        th_frame = ctk.CTkFrame(table_container, height=38, corner_radius=0, fg_color=theme.BG_HEADER)
        th_frame.grid(row=0, column=0, sticky="ew")
        th_frame.grid_propagate(False)

        # Header Columns
        ctk.CTkLabel(th_frame, text="#", width=40, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="center").pack(side="left", padx=(10, 0))
        ctk.CTkLabel(th_frame, text="TITLE", width=260, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(th_frame, text="ARTIST", width=180, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(th_frame, text="QUALITY", width=90, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="center").pack(side="left", padx=10)
        ctk.CTkLabel(th_frame, text="STATUS", width=130, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="center").pack(side="left", padx=10)
        ctk.CTkLabel(th_frame, text="ACTIONS", width=110, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="center").pack(side="right", padx=(0, 20))

        # Scrollable Songs List
        self.songs_scroll = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
        self.songs_scroll.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.songs_scroll.grid_columnconfigure(0, weight=1)

        self.song_status_labels: Dict[int, ctk.CTkLabel] = {}
        self.song_status_frames: Dict[int, ctk.CTkFrame] = {}

    def _create_metric_chip(self, parent: ctk.CTkFrame, text: str, bg_color: str, fg_color: str) -> ctk.CTkLabel:
        pill = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=theme.RADIUS_SM)
        pill.pack(side="left", padx=(0, 8))
        lbl = ctk.CTkLabel(pill, text=text, font=theme.font_caption_bold(), text_color=fg_color)
        lbl.pack(padx=8, pady=3)
        return lbl

    def set_movie(self, movie_id: int) -> None:
        """Set active movie and reload view."""
        self.movie_id = movie_id
        self.refresh()

    def refresh(self) -> None:
        """Reload movie metadata and song status from database."""
        if not self.movie_id:
            return

        data = self.service.get_movie_details(self.movie_id)
        if not data:
            messagebox.showerror("Error", f"Movie with ID {self.movie_id} not found.")
            self.on_back()
            return

        self._movie_data = data
        movie = data["movie"]
        stats = data["stats"]
        songs = data["songs"]
        composers = data.get("composers", [])

        # Update Headers
        self.nav_title_lbl.configure(text=f"Movie: {movie.title}")
        self.movie_title_lbl.configure(text=movie.title)

        meta_parts = []
        if movie.year:
            meta_parts.append(str(movie.year))
        if movie.director:
            meta_parts.append(f"Directed by {movie.director}")
        if composers:
            comp_names = [c if isinstance(c, str) else c.get("name", "") for c in composers]
            meta_parts.append(f"Music by {', '.join(comp_names)}")
        self.movie_subtitle_lbl.configure(text=" • ".join(meta_parts) if meta_parts else "Tamil Movie Soundtrack")

        # Render clickable composer & actor credits
        for w in self.credits_box.winfo_children():
            w.destroy()

        composer_objs = data.get("composer_objects", [])
        for c in composer_objs:
            c_name = c.get("name")
            c_id = c.get("id")
            if c_name and c_id and self.on_open_artist:
                btn_c = ctk.CTkButton(
                    self.credits_box,
                    text=f"🎼 {c_name}",
                    height=24,
                    font=theme.font_caption_bold(),
                    fg_color=theme.SURFACE_ELEVATED,
                    hover_color=theme.SURFACE_HOVER,
                    text_color=theme.PRIMARY_LIGHT,
                    corner_radius=theme.RADIUS_SM,
                    command=lambda aid=c_id: self.on_open_artist(aid),
                )
                btn_c.pack(side="left", padx=(0, 6))

        actor_objs = data.get("actor_objects", [])
        for a in actor_objs[:4]:
            a_name = a.get("name")
            a_id = a.get("id")
            if a_name and a_id and self.on_open_artist:
                btn_a = ctk.CTkButton(
                    self.credits_box,
                    text=f"🎬 {a_name}",
                    height=24,
                    font=theme.font_caption(),
                    fg_color=theme.SURFACE_ELEVATED,
                    hover_color=theme.SURFACE_HOVER,
                    text_color=theme.TEXT_SECONDARY,
                    corner_radius=theme.RADIUS_SM,
                    command=lambda aid=a_id: self.on_open_artist(aid),
                )
                btn_a.pack(side="left", padx=(0, 6))

        # Update Metrics Chips
        self._update_stats_chips(stats)

        # Render Songs Rows
        self._render_song_rows(songs)

    def _update_stats_chips(self, stats: Optional[Dict[str, int]] = None) -> None:
        """Update top summary chips and download button state."""
        if not self.movie_id:
            return
        if stats is None:
            stats = self.service.db.get_movie_download_stats(self.movie_id)

        total_songs = stats.get("total", 0)
        downloaded = stats.get("downloaded", 0)
        missing = stats.get("missing", 0)

        self.chip_total.configure(text=f"🎵 Total Songs: {total_songs}")
        self.chip_downloaded.configure(text=f"✓ Downloaded: {downloaded}")
        self.chip_missing.configure(text=f"⏳ Missing: {missing}")

        # Update Download Missing button state
        if missing == 0 and total_songs > 0:
            self.btn_dl_missing.configure(state="disabled", text="✓ All Downloaded")
        else:
            self.btn_dl_missing.configure(state="normal", text=f"⬇  Download Missing ({missing})")

    def _render_song_rows(self, songs: List[Dict[str, Any]]) -> None:
        """Render rows for each song in the movie."""
        for widget in self.songs_scroll.winfo_children():
            widget.destroy()

        self.song_status_labels.clear()
        self.song_status_frames.clear()

        if not songs:
            empty_row = ctk.CTkFrame(self.songs_scroll, fg_color="transparent")
            empty_row.pack(fill="x", pady=40)
            ctk.CTkLabel(
                empty_row,
                text="No songs found for this movie yet. Click 'Discover Online' on the Movies page to fetch tracks.",
                font=theme.font_body(),
                text_color=theme.TEXT_MUTED,
            ).pack()
            return

        for idx, song in enumerate(songs, start=1):
            song_id = song["song_id"]
            track_num = song.get("track_number") or idx
            is_dl = song["is_downloaded"]
            active_status = self._active_downloads.get(song_id)

            row = ctk.CTkFrame(
                self.songs_scroll,
                height=42,
                fg_color=theme.SURFACE_MUTED if idx % 2 == 0 else "transparent",
                corner_radius=theme.RADIUS_SM,
            )
            row.pack(fill="x", padx=4, pady=2)
            row.pack_propagate(False)

            # Track number
            ctk.CTkLabel(row, text=str(track_num), width=40, font=theme.font_body(), text_color=theme.TEXT_MUTED, anchor="center").pack(side="left", padx=(10, 0))

            # Title
            ctk.CTkLabel(row, text=song["title"], width=260, font=theme.font_body_bold(), text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left", padx=10)

            # Artist
            ctk.CTkLabel(row, text=song["artist"], width=180, font=theme.font_caption(), text_color=theme.TEXT_SECONDARY, anchor="w").pack(side="left", padx=10)

            # Quality
            ctk.CTkLabel(row, text=song["quality_display"], width=90, font=theme.font_caption(), text_color=theme.TEXT_MUTED, anchor="center").pack(side="left", padx=10)

            # Status Badge Pill
            if active_status:
                badge_text = active_status
                badge_bg = theme.INFO_BG
                badge_fg = theme.INFO_LIGHT
            elif is_dl:
                badge_text = "✓ Downloaded"
                badge_bg = theme.SUCCESS_BG
                badge_fg = theme.SUCCESS_LIGHT
            else:
                badge_text = "Not Downloaded"
                badge_bg = theme.SURFACE_ELEVATED
                badge_fg = theme.TEXT_MUTED

            badge_frame = ctk.CTkFrame(row, fg_color=badge_bg, corner_radius=theme.RADIUS_SM, width=120, height=24)
            badge_frame.pack(side="left", padx=10)
            badge_frame.pack_propagate(False)

            badge_lbl = ctk.CTkLabel(badge_frame, text=badge_text, font=theme.font_badge(), text_color=badge_fg)
            badge_lbl.pack(expand=True)

            self.song_status_labels[song_id] = badge_lbl
            self.song_status_frames[song_id] = badge_frame

            # Actions Button
            act_box = ctk.CTkFrame(row, width=110, fg_color="transparent")
            act_box.pack(side="right", padx=(0, 20))

            if is_dl:
                ctk.CTkButton(
                    act_box,
                    text="▶  Play",
                    width=75,
                    height=26,
                    font=theme.font_caption_bold(),
                    fg_color=theme.SURFACE_ELEVATED,
                    hover_color=theme.SURFACE_HOVER,
                    corner_radius=theme.RADIUS_SM,
                    command=lambda sid=song_id, fp=song.get("file_path"): self._play_song(sid, fp),
                ).pack(side="right")
            else:
                ctk.CTkButton(
                    act_box,
                    text="⬇  Download",
                    width=85,
                    height=26,
                    font=theme.font_caption_bold(),
                    fg_color=theme.PRIMARY,
                    hover_color=theme.PRIMARY_HOVER,
                    corner_radius=theme.RADIUS_SM,
                    command=lambda sid=song_id: self._download_single_song(sid),
                ).pack(side="right")

    def _play_song(self, song_id: int, file_path: Optional[str]) -> None:
        """Launch the downloaded audio track."""
        success, msg = self.service.play_audio_file(file_path)
        if not success:
            messagebox.showwarning("Cannot Play", msg)

    def _download_single_song(self, song_id: int) -> None:
        """Queue and download a single song."""
        plan = self.service.preview_download_plan(song_ids=[song_id])
        if not plan.new_songs:
            messagebox.showinfo("Download", "This song is already downloaded or has no downloadable source.")
            return

        enqueued_ids = self.service.execute_download_plan(plan, run_async=True)
        self._update_song_ui_status(song_id, "⏳ QUEUED", theme.INFO_BG, theme.INFO_LIGHT)
        if self.on_start_downloads and enqueued_ids:
            self.on_start_downloads(enqueued_ids)

    def _on_download_all(self) -> None:
        """Plan and execute Download All for the movie."""
        if not self.movie_id:
            return
        plan = self.service.plan_movie_download_all(self.movie_id)
        if not plan.new_songs:
            messagebox.showinfo("Movie Download", "All songs for this movie are already downloaded!")
            return

        enqueued_ids = self.service.execute_download_plan(plan, run_async=True)
        for planned in plan.new_songs:
            self._update_song_ui_status(planned.song_id, "⏳ QUEUED", theme.INFO_BG, theme.INFO_LIGHT)

        messagebox.showinfo(
            "Download Started",
            f"Queued {len(enqueued_ids)} songs from '{self._movie_data['movie'].title}' for download!"
        )
        if self.on_start_downloads and enqueued_ids:
            self.on_start_downloads(enqueued_ids)

    def _on_download_missing(self) -> None:
        """Plan and execute Download Missing for the movie."""
        if not self.movie_id:
            return
        plan = self.service.plan_movie_download_missing(self.movie_id)
        if not plan.new_songs:
            messagebox.showinfo("Download Missing", "No missing songs found. Your movie soundtrack library is complete!")
            return

        enqueued_ids = self.service.execute_download_plan(plan, run_async=True)
        for planned in plan.new_songs:
            self._update_song_ui_status(planned.song_id, "⏳ QUEUED", theme.INFO_BG, theme.INFO_LIGHT)

        messagebox.showinfo(
            "Download Missing",
            f"Queued {len(enqueued_ids)} missing songs for download."
        )
        if self.on_start_downloads and enqueued_ids:
            self.on_start_downloads(enqueued_ids)

    def _update_song_ui_status(self, song_id: int, text: str, bg_color: str, fg_color: str) -> None:
        """Update the status badge for an individual song row."""
        cache_key = f"_badge_{song_id}"
        if self._active_downloads.get(cache_key) == (text, bg_color, fg_color):
            return
        self._active_downloads[cache_key] = (text, bg_color, fg_color)

        lbl = self.song_status_labels.get(song_id)
        frame = self.song_status_frames.get(song_id)
        if lbl and frame:
            try:
                self.after(0, lambda: [
                    lbl.configure(text=text, text_color=fg_color),
                    frame.configure(fg_color=bg_color),
                ])
            except Exception:
                pass

    def _on_download_progress(self, event: DownloadProgressEvent) -> None:
        """Handle live download progress updates from the event bus."""
        if not event.song_id or event.song_id not in self.song_status_labels:
            return

        sid = event.song_id
        if event.status == "DOWNLOADING":
            pct = int((event.percent or 0) * 100)
            txt = f"⏳ DL {pct}%" if pct > 0 else "⏳ DL..."
            self._active_downloads[sid] = txt
            self._update_song_ui_status(sid, txt, theme.INFO_BG, theme.INFO_LIGHT)
        elif event.status == "COMPLETED":
            self._active_downloads.pop(sid, None)
            self._update_song_ui_status(sid, "✓ Downloaded", theme.SUCCESS_BG, theme.SUCCESS_LIGHT)
            # Update metrics chips without rebuilding the entire UI
            self.after(100, self._update_stats_chips)
        elif event.status == "FAILED":
            self._active_downloads.pop(sid, None)
            self._update_song_ui_status(sid, "Failed", theme.ERROR_BG, theme.ERROR_LIGHT)

    def destroy(self) -> None:
        """Clean up progress listener upon removal."""
        try:
            self.service.remove_progress_listener(self._on_download_progress)
        except Exception:
            pass
        super().destroy()
