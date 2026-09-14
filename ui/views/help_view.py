"""
Help & User Guide View.

Interactive desktop help center with:
- Visual step-by-step workflow guide
- Category filter pills (Getting Started, Sources, Playlists, Troubleshooting, FAQ)
- Expandable question/topic cards
- Troubleshooting diagnostic guides (FFmpeg, rate limits, private playlists)
- Legal & copyright responsibility notice
"""

from typing import Dict, List, Tuple, Any, Optional
import tkinter as tk
import customtkinter as ctk

from ui import theme


class HelpView(ctk.CTkFrame):
    """
    Consumer-friendly Help & Documentation Center.
    """

    TOPICS: List[Dict[str, Any]] = [
        {
            "category": "Getting Started",
            "icon": "🚀",
            "title": "Quick Start: 5-Step Music Acquisition",
            "content": (
                "1. Add a URL: Click '+ Add Music' in the navigation bar and paste a song, album, or playlist link.\n\n"
                "2. Analyze: Click '⚡ Analyze URL'. The engine will detect the platform, fetch track metadata, and search audio providers.\n\n"
                "3. Select Songs: In the Playlist Result UI, review match confidence scores and check the songs you want.\n\n"
                "4. Download: Click '📥 Download Selected' to start fetching audio in the background.\n\n"
                "5. Find Your Music: Downloaded tracks are automatically tagged, artwork is embedded, and files are organized into your local library directory."
            ),
        },
        {
            "category": "Supported Sources",
            "icon": "🔗",
            "title": "Supported URL Formats & Platforms",
            "content": (
                "• Spotify Playlists & Tracks (open.spotify.com/playlist/... or /track/...)\n"
                "  Public playlists and tracks are analyzed token-free. Canonical metadata is extracted, and audio is sourced via YouTube or regional scrapers.\n\n"
                "• YouTube Videos & Music (youtube.com/watch?v=... or music.youtube.com/...)\n"
                "  Direct high-quality audio extraction powered by yt-dlp.\n\n"
                "• YouTube Playlists (youtube.com/playlist?list=...)\n"
                "  Fast flat enumeration of full playlists with individual track selection.\n\n"
                "• Regional Tamil Sites (MassTamilan, TamilMP3, FriendsTamilMP3)\n"
                "  Original 320 kbps regional album masters and movie soundtrack packages.\n\n"
                "• Direct Audio Streams (HTTP/HTTPS URLs ending in .mp3, .m4a, or .wav)\n"
                "  Direct streaming and download with byte-range resume support."
            ),
        },
        {
            "category": "Playlists",
            "icon": "📑",
            "title": "Downloading Large Playlists & Partial Failures",
            "content": (
                "• Safe Resilient Downloading: A single failing or unavailable video will never cancel an entire playlist.\n\n"
                "• Match Confidence Tiers:\n"
                "  - HIGH (>= 85%): Preselected and ready for one-click downloading.\n"
                "  - MEDIUM (65% - 84%): Suggested candidate, flagged for quick review.\n"
                "  - LOW (< 65%): Excluded from automatic queue to prevent wrong track downloads.\n\n"
                "• Retry Failed Tracks: Use the '🔄 Retry Failed' button in Downloads Manager to re-attempt failed items with alternate providers."
            ),
        },
        {
            "category": "Library",
            "icon": "📚",
            "title": "Library Organization & Deduplication",
            "content": (
                "• Canonical Normalization: Tracks are fingerprinted based on clean title and artist tokens.\n\n"
                "• Zero Duplicates: If a track is already in your library, the system marks it as '✓ Already in Library' and skips re-downloading.\n\n"
                "• Quality Upgrades: If you have a 128 kbps copy and a 320 kbps master is found, the system flags a Quality Upgrade Available."
            ),
        },
        {
            "category": "Troubleshooting",
            "icon": "🛠️",
            "title": "Common Issues & Troubleshooting Guide",
            "content": (
                "• URL Cannot be Analyzed: Ensure the playlist or video is set to 'Public' or 'Unlisted'. Private playlists cannot be read.\n\n"
                "• FFmpeg Warning: If FFmpeg is missing from your Windows PATH, audio is saved in native .m4a or .webm. To enable pristine 320 kbps MP3 conversion, install FFmpeg.\n\n"
                "• Video Blocked or Region Restricted: The engine will automatically attempt secondary providers (Regional Tamil scraper or Direct stream).\n\n"
                "• Network Timeouts / 429 Rate Limiting: Streaming platforms may temporarily throttle heavy traffic. Wait 60 seconds and click 'Retry Failed'."
            ),
        },
        {
            "category": "FAQ",
            "icon": "❓",
            "title": "Frequently Asked Questions",
            "content": (
                "Q: Does this app download directly from Spotify?\n"
                "A: No. Spotify does not provide downloadable MP3 files. The app reads Spotify metadata for track names and resolves high-quality audio through authorized providers like YouTube or regional archives.\n\n"
                "Q: Can I import my existing offline MP3 folder?\n"
                "A: Yes! Go to Library -> '📂 Import Existing Files'. The app will index your files into SQLite without duplicating them."
            ),
        },
        {
            "category": "Legal",
            "icon": "⚖️",
            "title": "Legal Responsibility & Copyright Disclaimer",
            "content": (
                "Tamil MP3 Downloader is an open-source software utility designed for personal archiving, backup, and fair use of content for which the user possesses valid access rights.\n\n"
                "This application does not circumvent digital rights management (DRM) or platform access controls. Users are strictly responsible for ensuring compliance with copyright laws and platform terms of service."
            ),
        },
    ]
    HELP_SECTIONS = TOPICS


    def __init__(self, master: Any, **kwargs):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self._active_category = "All"
        self._expanded_indices = {0, 1}  # Open first two by default

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=24, pady=12)

        ctk.CTkLabel(
            hdr_box,
            text="❓  HELP & USER GUIDE",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text="Documentation, Platform Rules & Troubleshooting",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=16, pady=(4, 0))

        # ── 2. Category Filter Pills ────────────────────────────────
        nav_bar = ctk.CTkFrame(
            self,
            corner_radius=theme.RADIUS_LG,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        nav_bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(16, 12))

        nav_inner = ctk.CTkFrame(nav_bar, fg_color="transparent")
        nav_inner.pack(fill="x", padx=16, pady=8)

        categories = ["All", "Getting Started", "Supported Sources", "Playlists", "Library", "Troubleshooting", "FAQ", "Legal"]
        self._cat_buttons = {}

        for cat in categories:
            btn = ctk.CTkButton(
                nav_inner,
                text=cat,
                font=theme.font_caption_bold(),
                height=30,
                width=80 if cat == "All" else 110,
                fg_color=theme.PRIMARY if cat == "All" else theme.SURFACE_ELEVATED,
                hover_color=theme.SURFACE_HOVER,
                text_color=theme.TEXT_PRIMARY,
                corner_radius=theme.RADIUS_SM,
                command=lambda c=cat: self._set_category(c),
            )
            btn.pack(side="left", padx=3)
            self._cat_buttons[cat] = btn

        # ── 3. Scrollable Help Content ──────────────────────────────
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        self.scroll.grid_columnconfigure(0, weight=1)

        self._render_topics()

    def _set_category(self, cat: str) -> None:
        self._active_category = cat
        for c_name, btn in self._cat_buttons.items():
            if c_name == cat:
                btn.configure(fg_color=theme.PRIMARY, text_color=theme.TEXT_PRIMARY)
            else:
                btn.configure(fg_color=theme.SURFACE_ELEVATED, text_color=theme.TEXT_SECONDARY)
        self._render_topics()

    def _render_topics(self) -> None:
        for w in self.scroll.winfo_children():
            w.destroy()

        filtered = [
            t for t in self.TOPICS
            if self._active_category == "All" or t["category"] == self._active_category
        ]

        for idx, topic in enumerate(filtered):
            card = ctk.CTkFrame(
                self.scroll,
                corner_radius=theme.RADIUS_MD,
                fg_color=theme.SURFACE,
                border_width=1,
                border_color=theme.BORDER,
            )
            card.pack(fill="x", pady=5)

            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=18, pady=12)

            # Icon & Title
            left_hdr = ctk.CTkFrame(hdr, fg_color="transparent")
            left_hdr.pack(side="left")

            ctk.CTkLabel(left_hdr, text=topic["icon"], font=ctk.CTkFont(size=18)).pack(side="left", padx=(0, 10))

            ctk.CTkLabel(
                left_hdr,
                text=topic["title"],
                font=theme.font_subtitle(),
                text_color=theme.TEXT_PRIMARY,
            ).pack(side="left")

            # Category chip
            ctk.CTkLabel(
                hdr,
                text=topic["category"],
                font=theme.font_badge(),
                fg_color=theme.SURFACE_ELEVATED,
                text_color=theme.PRIMARY_LIGHT,
                corner_radius=6,
                padx=8,
                pady=2,
            ).pack(side="right")

            # Body text
            body = ctk.CTkFrame(card, fg_color=theme.SURFACE_MUTED, corner_radius=theme.RADIUS_SM)
            body.pack(fill="x", padx=18, pady=(0, 14))

            ctk.CTkLabel(
                body,
                text=topic["content"],
                font=theme.font_body(),
                text_color=theme.TEXT_SECONDARY,
                justify="left",
                anchor="w",
                wraplength=850,
            ).pack(padx=16, pady=14, anchor="w")
