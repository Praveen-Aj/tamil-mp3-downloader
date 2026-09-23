"""
Tamil MP3 Downloader — GUI Artwork Service.

Bridges the background PIL artwork loader to CustomTkinter CTkImage objects.
Provides non-blocking widget binding, main-thread cache of CTkImages,
lifecycle safety (detects destroyed widgets), and seamless fallback gradients.
"""

from typing import Optional, Tuple, Dict, Any, Callable
import logging
import threading
from collections import OrderedDict
from PIL import Image
import customtkinter as ctk

from library.artwork import ArtworkManager, ArtworkFallbackGenerator

logger = logging.getLogger(__name__)


class ArtworkService:
    """
    GUI-facing artwork service for CustomTkinter views.
    Maintains a main-thread cache of CTkImage objects and coordinates async loading.
    """

    _instance: Optional["ArtworkService"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ArtworkService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self, manager: Optional[ArtworkManager] = None, max_ctk_images: int = 300):
        self.manager = manager or ArtworkManager.get_instance()
        self.max_ctk_images = max_ctk_images
        self._ctk_cache: OrderedDict[Tuple[str, int, int], ctk.CTkImage] = OrderedDict()
        self._cache_lock = threading.RLock()

    def get_ctk_image_sync(
        self,
        source: Optional[str],
        size: Tuple[int, int] = (64, 64),
        entity_type: str = "song",
        fallback_text: Optional[str] = None,
    ) -> ctk.CTkImage:
        """Synchronously retrieves or creates a CTkImage."""
        key = (source or "").strip()
        w, h = size
        cache_key = (f"{key}:{fallback_text}:{entity_type}", w, h)

        with self._cache_lock:
            if cache_key in self._ctk_cache:
                self._ctk_cache.move_to_end(cache_key)
                return self._ctk_cache[cache_key]

        # Get PIL Image
        pil_img = self.manager.get_artwork(
            source=source,
            size=size,
            entity_type=entity_type,
            fallback_text=fallback_text,
        )
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)

        with self._cache_lock:
            if len(self._ctk_cache) >= self.max_ctk_images:
                self._ctk_cache.popitem(last=False)
            self._ctk_cache[cache_key] = ctk_img

        return ctk_img

    def get_fallback_ctk_image(
        self,
        fallback_text: Optional[str],
        size: Tuple[int, int] = (64, 64),
        entity_type: str = "song",
    ) -> ctk.CTkImage:
        """Immediately generates a procedural fallback CTkImage."""
        w, h = size
        cache_key = (f"__fallback__:{fallback_text}:{entity_type}", w, h)
        with self._cache_lock:
            if cache_key in self._ctk_cache:
                self._ctk_cache.move_to_end(cache_key)
                return self._ctk_cache[cache_key]

        pil_img = ArtworkFallbackGenerator.generate(
            text=fallback_text,
            size=size,
            entity_type=entity_type,
        )
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        with self._cache_lock:
            if len(self._ctk_cache) >= self.max_ctk_images:
                self._ctk_cache.popitem(last=False)
            self._ctk_cache[cache_key] = ctk_img

        return ctk_img

    def bind_artwork(
        self,
        widget: Any,
        source: Optional[str],
        size: Tuple[int, int] = (64, 64),
        entity_type: str = "song",
        fallback_text: Optional[str] = None,
        on_loaded: Optional[Callable[[ctk.CTkImage], None]] = None,
    ) -> None:
        """
        Binds artwork to a widget (e.g. CTkLabel or CTkButton).
        Immediately sets a fast fallback image to avoid layout shift,
        then asynchronously fetches and applies the full artwork.
        """
        w, h = size
        key = (source or "").strip()
        cache_key = (f"{key}:{fallback_text}:{entity_type}", w, h)

        # 1. If already in memory cache, apply immediately
        with self._cache_lock:
            if cache_key in self._ctk_cache:
                img = self._ctk_cache[cache_key]
                self._apply_to_widget(widget, img)
                if on_loaded:
                    on_loaded(img)
                return

        # 2. Set instant procedural fallback placeholder
        fallback_img = self.get_fallback_ctk_image(
            fallback_text=fallback_text or key,
            size=size,
            entity_type=entity_type,
        )
        self._apply_to_widget(widget, fallback_img)

        # If no source URL/path was given, we are done with the fallback
        if not key:
            return

        # 3. Asynchronously load the real artwork
        def _on_pil_loaded(pil_img: Image.Image) -> None:
            # Safely marshal to Tkinter main thread
            try:
                if not widget.winfo_exists():
                    return
            except Exception:
                return

            def _main_thread_update():
                try:
                    if not widget.winfo_exists():
                        return
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
                    with self._cache_lock:
                        if len(self._ctk_cache) >= self.max_ctk_images:
                            self._ctk_cache.popitem(last=False)
                        self._ctk_cache[cache_key] = ctk_img

                    self._apply_to_widget(widget, ctk_img)
                    if on_loaded:
                        on_loaded(ctk_img)
                except Exception as exc:
                    logger.debug(f"Failed to apply loaded artwork to widget: {exc}")

            try:
                widget.after(0, _main_thread_update)
            except Exception:
                pass

        self.manager.load_artwork_async(
            source=source,
            size=size,
            entity_type=entity_type,
            fallback_text=fallback_text,
            callback=_on_pil_loaded,
        )

    def _apply_to_widget(self, widget: Any, image: ctk.CTkImage) -> None:
        """Safely updates widget image and clears text placeholder."""
        try:
            if not widget.winfo_exists():
                return
            widget.configure(image=image, text="")
        except Exception as exc:
            logger.debug(f"Could not configure widget with image: {exc}")

    def clear_cache(self) -> None:
        """Clears memory and CTkImage caches."""
        with self._cache_lock:
            self._ctk_cache.clear()
        self.manager.memory_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        stats = self.manager.get_stats()
        with self._cache_lock:
            stats["ctk_images_cached"] = len(self._ctk_cache)
        return stats
