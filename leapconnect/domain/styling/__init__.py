"""Vehicle appearance / theming domain.

Factory exterior colour palettes per model and helpers to match a vehicle's
reported colour (or an extracted image colour) to a palette entry, plus the
map tile provider selection. Pure stdlib so it stays importable from the
application layer without side effects.
"""

from leapconnect.domain.styling.map_tiles import (
    DEFAULT_MAP_TILE_PROVIDER,
    MAP_TILE_KEYED_PROVIDERS,
    MAP_TILE_PROVIDERS,
    MapTileSettings,
    map_tile_settings_error,
    sanitize_map_tile_settings,
)
from leapconnect.domain.styling.palettes import (
    PaletteColor,
    hex_to_rgb,
    match_color_name,
    nearest_color,
    palette_for_car_type,
)

__all__ = [
    "DEFAULT_MAP_TILE_PROVIDER",
    "MAP_TILE_KEYED_PROVIDERS",
    "MAP_TILE_PROVIDERS",
    "MapTileSettings",
    "PaletteColor",
    "hex_to_rgb",
    "map_tile_settings_error",
    "match_color_name",
    "nearest_color",
    "palette_for_car_type",
    "sanitize_map_tile_settings",
]
