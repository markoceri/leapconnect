"""Small helpers shared by the DTO modules."""


def _enum_val(v):
    """Extract .value from an IntEnum/StrEnum, pass through None."""
    if v is None:
        return None
    return v.value if hasattr(v, "value") else v
