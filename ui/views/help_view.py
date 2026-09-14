"""
Help & User Guide View.

Consumer-oriented desktop help center answering real end-user questions:
- How do I download a song or Spotify playlist?
- Why did my download fail and how do I retry?
- Why does this song need review?
- How do I download multiple songs at once?
- Where are my downloaded songs stored?
- How do I delete a downloaded song?
- Category filter pills and expandable question cards
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
            "category": "Downloading",
            "icon": "⚡",
            "title": "How do I download a song or Spotify playlist?",
            "content": (
                "1. Click '+ Add Music' in the navigation bar or Dashboard.\n\n"
                "2. Paste any supported song, album, or playlist link (Spotify, YouTube, or direct MP3 audio URL).\n\n"
                "3. Click '⚡ Analyze URL'. The app will detect the tracks and find the best audio matches.\n\n"
                "4. In the Playlist Results screen, review the track list and click '📥 Download Selected' to save high-quality MP3s to your computer."
            ),
        },
        {
            "category": "Troubleshooting",
            "icon": "🔄",
            "title": "Why did my download fail and how do I fix it?",
            "content": (
                "• Source Unavailable: A remote audio server or video may be temporarily offline or restricted.\n\n"
                "• Automatic Alternate Fallback: When you click '🔄 Retry', the app automatically tries secondary providers (such as alternative regional archives or audio sources).\n\n"
                "• Network Timeouts: If your internet connection was interrupted, click '🔄 Retry' on the download card.\n\n"
                "• Find Another Source: Click '🔍 Find Source' on the card to paste an alternative URL."
            ),
        },
        {
            "category": "Review Matches",
            "icon": "🎯",
            "title": "Why does a song recommend review?",
            "content": (
                "• Match Confidence: When extracting tracks from playlists, the engine compares song titles, artists, and movie names.\n\n"
                "• High Confidence (85–100%): Verified match, ready for one-click downloading.\n\n"
                "• Review Recommended (70–84%): The track might have a slight title variation, remix, or multiple singers. Click '🔍 Review Match' to inspect details before downloading.\n\n"
                "• Audio Preview: You can click '▶ Preview' to listen to a short audio clip before saving."
            ),
        },
        {
            "category": "Library & Files",
            "icon": "📁",
            "title": "Where are my downloaded songs stored?",
            "content": (
                "• Default Location: Songs are saved into your configured 'Downloads' folder in high-quality 320 kbps MP3 format.\n\n"
                "• Open Directly: Click '📁 Open Folder' on any completed card in Downloads or Music Library to open Windows Explorer with the file highlighted.\n\n"
                "• Change Folder: You can customize the download location in Settings -> Download Location."
            ),
        },
        {
            "category": "Library & Files",
            "icon": "🗑️",
            "title": "How do I delete a downloaded song?",
            "content": (
                "• From Downloads: Click '🗑️ Delete' on any completed download card.\n\n"
                "• From Music Library: Select the song and click '🗑️ Delete', or use '🗑️ Delete Selected' for bulk deletion.\n\n"
                "• Safety Confirmation: The app will always ask for your confirmation before deleting physical audio files from your disk."
            ),
        },
        {
            "category": "Bulk & Playlists",
            "icon": "📑",
            "title": "How do I download multiple songs at once?",
            "content": (
                "• Select All: In the Playlist Results or Music Library screen, click 'Select All' or check individual song checkboxes.\n\n"
                "• Download Selected: Click '⬇ Download Selected' to queue all selected tracks for parallel background downloading.\n\n"
                "• Safe Resilient Downloading: A failure on one track will not cancel the rest of your playlist."
            ),
        },
        {
            "category": "Audio Quality",
            "icon": "🎧",
            "title": "How do I ensure the highest audio quality (320 kbps)?",
            "content": (
                "• Preferred Bitrate: Under Settings, ensure 'Preferred Audio Bitrate' is set to 320 kbps.\n\n"
                "• Quality Upgrades: If you previously downloaded a 128 kbps version and a 320 kbps master is discovered, the app flags a Quality Upgrade available in your library.\n\n"
                "• ID3 Tags & Art: The app embeds title, artist, album, and artwork metadata into every MP3."
            ),
        },
        {
            "category": "Legal",
            "icon": "⚖️",
            "title": "Legal Responsibility & Copyright Disclaimer",
            "content": (
                "Tamil MP3 Downloader is an open-source software utility designed for personal archiving, backup, and fair use of music for which the user possesses valid access rights.\n\n"
                "This application does not circumvent digital rights management (DRM) or platform access controls. Users are strictly responsible for ensuring compliance with copyright laws and platform terms of service."
            ),
        },
    ]
    HELP_SECTIONS = TOPICS

    def __init__(self, master: Any, **kwargs):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self._active_category = "All"
        self._expanded_indices = {0, 1}

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            hdr_box,
            text="❓  HELP & USER GUIDE",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text="Frequently Asked Questions & How-To Guides",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=14, pady=(2, 0))

        # ── 2. Category Filter Pills ────────────────────────────────
        cat_bar = ctk.CTkFrame(self, fg_color="transparent")
        cat_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(10, 8))

        categories = ["All", "Downloading", "Troubleshooting", "Review Matches", "Library & Files", "Bulk & Playlists", "Audio Quality"]
        self._cat_buttons: Dict[str, ctk.CTkButton] = {}

        for cat in categories:
            btn = ctk.CTkButton(
                cat_bar,
                text=cat,
                font=theme.font_caption_bold(),
                height=28,
                fg_color=theme.PRIMARY if cat == "All" else theme.SURFACE_ELEVATED,
                hover_color=theme.SURFACE_HOVER,
                text_color=theme.TEXT_PRIMARY,
                corner_radius=theme.RADIUS_SM,
                command=lambda c=cat: self._filter_category(c),
            )
            btn.pack(side="left", padx=2)
            self._cat_buttons[cat] = btn

        # ── 3. Scrollable Cards Container ───────────────────────────
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 12))
        self.scroll.grid_columnconfigure(0, weight=1)

        self._render_topics()

    def _filter_category(self, cat: str) -> None:
        self._active_category = cat
        for c, btn in self._cat_buttons.items():
            if c == cat:
                btn.configure(fg_color=theme.PRIMARY, text_color=theme.TEXT_PRIMARY)
            else:
                btn.configure(fg_color=theme.SURFACE_ELEVATED, text_color=theme.TEXT_SECONDARY)
        self._render_topics()

    def _render_topics(self) -> None:
        for w in self.scroll.winfo_children():
            w.destroy()

        filtered = [
            (idx, t) for idx, t in enumerate(self.TOPICS)
            if self._active_category == "All" or t["category"] == self._active_category
        ]

        for idx, item in filtered:
            is_open = (idx in self._expanded_indices)

            card = ctk.CTkFrame(
                self.scroll,
                corner_radius=theme.RADIUS_MD,
                fg_color=theme.SURFACE,
                border_width=1,
                border_color=theme.BORDER,
            )
            card.pack(fill="x", pady=4)

            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=16, pady=10)

            icon_lbl = ctk.CTkLabel(hdr, text=item["icon"], font=ctk.CTkFont(size=15))
            icon_lbl.pack(side="left", padx=(0, 8))

            title_lbl = ctk.CTkLabel(
                hdr,
                text=item["title"],
                font=theme.font_subtitle(),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            )
            title_lbl.pack(side="left", fill="x", expand=True)

            arrow_txt = "▲" if is_open else "▼"
            toggle_btn = ctk.CTkButton(
                hdr,
                text=arrow_txt,
                width=28,
                height=24,
                font=ctk.CTkFont(size=10),
                fg_color=theme.SURFACE_ELEVATED,
                hover_color=theme.SURFACE_HOVER,
                text_color=theme.TEXT_SECONDARY,
                command=lambda i=idx: self._toggle_expand(i),
            )
            toggle_btn.pack(side="right")

            if is_open:
                sep = ctk.CTkFrame(card, height=1, fg_color=theme.BORDER)
                sep.pack(fill="x", padx=16, pady=(0, 8))

                body = ctk.CTkFrame(card, fg_color="transparent")
                body.pack(fill="x", padx=16, pady=(0, 12))

                ctk.CTkLabel(
                    body,
                    text=item["content"],
                    font=theme.font_body(),
                    text_color=theme.TEXT_SECONDARY,
                    justify="left",
                    anchor="w",
                    wraplength=850,
                ).pack(fill="x")

    def _toggle_expand(self, idx: int) -> None:
        if idx in self._expanded_indices:
            self._expanded_indices.remove(idx)
        else:
            self._expanded_indices.add(idx)
        self._render_topics()
