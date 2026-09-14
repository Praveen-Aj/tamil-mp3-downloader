"""
Comprehensive Help and User Guide View.
Explains URL imports, audio providers, match confidence, library deduplication,
troubleshooting, and legal responsibility.
"""

import customtkinter as ctk


class HelpView(ctk.CTkFrame):
    """
    User help and documentation center within the application.
    """

    HELP_SECTIONS = [
        (
            "🚀 Getting Started",
            "Welcome to Tamil MP3 Downloader!\n\n"
            "The application functions as a modern music downloader and canonical library manager:\n"
            "1. Click '+ Add Music' in the sidebar or paste a link in the input bar.\n"
            "2. Click 'Analyze URL'. The application will identify the platform and resolve the tracks.\n"
            "3. Review the tracks, match confidence scores, and sources.\n"
            "4. Click 'Download Ready Tracks' to start fetching audio into your library."
        ),
        (
            "🔗 Adding a Song or Playlist",
            "You can paste URLs from supported streaming platforms:\n\n"
            "• Spotify: Tracks, albums, and public playlists (e.g. open.spotify.com/playlist/...)\n"
            "• YouTube: Single videos, music videos, and playlists (youtube.com/playlist?list=...)\n"
            "• YouTube Music: Direct song links and albums (music.youtube.com/...)\n"
            "• Tamil Music Sites: Direct album links from MassTamilan, TamilMP3, etc.\n"
            "• Direct Audio: Any direct link ending in .mp3, .m4a, or .wav.\n\n"
            "Note: Spotify URLs do not provide MP3 files directly. The app extracts canonical metadata from Spotify "
            "and automatically matches and acquires the best audio stream from configured audio providers."
        ),
        (
            "🎯 Understanding Matches & Confidence",
            "When analyzing a track, the engine computes a multi-factor match score based on:\n"
            "• Title similarity (token overlap and sequence distance)\n"
            "• Artist and channel uploader matching\n"
            "• Duration similarity (|delta| <= 8 seconds)\n\n"
            "Confidence Tiers:\n"
            "• HIGH CONFIDENCE (>= 82%): Audio matches title and duration closely. Automatically ready to download.\n"
            "• MEDIUM CONFIDENCE (60% - 81%): Suggested match, review recommended.\n"
            "• LOW CONFIDENCE (< 60%): Weak match, possible alternate or live version.\n"
            "• NO SOURCE: No audio stream found matching the requested track."
        ),
        (
            "🌐 Audio Providers & Fallback",
            "The application utilizes pluggable audio providers:\n"
            "1. YouTube / YouTube Music (powered by yt-dlp)\n"
            "2. Tamil Regional Sources (MassTamilan, TamilMP3, FriendsTamilMP3)\n"
            "3. Direct HTTP Audio Streams\n\n"
            "If a primary source fails during download, the engine automatically attempts the next best candidate."
        ),
        (
            "📚 Canonical Library & Deduplication",
            "Every song is registered into a local SQLite database using canonical normalization. "
            "If a song is already present in your library at equal or higher quality, the system marks it as "
            "'OWNED' and skips re-downloading to save bandwidth and prevent duplicate files on disk."
        ),
        (
            "⬆️ Quality Upgrades",
            "If you own a song at 128 kbps and a verified 320 kbps source becomes available, "
            "the system flags it as an 'Upgrade Available'. Downloading the upgrade replaces the lower-quality file "
            "and updates your library tags automatically."
        ),
        (
            "🛠️ Troubleshooting & FFmpeg",
            "• FFmpeg missing: If FFmpeg is not installed on your system, YouTube audio will be downloaded in its "
            "native format (.m4a or .webm) without conversion errors. To enable high-bitrate MP3 conversion, install "
            "FFmpeg and add it to your Windows PATH.\n"
            "• Rate Limiting / 429: If a platform temporarily slows down requests, wait a minute and click 'Retry Failed Only'.\n"
            "• Private Playlists: Ensure your Spotify or YouTube playlist privacy is set to 'Public' or 'Unlisted'."
        ),
        (
            "⚖️ Privacy & Legal Notice",
            "Tamil MP3 Downloader does not operate central servers or collect telemetry. "
            "All downloads and library records remain strictly on your local device.\n\n"
            "This software is provided for personal archival, educational, and backup purposes. Users are solely "
            "responsible for verifying they have the appropriate rights and permissions for any content downloaded, "
            "and for complying with applicable platform terms of service and copyright laws."
        ),
    ]

    def __init__(self, master: ctk.CTkFrame, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=25, pady=(20, 10))

        lbl_title = ctk.CTkLabel(
            header,
            text="❓ HELP & USER GUIDE",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=("gray10", "#f3f4f6"),
        )
        lbl_title.pack(side="left")

        lbl_sub = ctk.CTkLabel(
            header,
            text="Comprehensive guide to downloading, providers, and library management.",
            font=ctk.CTkFont(size=13),
            text_color=("gray50", "#9ca3af"),
        )
        lbl_sub.pack(side="left", padx=15, pady=(4, 0))

        # Scrollable content area
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=25, pady=(0, 20))
        scroll.grid_columnconfigure(0, weight=1)

        for idx, (title, content) in enumerate(self.HELP_SECTIONS):
            card = ctk.CTkFrame(scroll, fg_color=("gray90", "#181824"), corner_radius=10)
            card.pack(fill="x", pady=8, padx=5)

            card_title = ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color=("gray10", "#60a5fa"),
                anchor="w",
            )
            card_title.pack(fill="x", padx=18, pady=(14, 6))

            card_body = ctk.CTkLabel(
                card,
                text=content,
                font=ctk.CTkFont(size=13),
                text_color=("gray30", "#d1d5db"),
                justify="left",
                anchor="w",
                wraplength=950,
            )
            card_body.pack(fill="x", padx=18, pady=(0, 14))
