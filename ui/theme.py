"""
Tamil MP3 Downloader — Centralized Design System & Theme.

Provides consistent color tokens, semantic palettes, typography tokens,
and layout metrics across all CustomTkinter views and components.
"""

import customtkinter as ctk

# ── Color Palette ─────────────────────────────────────────────────────────────
# Deep modern dark palette (obsidian / navy tint instead of flat grey)
BG_APP = "#0c0d14"          # Main application background
BG_SIDEBAR = "#11131c"      # Sidebar navigation background
BG_HEADER = "#151724"       # Top header / status bar background

# Card & Surface Hierarchy
SURFACE = "#161826"          # Default card / section surface
SURFACE_ELEVATED = "#1e2133" # Elevated cards, hover containers, popups
SURFACE_HOVER = "#23273a"    # Card hover / button hover
SURFACE_ACTIVE = "#262b42"   # Active / focused item background
SURFACE_MUTED = "#131420"    # Inset areas, code blocks, dark inputs

# Borders & Separators
BORDER = "#24283b"           # Subtle container border
BORDER_LIGHT = "#323752"     # Focused / highlighted border
BORDER_ACCENT = "#6366f1"    # Active accent border

# Primary & Secondary Brand Accents
PRIMARY = "#6366f1"          # Modern Indigo primary brand color
PRIMARY_HOVER = "#4f46e5"    # Primary hover
PRIMARY_MUTED = "#312e81"    # Primary subtle background container
PRIMARY_LIGHT = "#a5b4fc"    # Primary text highlight

SECONDARY = "#3b82f6"        # Vibrant Blue
SECONDARY_HOVER = "#2563eb"
SECONDARY_MUTED = "#1e3a8a"

ACCENT_CYAN = "#06b6d4"      # Cyan for links, streams, audio chips
ACCENT_PURPLE = "#8b5cf6"    # Purple for special indicators

# Semantic Status Colors
SUCCESS = "#10b981"          # Emerald Green (Completed, Owned, Operational)
SUCCESS_BG = "#064e3b"
SUCCESS_LIGHT = "#6ee7b7"

WARNING = "#f59e0b"          # Amber / Orange (Needs Review, Degraded)
WARNING_BG = "#78350f"
WARNING_LIGHT = "#fcd34d"

ERROR = "#ef4444"            # Rose / Red (Failed, Unavailable)
ERROR_BG = "#7f1d1d"
ERROR_LIGHT = "#fca5a5"

INFO = "#38bdf8"             # Sky Blue (Downloading, Pending)
INFO_BG = "#0c4a6e"
INFO_LIGHT = "#bae6fd"

# Typography Colors
TEXT_PRIMARY = "#f8fafc"     # Highest contrast white/slate
TEXT_SECONDARY = "#cbd5e1"   # Soft readable text
TEXT_MUTED = "#94a3b8"       # Secondary labels, captions, metadata
TEXT_DIM = "#64748b"         # De-emphasized timestamps, hashes, icons
TEXT_DISABLED = "#475569"    # Disabled controls

# ── Radii & Metrics ───────────────────────────────────────────────────────────
RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14
RADIUS_XL = 18

# ── Typography Tokens (Factory Callers) ────────────────────────────────────────
def font_hero() -> ctk.CTkFont:
    return ctk.CTkFont(size=22, weight="bold")

def font_title() -> ctk.CTkFont:
    return ctk.CTkFont(size=17, weight="bold")

def font_subtitle() -> ctk.CTkFont:
    return ctk.CTkFont(size=14, weight="bold")

def font_body() -> ctk.CTkFont:
    return ctk.CTkFont(size=13)

def font_body_bold() -> ctk.CTkFont:
    return ctk.CTkFont(size=13, weight="bold")

def font_caption() -> ctk.CTkFont:
    return ctk.CTkFont(size=11)

def font_caption_bold() -> ctk.CTkFont:
    return ctk.CTkFont(size=11, weight="bold")

def font_badge() -> ctk.CTkFont:
    return ctk.CTkFont(size=10, weight="bold")
