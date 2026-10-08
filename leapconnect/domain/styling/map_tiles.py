"""Map base-layer (tile provider) selection.

The dashboard maps load raster tiles straight from the chosen provider, so
this only models *which* provider is active, the per-provider API keys and
the user's own URL templates; the URL catalog lives in the frontend.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_MAP_TILE_PROVIDER = "osm"

# Every provider the frontend knows how to draw.
MAP_TILE_PROVIDERS = (
    "osm",
    "carto",
    "maptiler",
    "stadia",
    "esri_imagery",
    "custom",
)

# Providers that take an API key: required ones refuse to load without it,
# Stadia also works key-less once the domain is registered on its dashboard.
MAP_TILE_KEYED_PROVIDERS = ("carto", "maptiler", "stadia")
MAP_TILE_KEY_REQUIRED = ("carto", "maptiler")

_TILE_PLACEHOLDERS = ("{z}", "{x}", "{y}")
_URL_SCHEME = re.compile(r"^https?://", re.IGNORECASE)


@dataclass
class MapTileSettings:
    """Active map provider, its API keys and the custom URL templates."""

    provider: str = DEFAULT_MAP_TILE_PROVIDER
    api_keys: dict[str, str] = field(default_factory=dict)
    custom_url: str = ""  # light (or only) template
    custom_dark_url: str = ""  # optional dark template


def is_valid_tile_url(url: str) -> bool:
    """Whether ``url`` is an http(s) Leaflet template with ``{z}/{x}/{y}``."""
    return bool(_URL_SCHEME.match(url)) and all(p in url for p in _TILE_PLACEHOLDERS)


def map_tile_settings_error(settings: MapTileSettings) -> str | None:
    """Return why ``settings`` can't draw a map, or ``None`` when usable."""
    if settings.provider not in MAP_TILE_PROVIDERS:
        return f"Unknown map provider: {settings.provider}"
    if settings.provider in MAP_TILE_KEY_REQUIRED and not settings.api_keys.get(
        settings.provider
    ):
        return f"An API key is required for {settings.provider}"
    if settings.provider == "custom" and not is_valid_tile_url(settings.custom_url):
        return "Custom URL must start with http(s):// and contain {z}, {x} and {y}"
    if settings.custom_dark_url and not is_valid_tile_url(settings.custom_dark_url):
        return "Custom dark URL must start with http(s):// and contain {z}, {x} and {y}"
    return None


def sanitize_map_tile_settings(settings: MapTileSettings) -> MapTileSettings:
    """Drop unknown/empty keys and fall back to OSM if the stored row is stale."""
    api_keys = {
        k: v.strip()
        for k, v in settings.api_keys.items()
        if k in MAP_TILE_KEYED_PROVIDERS and isinstance(v, str) and v.strip()
    }
    custom_url = settings.custom_url.strip()
    custom_dark_url = settings.custom_dark_url.strip()
    clean = MapTileSettings(
        provider=settings.provider,
        api_keys=api_keys,
        custom_url=custom_url if is_valid_tile_url(custom_url) else "",
        custom_dark_url=custom_dark_url if is_valid_tile_url(custom_dark_url) else "",
    )
    if map_tile_settings_error(clean):
        clean.provider = DEFAULT_MAP_TILE_PROVIDER
    return clean
