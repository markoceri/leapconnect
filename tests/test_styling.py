"""Unit tests for the vehicle appearance / accent-colour domain."""

from leapconnect.application.theme_detection import dominant_color
from leapconnect.domain.styling import (
    hex_to_rgb,
    match_color_name,
    nearest_color,
    palette_for_car_type,
)
from leapconnect.domain.styling.palettes import (
    DEFAULT_PALETTE,
    MODEL_PALETTES,
    palette_key_for_car_type,
)


def test_palette_key_resolution():
    assert palette_key_for_car_type("T03") == "T03"
    assert palette_key_for_car_type("b10-something") == "B10"
    assert palette_key_for_car_type("LEAP C10 REEV") == "C10"
    assert palette_key_for_car_type("") is None
    assert palette_key_for_car_type(None) is None
    assert palette_key_for_car_type("ZZZ") is None


def test_palette_for_known_models():
    t03 = palette_for_car_type("T03")
    names = {c.name for c in t03}
    assert "Mint Green" in names
    assert "Caribbean Blue" in names
    # B10 has its own distinct colours
    b10_names = {c.name for c in palette_for_car_type("B10")}
    assert "Dawn Purple" in b10_names
    assert "Mint Green" not in b10_names


def test_palette_unknown_falls_back_to_default():
    assert palette_for_car_type("totally-unknown") is DEFAULT_PALETTE


def test_palette_color_keys_are_unique_slugs():
    for model, palette in MODEL_PALETTES.items():
        keys = [c.key for c in palette]
        assert len(keys) == len(set(keys)), f"duplicate keys in {model}"
        for c in palette:
            assert c.hex.startswith("#") and len(c.hex) == 7


def test_match_color_name_exact_and_fuzzy():
    palette = palette_for_car_type("C10")
    # Exact (case/space-insensitive)
    assert match_color_name("pearl white", palette).name == "Pearl White"
    assert match_color_name("Glazed Green", palette).name == "Glazed Green"
    # Fuzzy: a near-spelling should still match.
    assert match_color_name("Tundra Gray", palette).name == "Tundra Grey"
    # No match
    assert match_color_name("Banana Yellow", palette) is None
    assert match_color_name(None, palette) is None


def test_hex_to_rgb():
    assert hex_to_rgb("#9fd9c0") == (0x9F, 0xD9, 0xC0)
    assert hex_to_rgb("000") == (0, 0, 0)


def test_nearest_color_snaps_to_closest():
    palette = palette_for_car_type("T03")
    # A pale mint should snap to Mint Green (#9fd9c0).
    assert nearest_color((160, 216, 191), palette).name == "Mint Green"
    # Near-black should snap to the darkest entry (Canopy Grey on the T03 EU set).
    assert nearest_color((20, 20, 22), palette).name == "Canopy Grey"


def test_dominant_color_ignores_transparent_pixels():
    pytest_image = _solid_image_with_transparent_border((0x40, 0xA0, 0x80))
    rgb = dominant_color(pytest_image)
    assert rgb is not None
    # Quantised to 16-step buckets +8 centre, so allow a small delta.
    assert abs(rgb[0] - 0x40) <= 16
    assert abs(rgb[1] - 0xA0) <= 16
    assert abs(rgb[2] - 0x80) <= 16


def test_dominant_color_handles_garbage():
    assert dominant_color(b"not an image") is None


def test_dominant_color_ignores_dark_glass_and_picks_body():
    # A grey body with a large black "glass/tyre" band and a white highlight:
    # the paint (grey) must win, not the dark or bright regions.
    from PIL import Image

    img = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
    for x in range(60):
        for y in range(60):
            if y < 20:
                img.putpixel((x, y), (255, 255, 255, 255))  # highlight/sky
            elif y < 38:
                img.putpixel((x, y), (95, 98, 107, 255))  # Canopy-grey body (cool grey)
            else:
                img.putpixel((x, y), (8, 8, 9, 255))  # glass / tyres / shadow
    rgb = dominant_color(_png(img))
    palette = palette_for_car_type("T03")
    assert nearest_color(rgb, palette).name == "Canopy Grey"


def _png(img):
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _solid_image_with_transparent_border(color):
    import io

    from PIL import Image

    img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    for x in range(8, 32):
        for y in range(8, 32):
            img.putpixel((x, y), (*color, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
