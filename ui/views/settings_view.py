"""
Settings View (Phase 11).

Application settings configuration:
- Output directory
- Preferred audio quality (320 kbps vs 128 kbps)
- Auto-upgrade threshold
- Max concurrent download workers
- Downloader engine (HTTP / aria2)
"""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

from config.settings import settings
from ui.services.library_service import LibraryService


class SettingsView(ctk.CTkFrame):
    """
    Application Settings configuration view.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        **kwargs,
    ):
        super().__init__(master, corner_radius=0, **kwargs)
        self.service = service

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#181824")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="⚙️  Application Settings",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=16, pady=10)

        # ── Settings Form ─────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        scroll.grid_columnconfigure(0, weight=1)

        # 1. Output Directory Card
        out_card = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#1c1c2e")
        out_card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            out_card,
            text="1. DOWNLOAD OUTPUT DIRECTORY",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#90caf9",
        ).pack(anchor="w", padx=16, pady=(12, 6))

        dir_frame = ctk.CTkFrame(out_card, fg_color="transparent")
        dir_frame.pack(fill="x", padx=16, pady=(0, 12))
        dir_frame.grid_columnconfigure(0, weight=1)

        self.out_dir_var = tk.StringVar(value=str(settings.output_dir))
        self.entry_out = ctk.CTkEntry(dir_frame, textvariable=self.out_dir_var, height=32)
        self.entry_out.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            dir_frame, text="Browse…", width=90, height=32, command=self._browse_output_dir
        ).grid(row=0, column=1)

        # 2. Quality & Upgrade Options Card
        qual_card = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#1c1c2e")
        qual_card.pack(fill="x", pady=6)

        ctk.CTkLabel(
            qual_card,
            text="2. QUALITY & UPGRADE PREFERENCES",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ce93d8",
        ).pack(anchor="w", padx=16, pady=(12, 6))

        self.quality_var = ctk.StringVar(
            value=str(settings.get("download.preferred_quality", "320"))
        )
        ctk.CTkLabel(
            qual_card, text="Preferred Audio Quality:", font=ctk.CTkFont(size=11)
        ).pack(anchor="w", padx=20, pady=(4, 2))

        q_btn = ctk.CTkSegmentedButton(
            qual_card,
            values=["320", "128"],
            variable=self.quality_var,
        )
        q_btn.pack(anchor="w", padx=20, pady=(0, 8))

        self.auto_upgrade_var = ctk.BooleanVar(
            value=bool(settings.get("download.auto_upgrade", True))
        )
        ctk.CTkCheckBox(
            qual_card,
            text="Enable automatic quality upgrade (128 kbps → 320 kbps)",
            variable=self.auto_upgrade_var,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=20, pady=6)

        ctk.CTkLabel(qual_card, text="", height=4).pack()

        # 3. Downloader Engine & Worker Options Card
        engine_card = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#1c1c2e")
        engine_card.pack(fill="x", pady=6)

        ctk.CTkLabel(
            engine_card,
            text="3. DOWNLOAD ENGINE & CONCURRENCY",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#81c784",
        ).pack(anchor="w", padx=16, pady=(12, 6))

        self.workers_var = tk.StringVar(
            value=str(settings.get("download.max_workers", 3))
        )
        ctk.CTkLabel(
            engine_card, text="Max Concurrent Workers:", font=ctk.CTkFont(size=11)
        ).pack(anchor="w", padx=20, pady=(4, 2))

        ctk.CTkEntry(
            engine_card, textvariable=self.workers_var, width=100, height=30
        ).pack(anchor="w", padx=20, pady=(0, 8))

        # Save Button
        ctk.CTkButton(
            scroll,
            text="💾 Save Settings",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            fg_color="#1a6b3c",
            hover_color="#236b4a",
            command=self._save_settings,
        ).pack(fill="x", pady=(12, 6))

        self.status_label = ctk.CTkLabel(
            scroll, text="", font=ctk.CTkFont(size=11), text_color="#888888"
        )
        self.status_label.pack(anchor="w", pady=4)

    def _browse_output_dir(self) -> None:
        chosen = filedialog.askdirectory()
        if chosen:
            self.out_dir_var.set(chosen)

    def _save_settings(self) -> None:
        """Save settings updates."""
        try:
            settings.output_dir = Path(self.out_dir_var.get().strip())
            settings.set("download.preferred_quality", int(self.quality_var.get()))
            settings.set("download.auto_upgrade", self.auto_upgrade_var.get())
            settings.set("download.max_workers", int(self.workers_var.get().strip()))
            settings.save()
            self.status_label.configure(
                text="✅ Settings saved successfully!", text_color="#81c784"
            )
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Failed to save settings: {e}", text_color="#ef5350"
            )
