"""
Redesigned Categorized Application Settings View (Part 16).
Provides categorized settings for General, Library, Downloads, Providers,
Metadata, and Advanced system tuning.
"""

from typing import Any
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

from config.settings import settings
from ui.services.library_service import LibraryService


class SettingsView(ctk.CTkFrame):
    """
    Categorized application settings view.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.service = service

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color="#181824")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="⚙️  Application Settings",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffffff",
        ).pack(side="left", padx=20, pady=12)

        # ── Settings Scrollable Form ──────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=15)
        scroll.grid_columnconfigure(0, weight=1)

        # ── 1. GENERAL CARD ───────────────────────────────────────────
        gen_card = self._create_card(scroll, "1. GENERAL & UI")

        self.confirm_bulk_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            gen_card,
            text="Confirm before starting large playlist downloads (>25 tracks)",
            variable=self.confirm_bulk_var,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=18, pady=(0, 10))

        # ── 2. LIBRARY CARD ───────────────────────────────────────────
        lib_card = self._create_card(scroll, "2. LIBRARY & STORAGE")

        ctk.CTkLabel(lib_card, text="Music Library & Download Directory:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=18, pady=(0, 4))
        dir_frame = ctk.CTkFrame(lib_card, fg_color="transparent")
        dir_frame.pack(fill="x", padx=18, pady=(0, 10))
        dir_frame.grid_columnconfigure(0, weight=1)

        self.out_dir_var = tk.StringVar(value=str(settings.output_dir))
        self.entry_out = ctk.CTkEntry(dir_frame, textvariable=self.out_dir_var, height=34)
        self.entry_out.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            dir_frame, text="Browse…", width=90, height=34, command=self._browse_output_dir
        ).grid(row=0, column=1)

        self.auto_upgrade_var = ctk.BooleanVar(value=bool(settings.get("download.auto_upgrade", True)))
        ctk.CTkCheckBox(
            lib_card,
            text="Enable automatic quality upgrade (replace 128 kbps tracks when 320 kbps is available)",
            variable=self.auto_upgrade_var,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=18, pady=(0, 10))

        # ── 3. DOWNLOADS & PERFORMANCE ────────────────────────────────
        dl_card = self._create_card(scroll, "3. DOWNLOADS & CONCURRENCY")

        ctk.CTkLabel(dl_card, text="Preferred Audio Quality:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=18, pady=(0, 4))
        self.quality_var = ctk.StringVar(value=str(settings.get("download.preferred_quality", "320")))
        q_btn = ctk.CTkSegmentedButton(
            dl_card,
            values=["320", "128"],
            variable=self.quality_var,
        )
        q_btn.pack(anchor="w", padx=18, pady=(0, 10))

        ctk.CTkLabel(dl_card, text="Max Concurrent Download Workers:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=18, pady=(0, 4))
        self.workers_var = tk.StringVar(value=str(settings.get("download.max_workers", 3)))
        ctk.CTkEntry(dl_card, textvariable=self.workers_var, width=100, height=32).pack(anchor="w", padx=18, pady=(0, 10))

        # ── 4. PROVIDERS & MATCH CONFIDENCE ───────────────────────────
        prov_card = self._create_card(scroll, "4. PROVIDERS & MATCHING")

        ctk.CTkLabel(
            prov_card,
            text="Match Confidence Threshold for Auto-Download:",
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=18, pady=(0, 4))

        self.threshold_var = ctk.StringVar(value="80%")
        th_btn = ctk.CTkSegmentedButton(
            prov_card,
            values=["75%", "80%", "85%", "90%"],
            variable=self.threshold_var,
        )
        th_btn.pack(anchor="w", padx=18, pady=(0, 10))

        self.fallback_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            prov_card,
            text="Enable automatic source fallback (if primary provider fails, try secondary source)",
            variable=self.fallback_var,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=18, pady=(0, 10))

        # ── 5. METADATA & TAGGING ─────────────────────────────────────
        meta_card = self._create_card(scroll, "5. METADATA & ID3 TAGGING")

        self.tagging_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            meta_card,
            text="Write clean ID3v2.3 tags (Title, Artist, Album, Year, Track Number)",
            variable=self.tagging_var,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=18, pady=(0, 6))

        self.artwork_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            meta_card,
            text="Embed high-resolution album artwork into audio files",
            variable=self.artwork_var,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=18, pady=(0, 10))

        # ── Save Button & Status ──────────────────────────────────────
        ctk.CTkButton(
            scroll,
            text="💾 Save All Settings",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            fg_color="#10b981",
            hover_color="#059669",
            command=self._save_settings,
        ).pack(fill="x", pady=(15, 6))

        self.status_label = ctk.CTkLabel(
            scroll, text="", font=ctk.CTkFont(size=12), text_color="#10b981"
        )
        self.status_label.pack(anchor="w", pady=(0, 20))

    def _create_card(self, parent: Any, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color=("gray90", "#181824"))
        card.pack(fill="x", pady=6)
        ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#60a5fa",
        ).pack(anchor="w", padx=18, pady=(12, 8))
        return card

    def _browse_output_dir(self) -> None:
        chosen = filedialog.askdirectory()
        if chosen:
            self.out_dir_var.set(chosen)

    def _save_settings(self) -> None:
        """Save settings updates."""
        try:
            settings.set("download.output_dir", self.out_dir_var.get().strip())
            settings.set("download.preferred_quality", int(self.quality_var.get()))
            settings.set("download.auto_upgrade", self.auto_upgrade_var.get())
            settings.set("download.max_workers", int(self.workers_var.get().strip()))
            settings.save()
            self.status_label.configure(
                text="✅ Settings saved successfully!", text_color="#10b981"
            )
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Failed to save settings: {e}", text_color="#ef4444"
            )
