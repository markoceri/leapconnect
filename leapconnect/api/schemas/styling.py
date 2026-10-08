"""DTOs for vehicle appearance / accent-colour theming."""

from __future__ import annotations

from pydantic import BaseModel, Field

from leapconnect.domain.styling import MapTileSettings, PaletteColor


class PaletteColorSchema(BaseModel):
    key: str
    name: str
    hex: str

    @classmethod
    def from_model(cls, color: PaletteColor) -> PaletteColorSchema:
        return cls(key=color.key, name=color.name, hex=color.hex)


class VehiclePaletteResponse(BaseModel):
    vin: str
    model_key: str | None = None
    colors: list[PaletteColorSchema]
    selected: PaletteColorSchema | None = None


class VehicleColorUpdate(BaseModel):
    color_key: str | None = None


class ColorDetectResponse(BaseModel):
    detected: PaletteColorSchema | None = None
    source: str  # "out_color" | "image" | "none"


class MapTileSettingsSchema(BaseModel):
    """Map tile provider selection (``GET``/``PUT /api/map-tiles``).

    ``api_keys`` maps a keyed provider id to its key; the PUT body replaces
    the whole map, so an omitted or empty entry clears that key.
    """

    provider: str = "osm"
    api_keys: dict[str, str] = Field(default_factory=dict)
    custom_url: str = ""
    custom_dark_url: str = ""

    @classmethod
    def from_model(cls, settings: MapTileSettings) -> MapTileSettingsSchema:
        return cls(
            provider=settings.provider,
            api_keys=dict(settings.api_keys),
            custom_url=settings.custom_url,
            custom_dark_url=settings.custom_dark_url,
        )

    def to_model(self) -> MapTileSettings:
        return MapTileSettings(
            provider=self.provider,
            api_keys=dict(self.api_keys),
            custom_url=self.custom_url,
            custom_dark_url=self.custom_dark_url,
        )
