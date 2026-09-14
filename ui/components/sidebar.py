"""
Sidebar Navigation Component for CustomTkinter.
"""

from typing import Callable, Dict
import customtkinter as ctk


class SidebarNav(ctk.CTkFrame):
    """Sidebar navigation panel."""

    def __init__(
        self,
        master: ctk.CTk,
        on_view_change: Callable[[str], None],
        **kwargs
    ):
        super().__init__(master, width=220, corner_radius=0, **kwargs)
        self.on_view_change = on_view_change
        self._buttons: Dict[str, ctk.CTkButton] = {}

        # App Logo / Title
        self.logo_label = ctk.CTkLabel(
            self,
            text="🎵 TAMIL MP3\nDOWNLOADER",
            font=ctk.CTkFont(size=18, weight="bold"),
            justify="center"
        )
        self.logo_label.pack(padx=20, pady=(20, 20))

        # Nav Buttons
        nav_items = [
            ("dashboard", "📊  Dashboard"),
            ("add_music", "➕  Add Music"),
            ("library", "📚  Library"),
            ("discover", "🔍  Discover"),
            ("results", "🎯  Review Results"),
            ("downloads", "📥  Downloads Queue"),
            ("sources", "🌐  Source Health"),
            ("settings", "⚙️  Settings"),
            ("help", "❓  Help & Guide"),
            ("import", "📁  Import Local Files"),
        ]

        for view_key, label in nav_items:
            btn = ctk.CTkButton(
                self,
                text=label,
                anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30"),
                height=40,
                font=ctk.CTkFont(size=13),
                command=lambda k=view_key: self._handle_click(k),
            )
            btn.pack(fill="x", padx=10, pady=3)
            self._buttons[view_key] = btn

    def _handle_click(self, view_key: str) -> None:
        self.set_active(view_key)
        self.on_view_change(view_key)

    def set_active(self, active_key: str) -> None:
        """Highlight active navigation button."""
        for key, btn in self._buttons.items():
            if key == active_key:
                btn.configure(
                    fg_color=("gray75", "#252538"),
                    text_color=("blue", "#64b5f6"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("gray10", "gray90"),
                )
