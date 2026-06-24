"""DTOs for vehicle appearance / accent-colour theming."""

from __future__ import annotations

from pydantic import BaseModel

from leapconnect.domain.styling import PaletteColor


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
