"""
StatusBar component for the application.

Displays summary stats, active download status, source health, and contextual status messages.
"""

from typing import Dict, Any, Optional
import tkinter as tk
import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    """Bottom status bar displaying global runtime status and metrics."""

    def __init__(self, master: Any, **kwargs):
        super().__init__(master, height=36, corner_radius=0, fg_color="#181824", **kwargs)
        self.grid_columnconfigure(3, weight=1)
        self.grid_propagate(False)

        # 1. Total & Owned stats label
        self.stats_var = tk.StringVar(value="Library: 0 total | 0 owned")
        self.stats_label = ctk.CTkLabel(
            self,
            textvariable=self.stats_var,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#a0aab8",
            fg_color="transparent",
        )
        self.stats_label.grid(row=0, column=0, padx=(12, 16), pady=6, sticky="w")

        # 2. Source health status
        self.sources_var = tk.StringVar(value="Sources: 3/3 Healthy")
        self.sources_label = ctk.CTkLabel(
            self,
            textvariable=self.sources_var,
            font=ctk.CTkFont(size=11),
            text_color="#4caf50",
            fg_color="transparent",
        )
        self.sources_label.grid(row=0, column=1, padx=(0, 16), pady=6, sticky="w")

        # 3. Downloads / Speed
        self.dl_var = tk.StringVar(value="Downloads: Idle")
        self.dl_label = ctk.CTkLabel(
            self,
            textvariable=self.dl_var,
            font=ctk.CTkFont(size=11),
            text_color="#64b5f6",
            fg_color="transparent",
        )
        self.dl_label.grid(row=0, column=2, padx=(0, 16), pady=6, sticky="w")

        # 4. Main message string
        self.msg_var = tk.StringVar(value="Ready — SQLite Canonical Library active.")
        self.msg_label = ctk.CTkLabel(
            self,
            textvariable=self.msg_var,
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            anchor="e",
            fg_color="transparent",
        )
        self.msg_label.grid(row=0, column=3, padx=(16, 12), pady=6, sticky="e")

    def update_stats(self, total: int, owned: int, healthy_sources: str, active_dl: int) -> None:
        """Update metrics in status bar."""
        self.stats_var.set(f"Library: {total:,} total | {owned:,} owned")
        self.sources_var.set(f"Sources: {healthy_sources}")
        if active_dl > 0:
            self.dl_var.set(f"Downloads: {active_dl} active")
        else:
            self.dl_var.set("Downloads: Idle")

    def set_message(self, message: str) -> None:
        """Set message string."""
        self.msg_var.set(message)
