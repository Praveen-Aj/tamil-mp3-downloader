"""
Dashboard view (Phase 2).

Displays high-value library metrics:
- Total canonical songs
- Owned songs
- Unowned songs
- Upgrades available
- Active downloads
- Failed downloads
- Latest discovery session summary
- Quick Action buttons
"""

from typing import Dict, Any, Callable, Optional
import tkinter as tk
import customtkinter as ctk

from ui.services.library_service import LibraryService


class DashboardView(ctk.CTkFrame):
    """
    Overview Dashboard displaying core library health and quick actions.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_navigate: Callable[[str], None],
        **kwargs,
    ):
        super().__init__(master, corner_radius=0, **kwargs)
        self.service = service
        self.on_navigate = on_navigate

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Title Header ──────────────────────────────────────────────
        header = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#181824")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="📊  Dashboard Overview",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffffff",
        ).pack(side="left", padx=16, pady=10)

        # Refresh button
        ctk.CTkButton(
            header,
            text="🔄 Refresh",
            width=90,
            height=30,
            command=self.refresh,
        ).pack(side="right", padx=16, pady=10)

        # ── Content Scroll Area ───────────────────────────────────────
        self.scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        self.scroll.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # ── KPI Cards Container ───────────────────────────────────────
        self._card_vars: Dict[str, tk.StringVar] = {}
        self._build_kpi_cards()

        # ── Discovery Session & Download Health Row ───────────────────
        self.middle_frame = ctk.CTkFrame(self.scroll, corner_radius=6, fg_color="#1c1c2e")
        self.middle_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(16, 12))
        self.middle_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.middle_frame,
            text="LATEST DISCOVERY SESSION",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#90caf9",
        ).pack(anchor="w", padx=16, pady=(12, 6))

        self.session_var = tk.StringVar(value="No discovery session run in this application session yet.")
        ctk.CTkLabel(
            self.middle_frame,
            textvariable=self.session_var,
            font=ctk.CTkFont(size=11),
            text_color="#d0d0d0",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

        # ── Quick Actions Panel ───────────────────────────────────────
        actions_frame = ctk.CTkFrame(self.scroll, corner_radius=6, fg_color="#1c1c2e")
        actions_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=6)

        ctk.CTkLabel(
            actions_frame,
            text="QUICK ACTIONS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffb74d",
        ).pack(anchor="w", padx=16, pady=(12, 8))

        btn_container = ctk.CTkFrame(actions_frame, fg_color="transparent")
        btn_container.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(
            btn_container,
            text="🔍 Discover Songs",
            width=140,
            height=36,
            command=lambda: self.on_navigate("discover"),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_container,
            text="📚 Open Library",
            width=140,
            height=36,
            command=lambda: self.on_navigate("library"),
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_container,
            text="📥 Active Queue",
            width=140,
            height=36,
            command=lambda: self.on_navigate("downloads"),
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_container,
            text="🌐 Source Health",
            width=140,
            height=36,
            command=lambda: self.on_navigate("sources"),
        ).pack(side="left", padx=8)

        self.refresh()

    def _build_kpi_cards(self) -> None:
        cards_data = [
            ("total_songs", "Total Songs", "#60a5fa"),
            ("owned_songs", "Owned Songs", "#4ade80"),
            ("unowned_songs", "Unowned Songs", "#fbbf24"),
            ("upgrades_available", "Upgrades Available", "#c084fc"),
        ]

        for i, (key, title, color) in enumerate(cards_data):
            card = ctk.CTkFrame(self.scroll, corner_radius=6, fg_color="#1c1c2e")
            card.grid(row=0, column=i, sticky="nsew", padx=4, pady=4)

            ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=11), text_color="#aaaaaa"
            ).pack(anchor="w", padx=12, pady=(12, 4))

            var = tk.StringVar(value="0")
            self._card_vars[key] = var

            ctk.CTkLabel(
                card,
                textvariable=var,
                font=ctk.CTkFont(size=24, weight="bold"),
                text_color=color,
            ).pack(anchor="w", padx=12, pady=(0, 12))

    def refresh(self) -> None:
        """Fetch updated stats from LibraryService."""
        stats = self.service.get_dashboard_stats()

        self._card_vars["total_songs"].set(f"{stats.get('total_songs', 0):,}")
        self._card_vars["owned_songs"].set(f"{stats.get('owned_songs', 0):,}")
        self._card_vars["unowned_songs"].set(f"{stats.get('unowned_songs', 0):,}")
        self._card_vars["upgrades_available"].set(f"{stats.get('upgrades_available', 0):,}")

        sess = stats.get("last_session")
        health_info = f"Source Status: {stats.get('healthy_sources', 'N/A')} ({stats.get('disabled_sources', 0)} Disabled)"

        if sess:
            self.session_var.set(
                f"{health_info}\n"
                f"Category: {sess.get('category')}\n"
                f"Raw Discovered: {sess.get('raw_discovered'):,}  |  "
                f"Unique Registered: {sess.get('unique_registered'):,}  |  "
                f"Duplicates Collapsed: {sess.get('duplicates_filtered'):,}"
            )
        else:
            self.session_var.set(f"{health_info}\nNo discovery session run yet in this application session.")
