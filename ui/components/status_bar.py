"""
StatusBar component for the application.

Displays global library metrics, download progress, source health,
and system status messages in a modern, streamlined footer.
"""

from typing import Any
import tkinter as tk
import customtkinter as ctk

from ui import theme


class StatusBar(ctk.CTkFrame):
    """Bottom status bar displaying global runtime status and metrics."""

    def __init__(self, master: Any, **kwargs):
        super().__init__(
            master,
            height=34,
            corner_radius=0,
            fg_color=theme.BG_HEADER,
            **kwargs
        )
        self.grid_columnconfigure(3, weight=1)
        self.grid_propagate(False)

        # 1. Total & Downloaded stats label
        self.stats_var = tk.StringVar(value="📚 Library: 0 total · 0 downloaded")
        self.stats_label = ctk.CTkLabel(
            self,
            textvariable=self.stats_var,
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_SECONDARY,
            fg_color="transparent",
        )
        self.stats_label.grid(row=0, column=0, padx=(16, 16), pady=4, sticky="w")

        # 2. Source health status
        self.sources_var = tk.StringVar(value="🟢 Sources: Operational")
        self.sources_label = ctk.CTkLabel(
            self,
            textvariable=self.sources_var,
            font=theme.font_caption(),
            text_color=theme.SUCCESS,
            fg_color="transparent",
        )
        self.sources_label.grid(row=0, column=1, padx=(0, 16), pady=4, sticky="w")

        # 3. Downloads / Speed
        self.dl_var = tk.StringVar(value="📥 Downloads: Idle")
        self.dl_label = ctk.CTkLabel(
            self,
            textvariable=self.dl_var,
            font=theme.font_caption(),
            text_color=theme.INFO,
            fg_color="transparent",
        )
        self.dl_label.grid(row=0, column=2, padx=(0, 16), pady=4, sticky="w")

        # 4. Main message string
        self.msg_var = tk.StringVar(value="Ready · Add music via URL or discover Tamil tracks.")
        self.msg_label = ctk.CTkLabel(
            self,
            textvariable=self.msg_var,
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="e",
            fg_color="transparent",
        )
        self.msg_label.grid(row=0, column=3, padx=(16, 16), pady=4, sticky="e")

    def update_stats(self, total: int, owned: int, healthy_sources: str, active_dl: int) -> None:
        """Update metrics in status bar."""
        self.stats_var.set(f"📚 Library: {total:,} songs · {owned:,} downloaded")
        if "3/3" in healthy_sources or "All" in healthy_sources:
            self.sources_var.set("🟢 Sources: Operational")
            self.sources_label.configure(text_color=theme.SUCCESS)
        else:
            self.sources_var.set(f"🟡 Sources: {healthy_sources}")
            self.sources_label.configure(text_color=theme.WARNING)

        if active_dl > 0:
            self.dl_var.set(f"📥 Downloads: {active_dl} active")
            self.dl_label.configure(text_color=theme.INFO)
        else:
            self.dl_var.set("📥 Downloads: Idle")
            self.dl_label.configure(text_color=theme.TEXT_MUTED)

    def set_message(self, message: str) -> None:
        """Set contextual footer message."""
        self.msg_var.set(message)
