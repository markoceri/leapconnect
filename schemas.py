"""DEPRECATED compatibility shim.

The Pydantic DTOs moved to ``leapconnect.api.schemas`` (grouped by bounded
context). Import from there instead. This module will be removed in a future
release.
"""

from leapconnect.api.schemas import *  # noqa: F401,F403
