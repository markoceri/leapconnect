"""Vehicle appearance / theming domain.

Factory exterior colour palettes per model and helpers to match a vehicle's
reported colour (or an extracted image colour) to a palette entry. Pure
stdlib so it stays importable from the application layer without side effects.
"""

from leapconnect.domain.styling.palettes import (
    PaletteColor,
    hex_to_rgb,
    match_color_name,
    nearest_color,
    palette_for_car_type,
)

__all__ = [
    "PaletteColor",
    "hex_to_rgb",
    "match_color_name",
    "nearest_color",
    "palette_for_car_type",
]
