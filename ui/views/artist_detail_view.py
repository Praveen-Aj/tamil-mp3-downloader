"""
Artist and Person Detail View.

Displays comprehensive person metadata, associated roles, verified download metrics,
associated soundtrack songs, and movies.
Provides:
- One-click [Download All Missing] and [Download All] actions
- Dual-tab layout for Songs and Movies
- Direct navigation from Artist -> Movie (opens MovieDetailView)
- Direct navigation from Song -> Download
- Live progress synchronization with DownloadJobManager
"""

import threading
from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from ui.services.library_service import LibraryService, DownloadProgressEvent
from ui import theme


class ArtistDetailView(ctk.CTkFrame):
    """
    Detailed Person view showing metadata, roles, associated songs, and movies.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_back: Callable[[], None],
        on_open_movie: Optional[Callable[[int], None]] = None,
        on_start_downloads: Optional[Callable[[List[int]], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_APP, corner_radius=0, **kwargs)
        self.service = service
        self.on_back = on_back
        self.on_open_movie = on_open_movie
        self.on_start_downloads = on_start_downloads

        self.artist_id: Optional[int] = None
        self._artist_data: Optional[Dict[str, Any]] = None
        self._active_downloads: Dict[Any, Any] = {}
        self._active_tab: str = "songs"  # 'songs' or 'movies'

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
            text="← Back to People",
            width=135,
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
            text="Person Details",
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
        )
        self.nav_title_lbl.pack(side="left", padx=10)

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

        # ── 2. Hero & Metadata Banner ────────────────────────────────
        self.hero_card = ctk.CTkFrame(
            self,
            fg_color=theme.SURFACE,
            corner_radius=theme.RADIUS_LG,
            border_color=theme.BORDER,
            border_width=1,
        )
        self.hero_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(14, 10))
        self.hero_card.grid_columnconfigure(1, weight=1)

        # Left: Icon / Avatar
        self.avatar_frame = ctk.CTkFrame(
            self.hero_card,
            width=72,
            height=72,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE_ELEVATED,
        )
        self.avatar_frame.grid(row=0, column=0, rowspan=2, padx=18, pady=18)
        self.avatar_frame.pack_propagate(False)

        self.avatar_label = ctk.CTkLabel(
            self.avatar_frame,
            text="👥",
            font=ctk.CTkFont(size=32),
        )
        self.avatar_label.pack(expand=True)

        # Middle: Metadata
        meta_box = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        meta_box.grid(row=0, column=1, sticky="w", padx=(0, 20), pady=(18, 4))

        self.artist_name_lbl = ctk.CTkLabel(
            meta_box,
            text="Loading…",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.artist_name_lbl.pack(anchor="w")

        self.roles_box = ctk.CTkFrame(meta_box, fg_color="transparent")
        self.roles_box.pack(anchor="w", pady=(4, 0))

        # Action Buttons (Right)
        actions_box = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        actions_box.grid(row=0, column=2, rowspan=2, sticky="e", padx=20, pady=18)

        self.btn_dl_missing = ctk.CTkButton(
            actions_box,
            text="⬇  Download Missing",
            width=180,
            height=36,
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._on_download_missing_clicked,
        )
        self.btn_dl_missing.pack(pady=(0, 8))

        self.btn_dl_all = ctk.CTkButton(
            actions_box,
            text="⬇  Download All",
            width=180,
            height=32,
            font=theme.font_body(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._on_download_all_clicked,
        )
        self.btn_dl_all.pack()

        # Metrics Pills Frame (Row 1 under metadata)
        pills_frame = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        pills_frame.grid(row=1, column=1, sticky="w", padx=(0, 20), pady=(0, 16))

        self.chip_total = ctk.CTkLabel(
            pills_frame, text="🎵 Total Songs: 0",
            font=theme.font_caption_bold(), text_color=theme.TEXT_SECONDARY,
            fg_color=theme.SURFACE_ELEVATED, corner_radius=theme.RADIUS_SM,
            padx=10, pady=4,
        )
        self.chip_total.pack(side="left", padx=(0, 8))

        self.chip_downloaded = ctk.CTkLabel(
            pills_frame, text="✓ Downloaded: 0",
            font=theme.font_caption_bold(), text_color=theme.SUCCESS_LIGHT,
            fg_color=theme.SUCCESS_BG, corner_radius=theme.RADIUS_SM,
            padx=10, pady=4,
        )
        self.chip_downloaded.pack(side="left", padx=(0, 8))

        self.chip_missing = ctk.CTkLabel(
            pills_frame, text="⏳ Missing: 0",
            font=theme.font_caption_bold(), text_color=theme.WARNING_LIGHT,
            fg_color=theme.WARNING_BG, corner_radius=theme.RADIUS_SM,
            padx=10, pady=4,
        )
        self.chip_missing.pack(side="left", padx=(0, 8))

        self.chip_movies = ctk.CTkLabel(
            pills_frame, text="🎬 Movies: 0",
            font=theme.font_caption_bold(), text_color=theme.PRIMARY_LIGHT,
            fg_color=theme.SURFACE_ELEVATED, corner_radius=theme.RADIUS_SM,
            padx=10, pady=4,
        )
        self.chip_movies.pack(side="left")

        # ── 3. Content Navigation Tabs & Content Container ───────────
        content_container = ctk.CTkFrame(self, fg_color="transparent")
        content_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 16))
        content_container.grid_rowconfigure(1, weight=1)
        content_container.grid_columnconfigure(0, weight=1)

        # Tab Selector Bar
        tab_bar = ctk.CTkFrame(content_container, height=40, fg_color="transparent")
        tab_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.btn_tab_songs = ctk.CTkButton(
            tab_bar,
            text="🎵 Associated Songs (0)",
            height=32,
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=lambda: self._switch_tab("songs"),
        )
        self.btn_tab_songs.pack(side="left", padx=(0, 8))

        self.btn_tab_movies = ctk.CTkButton(
            tab_bar,
            text="🎬 Associated Movies (0)",
            height=32,
            font=theme.font_body(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=lambda: self._switch_tab("movies"),
        )
        self.btn_tab_movies.pack(side="left")

        # Scrollable View for Active Tab Content
        self.content_scroll = ctk.CTkScrollableFrame(content_container, fg_color=theme.SURFACE, corner_radius=theme.RADIUS_LG)
        self.content_scroll.grid(row=1, column=0, sticky="nsew")
        self.content_scroll.grid_columnconfigure(0, weight=1)

        # State storage for track rows
        self.song_status_labels: Dict[int, ctk.CTkLabel] = {}
        self.song_status_frames: Dict[int, ctk.CTkFrame] = {}

    # ── Setup & Refresh ──────────────────────────────────────────────

    def set_artist(self, artist_id: int) -> None:
        """Set active artist and trigger fetch."""
        self.artist_id = artist_id
        self._active_downloads.clear()
        self.refresh()

    def refresh(self) -> None:
        """Reload artist metadata, songs, and movies from database."""
        if not self.artist_id:
            return

        data = self.service.get_artist_details(self.artist_id)
        if not data:
            messagebox.showerror("Error", f"Artist with ID {self.artist_id} not found.")
            self.on_back()
            return

        self._artist_data = data
        artist = data["artist"]
        stats = data["stats"]
        songs = data["songs"]
        movies = data["movies"]
        roles = data.get("roles", [])

        # Update Navigation & Hero
        self.nav_title_lbl.configure(text=f"Person: {artist.name}")
        self.artist_name_lbl.configure(text=artist.name)

        # Avatar icon
        if "music_director" in roles:
            self.avatar_label.configure(text="🎼")
        elif "actor" in roles:
            self.avatar_label.configure(text="🎬")
        else:
            self.avatar_label.configure(text="🎤")

        # Roles Badges
        for w in self.roles_box.winfo_children():
            w.destroy()

        for r in roles:
            r_frame = ctk.CTkFrame(self.roles_box, fg_color=theme.PRIMARY_MUTED, corner_radius=theme.RADIUS_SM)
            r_frame.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(
                r_frame,
                text=r.replace("_", " ").title(),
                font=theme.font_caption_bold(),
                text_color=theme.PRIMARY_LIGHT,
            ).pack(padx=8, pady=2)

        # Update Metric Chips
        self._update_stats_chips(stats)

        # Update Tab Labels
        self.btn_tab_songs.configure(text=f"🎵 Associated Songs ({len(songs)})")
        self.btn_tab_movies.configure(text=f"🎬 Associated Movies ({len(movies)})")

        # Render Active Tab Content
        self._render_active_tab()

    def _update_stats_chips(self, stats: Optional[Dict[str, Any]] = None) -> None:
        """Update top summary chips and download button state."""
        if not self.artist_id:
            return
        if stats is None:
            stats = self.service.db.get_artist_statistics(self.artist_id)

        tot_s = stats.get("total", 0)
        dl_s = stats.get("downloaded", 0)
        miss_s = stats.get("missing", 0)
        tot_m = stats.get("movies_count", 0)

        self.chip_total.configure(text=f"🎵 Total Songs: {tot_s}")
        self.chip_downloaded.configure(text=f"✓ Downloaded: {dl_s}")
        self.chip_missing.configure(text=f"⏳ Missing: {miss_s}")
        self.chip_movies.configure(text=f"🎬 Movies: {tot_m}")

        if miss_s == 0 and tot_s > 0:
            self.btn_dl_missing.configure(state="disabled", text="✓ All Downloaded")
        else:
            self.btn_dl_missing.configure(state="normal", text=f"⬇  Download Missing ({miss_s})")

    def _switch_tab(self, tab: str) -> None:
        """Switch between Songs and Movies tabs."""
        if self._active_tab == tab:
            return
        self._active_tab = tab

        if tab == "songs":
            self.btn_tab_songs.configure(fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER, font=theme.font_body_bold())
            self.btn_tab_movies.configure(fg_color=theme.SURFACE_ELEVATED, hover_color=theme.SURFACE_HOVER, font=theme.font_body())
        else:
            self.btn_tab_movies.configure(fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER, font=theme.font_body_bold())
            self.btn_tab_songs.configure(fg_color=theme.SURFACE_ELEVATED, hover_color=theme.SURFACE_HOVER, font=theme.font_body())

        self._render_active_tab()

    def _render_active_tab(self) -> None:
        """Render active tab content in scroll view."""
        if not self._artist_data:
            return
        if self._active_tab == "songs":
            self._render_songs_table(self._artist_data.get("songs", []))
        else:
            self._render_movies_grid(self._artist_data.get("movies", []))

    # ── Songs Table ──────────────────────────────────────────────────

    def _render_songs_table(self, songs: List[Dict[str, Any]]) -> None:
        """Render tracklist table for this artist."""
        for widget in self.content_scroll.winfo_children():
            widget.destroy()

        self.song_status_labels.clear()
        self.song_status_frames.clear()

        if not songs:
            self._render_tab_empty_state("No songs associated with this artist.")
            return

        # Table Header Row
        hdr = ctk.CTkFrame(self.content_scroll, height=36, fg_color=theme.SURFACE_ELEVATED, corner_radius=theme.RADIUS_SM)
        hdr.pack(fill="x", padx=12, pady=(12, 6))
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="#", width=36, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(hdr, text="TITLE", width=220, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(hdr, text="MOVIE / ALBUM", width=180, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(hdr, text="QUALITY", width=90, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(hdr, text="STATUS", width=130, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(hdr, text="ACTION", width=110, font=theme.font_caption_bold(), text_color=theme.TEXT_MUTED, anchor="e").pack(side="right", padx=(0, 14))

        # Song Rows
        for idx, song in enumerate(songs, start=1):
            row = ctk.CTkFrame(self.content_scroll, height=44, fg_color=theme.SURFACE_MUTED if idx % 2 == 0 else "transparent", corner_radius=theme.RADIUS_SM)
            row.pack(fill="x", padx=12, pady=2)
            row.pack_propagate(False)

            sid = song["song_id"]
            mid = song.get("movie_id")
            movie_title = song.get("movie_title") or "Soundtrack"

            # Index
            ctk.CTkLabel(row, text=str(idx), width=36, font=theme.font_caption(), text_color=theme.TEXT_MUTED).pack(side="left", padx=(10, 0))

            # Title
            ctk.CTkLabel(row, text=song["title"], width=220, font=theme.font_body_bold(), text_color=theme.TEXT_PRIMARY, anchor="w").pack(side="left", padx=10)

            # Movie Name (Clickable link if movie_id exists)
            movie_box = ctk.CTkFrame(row, width=180, fg_color="transparent")
            movie_box.pack(side="left", padx=10)
            movie_box.pack_propagate(False)

            if mid and self.on_open_movie:
                btn_m = ctk.CTkButton(
                    movie_box,
                    text=f"🎬 {movie_title}",
                    height=26,
                    font=theme.font_caption(),
                    fg_color="transparent",
                    hover_color=theme.SURFACE_HOVER,
                    text_color=theme.PRIMARY_LIGHT,
                    anchor="w",
                    command=lambda m_id=mid: self.on_open_movie(m_id),
                )
                btn_m.pack(fill="both", expand=True)
            else:
                ctk.CTkLabel(movie_box, text=movie_title, font=theme.font_caption(), text_color=theme.TEXT_SECONDARY, anchor="w").pack(fill="both", expand=True)

            # Quality
            ctk.CTkLabel(row, text=song.get("quality_display", "320 kbps"), width=90, font=theme.font_caption(), text_color=theme.TEXT_SECONDARY, anchor="w").pack(side="left", padx=10)

            # Status Badge
            is_dl = song["is_downloaded"]
            status_text = "✓ Downloaded" if is_dl else "Not Downloaded"
            status_fg = theme.SUCCESS_LIGHT if is_dl else theme.TEXT_MUTED
            status_bg = theme.SUCCESS_BG if is_dl else theme.SURFACE_ELEVATED

            badge_frame = ctk.CTkFrame(row, width=120, height=24, fg_color=status_bg, corner_radius=theme.RADIUS_SM)
            badge_frame.pack(side="left", padx=10)
            badge_frame.pack_propagate(False)

            badge_lbl = ctk.CTkLabel(badge_frame, text=status_text, font=theme.font_caption_bold(), text_color=status_fg)
            badge_lbl.pack(expand=True)

            self.song_status_frames[sid] = badge_frame
            self.song_status_labels[sid] = badge_lbl

            # Action Button
            act_box = ctk.CTkFrame(row, width=110, fg_color="transparent")
            act_box.pack(side="right", padx=(0, 14))

            if is_dl:
                btn_play = ctk.CTkButton(
                    act_box, text="▶ Play", width=80, height=26,
                    font=theme.font_caption_bold(), fg_color=theme.SURFACE_ELEVATED,
                    hover_color=theme.SURFACE_HOVER, corner_radius=theme.RADIUS_SM,
                    command=lambda p=song.get("file_path"): self._play_audio(p)
                )
                btn_play.pack(side="right")
            else:
                btn_dl = ctk.CTkButton(
                    act_box, text="⬇ Download", width=80, height=26,
                    font=theme.font_caption(), fg_color=theme.PRIMARY,
                    hover_color=theme.PRIMARY_HOVER, corner_radius=theme.RADIUS_SM,
                    command=lambda s_id=sid: self._download_single_song(s_id)
                )
                btn_dl.pack(side="right")

    # ── Movies Grid ──────────────────────────────────────────────────

    def _render_movies_grid(self, movies: List[Dict[str, Any]]) -> None:
        """Render associated movies for this artist."""
        for widget in self.content_scroll.winfo_children():
            widget.destroy()

        if not movies:
            self._render_tab_empty_state("No movies associated with this artist.")
            return

        grid_container = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
        grid_container.pack(fill="both", expand=True, padx=12, pady=12)
        grid_container.grid_columnconfigure(0, weight=1)
        grid_container.grid_columnconfigure(1, weight=1)

        for idx, m in enumerate(movies):
            mid = m["movie_id"]
            row = idx // 2
            col = idx % 2

            m_card = ctk.CTkFrame(
                grid_container,
                fg_color=theme.SURFACE_ELEVATED,
                corner_radius=theme.RADIUS_MD,
                border_color=theme.BORDER,
                border_width=1,
            )
            m_card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            # Header inside card
            c_top = ctk.CTkFrame(m_card, fg_color="transparent")
            c_top.pack(fill="x", padx=14, pady=(12, 6))

            ctk.CTkLabel(
                c_top,
                text="🎬",
                font=ctk.CTkFont(size=20),
            ).pack(side="left", padx=(0, 10))

            t_box = ctk.CTkFrame(c_top, fg_color="transparent")
            t_box.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(
                t_box,
                text=f"{m['title']} ({m.get('year', '—')})",
                font=theme.font_body_bold(),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            ).pack(anchor="w")

            # Credit role badge (Music Director, Actor, Character)
            credit_text = m.get("credit_role", "Contributor")
            if m.get("character_name"):
                credit_text += f" as {m['character_name']}"

            ctk.CTkLabel(
                t_box,
                text=credit_text,
                font=theme.font_caption(),
                text_color=theme.PRIMARY_LIGHT,
                anchor="w",
            ).pack(anchor="w")

            # Stats line
            tot = m.get("total_songs", 0)
            dl = m.get("downloaded_songs", 0)
            stats_line = f"🎵 {tot} Songs   •   ✓ {dl}/{tot} Downloaded"
            ctk.CTkLabel(
                m_card,
                text=stats_line,
                font=theme.font_caption(),
                text_color=theme.TEXT_SECONDARY,
                anchor="w",
            ).pack(fill="x", padx=14, pady=(4, 8))

            # Button to open movie detail
            if self.on_open_movie:
                btn_m = ctk.CTkButton(
                    m_card,
                    text="Open Movie Soundtrack  ›",
                    height=28,
                    font=theme.font_caption_bold(),
                    fg_color=theme.SURFACE_MUTED,
                    hover_color=theme.SURFACE_HOVER,
                    corner_radius=theme.RADIUS_SM,
                    command=lambda movie_id=mid: self.on_open_movie(movie_id),
                )
                btn_m.pack(fill="x", padx=14, pady=(0, 12))

    def _render_tab_empty_state(self, message: str) -> None:
        """Empty state for content tab."""
        box = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
        box.pack(pady=40)
        ctk.CTkLabel(box, text="ℹ️", font=ctk.CTkFont(size=36)).pack(pady=(0, 8))
        ctk.CTkLabel(box, text=message, font=theme.font_body(), text_color=theme.TEXT_MUTED).pack()

    # ── Download Actions ─────────────────────────────────────────────

    def _on_download_missing_clicked(self) -> None:
        """Handle Download Missing action."""
        if not self.artist_id:
            return
        plan = self.service.plan_artist_download_missing(self.artist_id)
        if not plan.new_songs:
            messagebox.showinfo("All Downloaded", "All songs for this artist are already downloaded!")
            return

        enqueued_ids = self.service.execute_download_plan(plan, run_async=True)
        for planned in plan.new_songs:
            self._update_song_ui_status(planned.song_id, "⏳ QUEUED", theme.INFO_BG, theme.INFO_LIGHT)
        if self.on_start_downloads and enqueued_ids:
            self.on_start_downloads(enqueued_ids)

    def _on_download_all_clicked(self) -> None:
        """Handle Download All action."""
        if not self.artist_id:
            return
        plan = self.service.plan_artist_download_all(self.artist_id)
        if not plan.new_songs:
            messagebox.showinfo("All Downloaded", "All songs for this artist are already downloaded!")
            return

        enqueued_ids = self.service.execute_download_plan(plan, run_async=True)
        for planned in plan.new_songs:
            self._update_song_ui_status(planned.song_id, "⏳ QUEUED", theme.INFO_BG, theme.INFO_LIGHT)
        if self.on_start_downloads and enqueued_ids:
            self.on_start_downloads(enqueued_ids)

    def _download_single_song(self, song_id: int) -> None:
        """Download an individual song from tracklist."""
        plan = self.service.preview_download_plan(song_ids=[song_id])
        if not plan.new_songs:
            messagebox.showwarning("Unavailable", "No available audio source found for this song or already downloaded.")
            return

        enqueued_ids = self.service.execute_download_plan(plan, run_async=True)
        self._update_song_ui_status(song_id, "⏳ QUEUED", theme.INFO_BG, theme.INFO_LIGHT)
        if self.on_start_downloads and enqueued_ids:
            self.on_start_downloads(enqueued_ids)

    def _play_audio(self, file_path: Optional[str]) -> None:
        """Launch default system audio player."""
        if not file_path:
            return
        import os, subprocess, sys
        if not os.path.isfile(file_path):
            messagebox.showerror("Missing File", "Physical audio file is missing on disk.")
            self.refresh()
            return
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
        except Exception as e:
            messagebox.showerror("Playback Error", f"Failed to play audio: {e}")

    # ── Live Progress Handling ───────────────────────────────────────

    def _update_song_ui_status(self, song_id: int, text: str, bg_color: str, fg_color: str) -> None:
        """Update status badge for a single song row."""
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
        sid = event.song_id
        if not sid or sid not in self.song_status_labels:
            return

        if event.status == "DOWNLOADING":
            pct = int(event.percent or 0)
            self._update_song_ui_status(sid, f"⬇ {pct}%", theme.PRIMARY_MUTED, theme.PRIMARY_LIGHT)
        elif event.status == "COMPLETED":
            self._active_downloads.pop(sid, None)
            self._update_song_ui_status(sid, "✓ Downloaded", theme.SUCCESS_BG, theme.SUCCESS_LIGHT)
            self.after(100, self._update_stats_chips)
        elif event.status == "FAILED":
            self._active_downloads.pop(sid, None)
            self._update_song_ui_status(sid, "Failed", theme.ERROR_BG, theme.ERROR_LIGHT)
