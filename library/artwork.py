"""
Tamil MP3 Downloader — Core Artwork Management & Caching Subsystem.

Provides high-performance, non-blocking artwork loading with:
1. Multi-tier caching: In-memory LRU cache + Persistent SHA256 disk cache.
2. Local MP3 ID3 embedded artwork extraction (mutagen APIC).
3. Resilient remote HTTP/HTTPS image fetching with timeout and size guards.
4. High-quality resampling (Pillow Lanczos).
5. Procedural modern gradient/fallback generation for offline or missing covers.
"""

from typing import Optional, Tuple, Dict, Any, Callable
import hashlib
import io
import logging
import os
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Optional Mutagen support for ID3 APIC frame extraction
try:
    import mutagen
    from mutagen.id3 import ID3, APIC
    HAVE_MUTAGEN = True
except ImportError:
    HAVE_MUTAGEN = False

# Default directories
CACHE_DIR = Path("cache") / "artwork"
DEFAULT_MEMORY_CAPACITY = 250
DEFAULT_DISK_MAX_MB = 150

# Modern Design Palette for Fallbacks
FALLBACK_PALETTES = {
    "movie": [("#1e1b4b", "#4338ca"), ("#311042", "#701a75"), ("#172554", "#1d4ed8")],
    "artist": [("#0f172a", "#334155"), ("#1c1917", "#44403c"), ("#18181b", "#3f3f46")],
    "chart": [("#3b0764", "#7e22ce"), ("#4a044e", "#a21caf"), ("#1e1b4b", "#4f46e5")],
    "playlist": [("#042f2e", "#0f766e"), ("#083344", "#0e7490"), ("#172554", "#2563eb")],
    "song": [("#18181b", "#27272a"), ("#0f172a", "#1e293b"), ("#1e1b4b", "#312e81")],
}


class ArtworkDiskCache:
    """Persistent on-disk cache for raw image bytes, indexed by SHA256 hash."""

    def __init__(self, cache_dir: Optional[Path] = None, max_size_mb: int = DEFAULT_DISK_MAX_MB):
        self.cache_dir = Path(cache_dir or CACHE_DIR)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = threading.Lock()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _hash_key(self, key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def get_path(self, key: str) -> Path:
        return self.cache_dir / f"{self._hash_key(key)}.png"

    def has(self, key: str) -> bool:
        path = self.get_path(key)
        return path.exists() and path.stat().st_size > 0

    def read_image(self, key: str) -> Optional[Image.Image]:
        path = self.get_path(key)
        if not path.exists():
            return None
        try:
            with self._lock:
                with Image.open(path) as img:
                    return img.convert("RGBA")
        except Exception as exc:
            logger.debug(f"Failed to read disk cached image for {key}: {exc}")
            return None

    def save_image(self, key: str, image: Image.Image) -> None:
        path = self.get_path(key)
        try:
            with self._lock:
                image.save(path, format="PNG", optimize=True)
            self._prune_if_needed()
        except Exception as exc:
            logger.debug(f"Failed to save disk cached image for {key}: {exc}")

    def save_raw_bytes(self, key: str, data: bytes) -> Optional[Image.Image]:
        try:
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            self.save_image(key, img)
            return img
        except Exception as exc:
            logger.debug(f"Failed to decode and save raw bytes for {key}: {exc}")
            return None

    def _prune_if_needed(self) -> None:
        """Evict oldest accessed files if disk cache exceeds quota."""
        try:
            total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.png"))
            if total_size <= self.max_size_bytes:
                return

            files = sorted(self.cache_dir.glob("*.png"), key=lambda f: f.stat().st_atime)
            for f in files:
                if total_size <= self.max_size_bytes * 0.8:
                    break
                sz = f.stat().st_size
                try:
                    f.unlink()
                    total_size -= sz
                except OSError:
                    pass
        except Exception as exc:
            logger.debug(f"Disk cache pruning error: {exc}")


class ArtworkMemoryCache:
    """Thread-safe LRU in-memory cache for scaled PIL Images."""

    def __init__(self, capacity: int = DEFAULT_MEMORY_CAPACITY):
        self.capacity = capacity
        self._cache: OrderedDict[Tuple[str, int, int], Image.Image] = OrderedDict()
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: str, width: int, height: int) -> Optional[Image.Image]:
        cache_key = (key, width, height)
        with self._lock:
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                self.hits += 1
                return self._cache[cache_key]
            self.misses += 1
            return None

    def put(self, key: str, width: int, height: int, image: Image.Image) -> None:
        cache_key = (key, width, height)
        with self._lock:
            if cache_key in self._cache:
                self._cache.move_to_end(cache_key)
                self._cache[cache_key] = image
                return
            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)
                self.evictions += 1
            self._cache[cache_key] = image

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


