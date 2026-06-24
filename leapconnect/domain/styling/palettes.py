"""Factory exterior colour palettes per Leapmotor model.

Colour names mirror the marketing names published on leapmotor.net; the hex
values are representative approximations chosen to read well as a UI accent,
since Leapmotor does not publish swatch hex codes. Each palette is keyed by the
canonical base model (T03/B10/C10) — variants (e.g. C10 REEV/BEV) share the
same exterior colours.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from leapconnect.domain.maintenance.resolver import MODEL_PATTERNS


@dataclass(frozen=True)
class PaletteColor:
    """A single named factory colour usable as a UI accent."""

    key: str  # stable slug, e.g. "mint-green"
    name: str  # marketing name, e.g. "Mint Green"
    hex: str  # accent hex, e.g. "#79cfae"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _palette(*pairs: tuple[str, str]) -> list[PaletteColor]:
    return [
        PaletteColor(key=_slug(name), name=name, hex=hex_.lower())
        for name, hex_ in pairs
    ]


# ---------------------------------------------------------------------------
# Palettes keyed by canonical base model
# ---------------------------------------------------------------------------
# Hex values are resampled approximations of the real factory paints (Leapmotor
# does not publish swatch hex codes); colour names and per-model availability
# follow the European configurator on leapmotor.net (FR/IT market).
MODEL_PALETTES: dict[str, list[PaletteColor]] = {
    # T03 EU (current): Bleu Caraïbes, Vert Menthe, Gris Canopée, Blanc Clair.
    "T03": _palette(
        ("Caribbean Blue", "#5fb0d6"),
        ("Mint Green", "#9fd9c0"),
        ("Canopy Grey", "#6c6f77"),
        ("Light White", "#eef0f1"),
    ),
    # B10 EU: Starry Night Blue, Dawn Purple, Tundra Grey, Galaxy Silver,
    # Light White, Metallic Black.
    "B10": _palette(
        ("Starry Night Blue", "#2b3a55"),
        ("Dawn Purple", "#8f88a4"),
        ("Tundra Grey", "#918d85"),
        ("Galaxy Silver", "#b7bcc2"),
        ("Light White", "#eef0f1"),
        ("Metallic Black", "#1d1f22"),
    ),
    # C10 EU: Gris Canopée, Vert Glacé, Gris Toundra, Blanc Nacré, Noir Métallique.
    "C10": _palette(
        ("Glazed Green", "#34564a"),
        ("Canopy Grey", "#6c6f77"),
        ("Tundra Grey", "#918d85"),
        ("Pearl White", "#eef0f1"),
        ("Metallic Black", "#1d1f22"),
    ),
}

# Fallback palette for unknown models — keeps the feature usable for any car.
DEFAULT_PALETTE: list[PaletteColor] = _palette(
    ("Cyan", "#00d4ff"),
    ("Mint Green", "#9fd9c0"),
    ("Dawn Purple", "#8f88a4"),
    ("Caribbean Blue", "#4fb1d6"),
    ("Glazed Green", "#34564a"),
    ("Light White", "#eef0f1"),
)


def palette_key_for_car_type(car_type: str | None) -> str | None:
    """Return the canonical base-model key for a raw ``car_type`` string."""
    ct = (car_type or "").strip()
    if not ct:
        return None
    for model_key, _display, patterns in MODEL_PATTERNS:
        for pat in patterns:
            if re.search(pat, ct, re.IGNORECASE):
                return model_key
    return None


def palette_for_car_type(car_type: str | None) -> list[PaletteColor]:
    """Return the colour palette for a vehicle's ``car_type``.

    Falls back to :data:`DEFAULT_PALETTE` when the model is unrecognised.
    """
    key = palette_key_for_car_type(car_type)
    return MODEL_PALETTES.get(key or "", DEFAULT_PALETTE)


# ---------------------------------------------------------------------------
# Colour matching helpers
# ---------------------------------------------------------------------------
def hex_to_rgb(hex_: str) -> tuple[int, int, int]:
    """Convert ``#rrggbb`` (or ``rrggbb``) to an ``(r, g, b)`` tuple."""
    h = hex_.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def match_color_name(
    out_color: str | None, palette: list[PaletteColor]
) -> PaletteColor | None:
    """Match a cloud-reported colour name to a palette entry.

    Tries exact normalised equality first, then bidirectional substring
    matching (so "Pearly White" matches "Pearl White" and vice versa).
    """
    if not out_color:
        return None
    target = _norm(out_color)
    if not target:
        return None
    for color in palette:
        if _norm(color.name) == target:
            return color
    for color in palette:
        norm_name = _norm(color.name)
        if norm_name and (norm_name in target or target in norm_name):
            return color
    # Fuzzy fallback for near-spellings (e.g. "Pearly White" -> "Pearl White").
    best: PaletteColor | None = None
    best_ratio = 0.0
    for color in palette:
        ratio = SequenceMatcher(None, _norm(color.name), target).ratio()
        if ratio > best_ratio:
            best, best_ratio = color, ratio
    return best if best_ratio >= 0.84 else None


def nearest_color(
    rgb: tuple[int, int, int], palette: list[PaletteColor]
) -> PaletteColor:
    """Return the palette entry closest to ``rgb`` by Euclidean RGB distance."""
    r, g, b = rgb

    def dist(color: PaletteColor) -> int:
        cr, cg, cb = hex_to_rgb(color.hex)
        return (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2

    return min(palette, key=dist)
