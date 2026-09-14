"""
Redesigned Modern Dashboard View (Part 14).
Provides rich library metrics, quick Add Music CTA, recent import jobs,
and discovery health overview.
"""

from typing import Dict, Any, Callable, Optional, List
import tkinter as tk
import customtkinter as ctk

from library.models import ImportJob, JobStatus
from ui.services.library_service import LibraryService


class DashboardView(ctk.CTkFrame):
    """
    Modern Desktop Music Dashboard with metric cards, quick acquisition CTA,
    and recent activity tracking.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_navigate: Callable[[str], None],
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.service = service
        self.on_navigate = on_navigate

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#181824")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="📊  Dashboard Overview",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffffff",
        ).pack(side="left", padx=20, pady=12)

        # Action bar in header
        ctk.CTkButton(
            header,
            text="➕ Add Music",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#6366f1",
            hover_color="#4f46e5",
            width=120,
            height=34,
            command=lambda: self.on_navigate("add_music"),
        ).pack(side="right", padx=16, pady=12)

        ctk.CTkButton(
            header,
            text="🔄 Refresh",
            width=85,
            height=34,
            fg_color=("gray75", "#2a2a3c"),
            hover_color=("gray65", "#3f3f5a"),
            command=self.refresh,
        ).pack(side="right", padx=(0, 8), pady=12)

        # ── 2. Scrollable Body ──────────────────────────────────────
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=15)
        self.scroll.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        # ── 3. Quick Action Hero Banner ─────────────────────────────
        hero = ctk.CTkFrame(self.scroll, corner_radius=12, fg_color=("gray90", "#181824"))
        hero.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 16))
        hero.grid_columnconfigure(0, weight=1)

        hero_left = ctk.CTkFrame(hero, fg_color="transparent")
        hero_left.pack(side="left", padx=20, pady=18)

        ctk.CTkLabel(
            hero_left,
            text="🎵 Ready to expand your music collection?",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("gray10", "#f3f4f6"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            hero_left,
            text="Paste Spotify, YouTube, or direct music URLs to analyze tracks, verify audio sources, and download into your library.",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "#9ca3af"),
        ).pack(anchor="w", pady=(4, 0))

        hero_btn = ctk.CTkButton(
            hero,
            text="➕ Add Music via URL",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=38,
            command=lambda: self.on_navigate("add_music"),
        )
        hero_btn.pack(side="right", padx=20, pady=18)

        # ── 4. Metric KPI Cards (6 Cards) ───────────────────────────
        self._card_vars: Dict[str, tk.StringVar] = {}
        self._build_kpi_cards()

        # ── 5. Split Panes: Recent Imports & System Status ───────────
        bottom_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, columnspan=6, sticky="nsew", pady=12)
        bottom_frame.grid_columnconfigure(0, weight=3)
        bottom_frame.grid_columnconfigure(1, weight=2)

        # Recent Import Jobs Pane (Left)
        self.jobs_card = ctk.CTkFrame(bottom_frame, corner_radius=12, fg_color=("gray90", "#181824"))
        self.jobs_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ctk.CTkLabel(
            self.jobs_card,
            text="RECENT PLAYLIST & URL IMPORTS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#60a5fa",
        ).pack(anchor="w", padx=16, pady=(14, 8))

        self.jobs_container = ctk.CTkFrame(self.jobs_card, fg_color="transparent")
        self.jobs_container.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # Discovery & Health Status Pane (Right)
        status_card = ctk.CTkFrame(bottom_frame, corner_radius=12, fg_color=("gray90", "#181824"))
        status_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(
            status_card,
            text="SOURCE & SYSTEM HEALTH",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#fbbf24",
        ).pack(anchor="w", padx=16, pady=(14, 8))

        self.health_var = tk.StringVar(value="Loading system health...")
        ctk.CTkLabel(
            status_card,
            textvariable=self.health_var,
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "#d1d5db"),
            justify="left",
            wraplength=350,
        ).pack(anchor="w", padx=16, pady=(0, 14))

        # Quick navigation buttons in status card
        nav_box = ctk.CTkFrame(status_card, fg_color="transparent")
        nav_box.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(
            nav_box,
            text="🔍 Discover Songs",
            height=32,
            fg_color=("gray75", "#2a2a3c"),
            hover_color=("gray65", "#3f3f5a"),
            command=lambda: self.on_navigate("discover"),
        ).pack(fill="x", pady=3)

        ctk.CTkButton(
            nav_box,
            text="📚 Browse Library",
            height=32,
            fg_color=("gray75", "#2a2a3c"),
            hover_color=("gray65", "#3f3f5a"),
            command=lambda: self.on_navigate("library"),
        ).pack(fill="x", pady=3)

        ctk.CTkButton(
            nav_box,
            text="🌐 Source Health",
            height=32,
            fg_color=("gray75", "#2a2a3c"),
            hover_color=("gray65", "#3f3f5a"),
            command=lambda: self.on_navigate("sources"),
        ).pack(fill="x", pady=3)

        self.refresh()

    def _build_kpi_cards(self) -> None:
        cards_data = [
            ("total_songs", "Total Songs", "#60a5fa", 0),
            ("owned_songs", "Owned", "#4ade80", 1),
            ("unowned_songs", "Ready to Download", "#38bdf8", 2),
            ("upgrades_available", "Upgrades Available", "#c084fc", 3),
            ("active_downloads", "Active Queue", "#fbbf24", 4),
            ("failed_downloads", "Failed Downloads", "#f87171", 5),
        ]

        for key, title, color, col_idx in cards_data:
            card = ctk.CTkFrame(self.scroll, corner_radius=10, fg_color=("gray90", "#181824"))
            card.grid(row=1, column=col_idx, sticky="nsew", padx=4, pady=4)

            ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=11), text_color=("gray50", "#9ca3af")
            ).pack(anchor="w", padx=12, pady=(10, 2))

            var = tk.StringVar(value="0")
            self._card_vars[key] = var

            ctk.CTkLabel(
                card,
                textvariable=var,
                font=ctk.CTkFont(size=22, weight="bold"),
                text_color=color,
            ).pack(anchor="w", padx=12, pady=(0, 10))

    def refresh(self) -> None:
        """Fetch updated metrics, recent import jobs, and system status."""
        stats = self.service.get_dashboard_stats()

        self._card_vars["total_songs"].set(f"{stats.get('total_songs', 0):,}")
        self._card_vars["owned_songs"].set(f"{stats.get('owned_songs', 0):,}")
        self._card_vars["unowned_songs"].set(f"{stats.get('unowned_songs', 0):,}")
        self._card_vars["upgrades_available"].set(f"{stats.get('upgrades_available', 0):,}")
        self._card_vars["active_downloads"].set(f"{stats.get('active_downloads', 0):,}")

        # Failed downloads
        all_dls = self.service.db.get_all_downloads()
        failed_cnt = sum(1 for d in all_dls if hasattr(d.state, "value") and d.state.value == "FAILED")
        self._card_vars["failed_downloads"].set(f"{failed_cnt:,}")

        # System health text
        health_info = (
            f"• Core Regional Sources: {stats.get('healthy_sources', 'N/A')}\n"
            f"• Audio Providers: YouTube (yt-dlp), Tamil Regional, Direct HTTP\n"
            f"• Storage Location: {self.service.db_path.parent}\n"
            f"• SQLite Canonical State: Synchronized"
        )
        self.health_var.set(health_info)

        # Render recent import jobs
        for w in self.jobs_container.winfo_children():
            w.destroy()

        recent_jobs = self.service.get_recent_import_jobs(limit=5)
        if not recent_jobs:
            ctk.CTkLabel(
                self.jobs_container,
                text="No URL or playlist imports yet. Click '+ Add Music' above to start!",
                font=ctk.CTkFont(size=12),
                text_color=("gray50", "#9ca3af"),
            ).pack(anchor="w", pady=10)
        else:
            for job in recent_jobs:
                row = ctk.CTkFrame(self.jobs_container, fg_color=("gray85", "#1e1e2d"), corner_radius=8)
                row.pack(fill="x", pady=4)

                status_color = "#10b981" if job.status == JobStatus.COMPLETED else "#60a5fa"
                if job.status == JobStatus.FAILED:
                    status_color = "#ef4444"

                lbl = ctk.CTkLabel(
                    row,
                    text=f"[{job.platform}] {job.title} ({job.total_tracks} tracks)",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    anchor="w",
                )
                lbl.pack(side="left", padx=12, pady=8)

                st_lbl = ctk.CTkLabel(
                    row,
                    text=job.status.value,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=status_color,
                )
                st_lbl.pack(side="right", padx=12, pady=8)