class ArtworkFallbackGenerator:
    """Generates procedural, aesthetically styled gradient placeholders."""

    @staticmethod
    def generate(
        text: Optional[str] = None,
        size: Tuple[int, int] = (64, 64),
        entity_type: str = "song",
    ) -> Image.Image:
        w, h = max(16, size[0]), max(16, size[1])
        palettes = FALLBACK_PALETTES.get(entity_type, FALLBACK_PALETTES["song"])
        
        seed = sum(ord(c) for c in (text or entity_type))
        color_start, color_end = palettes[seed % len(palettes)]

        def hex_to_rgb(h_str: str) -> Tuple[int, int, int]:
            h_str = h_str.lstrip("#")
            return tuple(int(h_str[i:i+2], 16) for i in (0, 2, 4))

        r1, g1, b1 = hex_to_rgb(color_start)
        r2, g2, b2 = hex_to_rgb(color_end)

        img = Image.new("RGBA", (w, h))
        draw = ImageDraw.Draw(img)

        for y in range(h):
            ratio = y / max(1, h - 1)
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            draw.line([(0, y), (w, y)], fill=(r, g, b, 255))

        draw.rectangle([(0, 0), (w - 1, h - 1)], outline=(255, 255, 255, 24), width=1)

        initials = ""
        if text:
            words = text.strip().split()
            if len(words) >= 2:
                initials = (words[0][0] + words[1][0]).upper()
            elif words:
                initials = words[0][:2].upper()

        if not initials:
            glyph_map = {
                "movie": "🎬",
                "artist": "👤",
                "chart": "🔥",
                "playlist": "📑",
                "song": "🎵",
            }
            initials = glyph_map.get(entity_type, "🎵")

        font_size = max(10, min(w, h) // 3)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("segoeui.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), initials, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (w - tw) // 2 - bbox[0]
        ty = (h - th) // 2 - bbox[1]

        draw.text((tx + 1, ty + 1), initials, font=font, fill=(0, 0, 0, 140))
        draw.text((tx, ty), initials, font=font, fill=(248, 250, 252, 225))

        return img


class ArtworkManager:
    """
    Central manager for loading, decoding, caching, and serving artwork across
    all entity types with high-performance background execution.
    """

    _instance: Optional["ArtworkManager"] = None
    _singleton_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ArtworkManager":
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        memory_capacity: int = DEFAULT_MEMORY_CAPACITY,
        max_workers: int = 4,
    ):
        self.disk_cache = ArtworkDiskCache(cache_dir=cache_dir)
        self.memory_cache = ArtworkMemoryCache(capacity=memory_capacity)
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ArtworkLoader")
        self._in_flight: Dict[Tuple[str, int, int], list] = {}
        self._flight_lock = threading.Lock()

    def get_artwork(
        self,
        source: Optional[str],
        size: Tuple[int, int] = (64, 64),
        entity_type: str = "song",
        fallback_text: Optional[str] = None,
    ) -> Image.Image:
        """
        Synchronous load: Checks memory -> disk -> remote/local -> fallback generator.
        Always returns a valid PIL Image.
        """
        w, h = size
        key = (source or "").strip()

        if not key:
            return ArtworkFallbackGenerator.generate(text=fallback_text, size=size, entity_type=entity_type)

        # 1. Check Memory Cache
        cached_img = self.memory_cache.get(key, w, h)
        if cached_img:
            return cached_img

        # 2. Check Disk Cache
        disk_img = self.disk_cache.read_image(key)
        if disk_img:
            scaled = self._scale_image(disk_img, size)
            self.memory_cache.put(key, w, h, scaled)
            return scaled

        # 3. Fetch from Remote URL or Local File
        loaded_img = self._load_from_source(key)
        if loaded_img:
            self.disk_cache.save_image(key, loaded_img)
            scaled = self._scale_image(loaded_img, size)
            self.memory_cache.put(key, w, h, scaled)
            return scaled

        # 4. Generate Procedural Fallback
        fallback = ArtworkFallbackGenerator.generate(text=fallback_text or key, size=size, entity_type=entity_type)
        self.memory_cache.put(key, w, h, fallback)
        return fallback

    def load_artwork_async(
        self,
        source: Optional[str],
        size: Tuple[int, int] = (64, 64),
        entity_type: str = "song",
        fallback_text: Optional[str] = None,
        callback: Optional[Callable[[Image.Image], None]] = None,
    ) -> None:
        """
        Asynchronously fetches and decodes artwork, calling callback(image) on completion.
        If already in memory cache, invokes callback immediately without worker dispatch.
        """
        w, h = size
        key = (source or "").strip()

        if key:
            cached = self.memory_cache.get(key, w, h)
            if cached:
                if callback:
                    callback(cached)
                return

        cache_tuple = (key, w, h)
        with self._flight_lock:
            if cache_tuple in self._in_flight:
                if callback:
                    self._in_flight[cache_tuple].append(callback)
                return
            self._in_flight[cache_tuple] = [callback] if callback else []

        def _worker():
            try:
                img = self.get_artwork(
                    source=source,
                    size=size,
                    entity_type=entity_type,
                    fallback_text=fallback_text,
                )
            except Exception as exc:
                logger.debug(f"Error in artwork worker for {source}: {exc}")
                img = ArtworkFallbackGenerator.generate(text=fallback_text or source, size=size, entity_type=entity_type)

            with self._flight_lock:
                callbacks = self._in_flight.pop(cache_tuple, [])

            for cb in callbacks:
                try:
                    cb(img)
                except Exception as exc:
                    logger.debug(f"Error in artwork callback: {exc}")

        self.executor.submit(_worker)

    def extract_from_audio_file(self, audio_path: str) -> Optional[Image.Image]:
        """Extract embedded ID3 cover art frame from an audio file."""
        p = Path(audio_path)
        if not p.exists() or p.suffix.lower() != ".mp3":
            return None

        if not HAVE_MUTAGEN:
            return None

        try:
            id3 = ID3(str(p))
            for tag in id3.values():
                if isinstance(tag, APIC):
                    img = Image.open(io.BytesIO(tag.data)).convert("RGBA")
                    return img
        except Exception as exc:
            logger.debug(f"Could not extract APIC frame from {audio_path}: {exc}")
        return None

    def _load_from_source(self, source: str) -> Optional[Image.Image]:
        """Resolves source as local audio file, local image file, or remote URL."""
        if source.lower().endswith(".mp3") and os.path.exists(source):
            return self.extract_from_audio_file(source)

        if os.path.exists(source) and os.path.isfile(source):
            try:
                with Image.open(source) as img:
                    return img.convert("RGBA")
            except Exception:
                return None

        if source.startswith(("http://", "https://")):
            return self._fetch_remote_url(source)

        return None

    def _fetch_remote_url(self, url: str) -> Optional[Image.Image]:
        try:
            import requests
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200 and len(resp.content) > 100:
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                return img
        except Exception as exc:
            logger.debug(f"Failed to fetch remote artwork {url}: {exc}")
        return None

    def _scale_image(self, image: Image.Image, size: Tuple[int, int]) -> Image.Image:
        """Scales image with high quality Lanczos resampling preserving aspect ratio or fill."""
        target_w, target_h = size
        if image.size == (target_w, target_h):
            return image
        
        img_w, img_h = image.size
        scale = max(target_w / img_w, target_h / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        right = left + target_w
        bottom = top + target_h
        
        return resized.crop((left, top, right, bottom))

    def get_stats(self) -> Dict[str, Any]:
        """Returns runtime performance statistics."""
        return {
            "memory_cache_hits": self.memory_cache.hits,
            "memory_cache_misses": self.memory_cache.misses,
            "memory_cache_evictions": self.memory_cache.evictions,
            "disk_cache_dir": str(self.disk_cache.cache_dir),
            "disk_cache_entries": len(list(self.disk_cache.cache_dir.glob("*.png"))),
        }
