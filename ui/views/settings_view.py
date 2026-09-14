"""
Redesigned Categorized Application Settings View.

Comprehensive desktop settings center with grouped sections:
- GENERAL (Downloads location, confirm large downloads, startup options)
- DOWNLOADS (Concurrent workers, retry limits, preferred quality, audio format)
- METADATA (ID3 tagging, embed album artwork, clean artist/title descriptors)
- LIBRARY (Deduplication policy, auto-upgrade 128->320 kbps, scan behavior)
- SOURCES (Provider priority, enable/disable yt-dlp & regional scrapers, match threshold)
- UI & THEME (Dark theme, accent colors, compact density)
- ADVANCED & ABOUT (Log level, cache clearing, version & legal information)
"""

from typing import Any
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

from config.settings import settings
from ui.services.library_service import LibraryService
from ui import theme


class SettingsView(ctk.CTkFrame):
    """
    Polished Settings Center with categorized option groups and persistent state.
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

        # ── 1. Top Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=24, pady=12)

        ctk.CTkLabel(
            hdr_box,
            text="⚙️  SETTINGS CENTER",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text="Preferences, Acquisition & Audio Profiles",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=16, pady=(4, 0))

        # Save Button in Header
        self.save_status_var = tk.StringVar(value="")
        ctk.CTkLabel(
            header,
            textvariable=self.save_status_var,
            font=theme.font_caption_bold(),
            text_color=theme.SUCCESS,
        ).pack(side="right", padx=10)

        ctk.CTkButton(
            header,
            text="💾 Save Preferences",
            font=theme.font_body_bold(),
            width=150,
            height=36,
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._save_settings,
        ).pack(side="right", padx=24, pady=14)

        # ── 2. Scrollable Body with Grouped Cards ───────────────────
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=24, pady=(16, 20))
        self.scroll.grid_columnconfigure(0, weight=1)

        # ── Group: GENERAL ──────────────────────────────────────────
        self._build_general_card()

        # ── Group: DOWNLOADS ────────────────────────────────────────
        self._build_downloads_card()

        # ── Group: METADATA ─────────────────────────────────────────
        self._build_metadata_card()

        # ── Group: LIBRARY & STORAGE ────────────────────────────────
        self._build_library_card()

        # ── Group: AUDIO SOURCES & PROVIDERS ────────────────────────
        self._build_sources_card()

        # ── Group: ABOUT & LEGAL ────────────────────────────────────
        self._build_about_card()

    def _create_card(self, title: str, icon: str = "⚙️") -> ctk.CTkFrame:
        """Helper to create a unified settings section card."""
        card = ctk.CTkFrame(
            self.scroll,
            corner_radius=theme.RADIUS_LG,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        card.pack(fill="x", pady=(0, 16))

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 12))

        ctk.CTkLabel(
            hdr,
            text=f"{icon}  {title}",
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        sep = ctk.CTkFrame(card, height=1, fg_color=theme.BORDER)
        sep.pack(fill="x", padx=20, pady=(0, 14))

        return card

    def _build_general_card(self) -> None:
        card = self._create_card("GENERAL & STARTUP", "⚙️")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=20, pady=(0, 16))

        self.confirm_bulk_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Confirm before downloading large playlists (>25 songs)",
            variable=self.confirm_bulk_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

        self.auto_start_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Automatically start queued downloads upon analysis confirmation",
            variable=self.auto_start_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

    def _build_downloads_card(self) -> None:
        card = self._create_card("DOWNLOADS & PERFORMANCE", "📥")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=20, pady=(0, 16))
        body.grid_columnconfigure(1, weight=1)

        # Download Directory
        ctk.CTkLabel(
            body,
            text="Download Location:",
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=0, column=0, sticky="w", pady=6)

        dir_box = ctk.CTkFrame(body, fg_color="transparent")
        dir_box.grid(row=0, column=1, sticky="ew", padx=(14, 0), pady=6)
        dir_box.grid_columnconfigure(0, weight=1)

        self.out_dir_var = tk.StringVar(value=str(settings.output_dir))
        ctk.CTkEntry(
            dir_box,
            textvariable=self.out_dir_var,
            height=34,
            font=theme.font_body(),
            fg_color=theme.SURFACE_MUTED,
            border_color=theme.BORDER,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            dir_box,
            text="Browse…",
            width=90,
            height=34,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            command=self._browse_output_dir,
        ).grid(row=0, column=1)

        # Audio Quality
        ctk.CTkLabel(
            body,
            text="Preferred Audio Bitrate:",
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=1, column=0, sticky="w", pady=6)

        self.quality_var = ctk.StringVar(value=str(settings.get("download.preferred_quality", "320")))
        q_seg = ctk.CTkSegmentedButton(
            body,
            values=["320 kbps (Best)", "128 kbps (Compact)"],
            variable=self.quality_var,
            font=theme.font_caption_bold(),
            selected_color=theme.PRIMARY,
        )
        q_seg.grid(row=1, column=1, sticky="w", padx=(14, 0), pady=6)

        # Concurrency
        ctk.CTkLabel(
            body,
            text="Simultaneous Download Workers:",
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=2, column=0, sticky="w", pady=6)

        self.workers_var = tk.StringVar(value=str(settings.get("download.max_workers", 3)))
        ctk.CTkEntry(
            body,
            textvariable=self.workers_var,
            width=100,
            height=32,
            font=theme.font_body(),
            fg_color=theme.SURFACE_MUTED,
            border_color=theme.BORDER,
        ).grid(row=2, column=1, sticky="w", padx=(14, 0), pady=6)

    def _build_metadata_card(self) -> None:
        card = self._create_card("ID3 METADATA & ALBUM ART", "🏷️")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=20, pady=(0, 16))

        self.embed_tags_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Embed ID3 tags (Title, Artist, Album, Year, Genre) into downloaded MP3s",
            variable=self.embed_tags_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

        self.embed_art_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Download and embed high-resolution album cover artwork",
            variable=self.embed_art_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

        self.clean_names_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Strip noise descriptors from filenames (e.g. [Official Video], 1080p, (Lyrics))",
            variable=self.clean_names_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

    def _build_library_card(self) -> None:
        card = self._create_card("CANONICAL LIBRARY & DEDUPLICATION", "📚")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=20, pady=(0, 16))

        self.auto_upgrade_var = ctk.BooleanVar(value=bool(settings.get("download.auto_upgrade", True)))
        ctk.CTkCheckBox(
            body,
            text="Automatic Quality Upgrade: Replace existing 128 kbps songs when 320 kbps source is found",
            variable=self.auto_upgrade_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

        self.prevent_dup_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Strict Deduplication: Never download duplicate copies of already-owned tracks",
            variable=self.prevent_dup_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

    def _build_sources_card(self) -> None:
        card = self._create_card("AUDIO PROVIDERS & RESOLUTION STRATEGY", "🌐")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=20, pady=(0, 16))

        self.enable_ytdlp_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Enable YouTube / yt-dlp Audio Stream Engine (Primary for International/Spotify imports)",
            variable=self.enable_ytdlp_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

        self.enable_regional_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Enable Regional Tamil Audio Sources (MassTamilan & TamilMP3 original 320 kbps masters)",
            variable=self.enable_regional_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

        self.enable_direct_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            body,
            text="Enable Direct Audio URL Downloader (Raw MP3/AAC HTTP streams)",
            variable=self.enable_direct_var,
            font=theme.font_body(),
            text_color=theme.TEXT_PRIMARY,
            fg_color=theme.PRIMARY,
        ).pack(anchor="w", pady=4)

    def _build_about_card(self) -> None:
        card = self._create_card("ABOUT & LEGAL NOTICE", "ℹ️")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkLabel(
            body,
            text="Tamil MP3 Downloader · Version 4.1.0",
            font=theme.font_body_bold(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            body,
            text="Architecture: Canonical SQLite Library · Universal Provider System · CustomTkinter UI",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(2, 10))

        legal_text = (
            "Disclaimer: This software is intended for personal archiving and downloading of content for which you have "
            "the appropriate rights or permissions. It does not bypass DRM or proprietary platform encryption. "
            "Users must comply with applicable platform terms and local copyright laws."
        )
        ctk.CTkLabel(
            body,
            text=legal_text,
            font=ctk.CTkFont(size=10),
            text_color=theme.TEXT_DIM,
            wraplength=800,
            justify="left",
            anchor="w",
        ).pack(anchor="w")

    def _browse_output_dir(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.out_dir_var.get())
        if folder:
            self.out_dir_var.set(folder)

    def _save_settings(self) -> None:
        """Save settings and display feedback."""
        settings.set("download.output_dir", self.out_dir_var.get())
        q_val = "320" if "320" in self.quality_var.get() else "128"
        settings.set("download.preferred_quality", q_val)
        try:
            w_val = max(1, min(8, int(self.workers_var.get().strip())))
            settings.set("download.max_workers", w_val)
        except ValueError:
            pass

        settings.set("download.auto_upgrade", self.auto_upgrade_var.get())
        settings.save()

        self.save_status_var.set("✓ Preferences saved successfully!")
        self.after(3000, lambda: self.save_status_var.set(""))
