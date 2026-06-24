"""Extract a vehicle's dominant body colour from its picture.

Used as a fallback for accent auto-detection when the cloud-reported
``out_color`` text does not match a known palette entry. Kept in the
application layer because it depends on Pillow (not stdlib-pure).
"""

from __future__ import annotations

import io
import logging
from collections import Counter

from PIL import Image

_LOGGER = logging.getLogger(__name__)

# Pixels darker/brighter than these are very likely glass, tyres, shadows or
# specular highlights/background — not the body paint — so they are excluded
# from the dominant-colour vote when enough mid-tone pixels remain.
_DARK_CUTOFF = 45
_LIGHT_CUTOFF = 235


def _count(pixels: list[tuple[int, int, int]]) -> Counter[tuple[int, int, int]]:
    counts: Counter[tuple[int, int, int]] = Counter()
    for r, g, b in pixels:
        # Quantise to 16-step buckets and key by the bucket centre.
        counts[(r & 0xF0, g & 0xF0, b & 0xF0)] += 1
    return counts


def dominant_color(image_bytes: bytes) -> tuple[int, int, int] | None:
    """Return the dominant body ``(r, g, b)`` of an image.

    Transparent pixels (background) are ignored. Near-black (windows, tyres,
    shadow) and near-white (highlights) pixels are filtered out so the actual
    paint wins the vote — falling back to all opaque pixels only when too few
    mid-tone pixels remain (e.g. a genuinely black or white car). Returns
    ``None`` when the image cannot be read or has no usable pixels.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    except (OSError, ValueError) as exc:
        _LOGGER.warning("Could not read vehicle image for colour detection: %s", exc)
        return None

    img.thumbnail((96, 96))
    data = img.tobytes()  # flat RGBA bytes

    opaque: list[tuple[int, int, int]] = []
    midtone: list[tuple[int, int, int]] = []
    for i in range(0, len(data), 4):
        if data[i + 3] < 200:  # alpha — skip transparent background
            continue
        r, g, b = data[i], data[i + 1], data[i + 2]
        opaque.append((r, g, b))
        peak = max(r, g, b)
        trough = min(r, g, b)
        if peak >= _DARK_CUTOFF and trough <= _LIGHT_CUTOFF:
            midtone.append((r, g, b))

    if not opaque:
        return None

    # Use mid-tones when they cover a meaningful share of the car; otherwise the
    # vehicle really is very dark or very light, so fall back to everything.
    pixels = midtone if len(midtone) >= max(20, len(opaque) // 10) else opaque

    br, bg, bb = _count(pixels).most_common(1)[0][0]
    return (br + 8, bg + 8, bb + 8)
