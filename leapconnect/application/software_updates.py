"""Installed vehicle software and pending OTA updates.

The Leapmotor cloud answers ``/hotspot/fetch`` only for the account that owns
the car: an account the car is shared with gets ``No such permission``, which
leapmotor-api raises as ``LeapmotorPermissionError``. That is an expected
state here (the setup suggests a shared account), reported as ``owner_only``.

The answer changes rarely, so it is cached per VIN for hours; the scheduler
reads the cache after each history poll to raise ``software_update_available``
once per version and feed the Home Assistant ``update`` entity.

The packages carry signed download links, hashes and signatures: none of them
reaches the frontend. The links are only followed server-side, to stream the
packages to the owner (see ``infrastructure/ota_cdn``).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from leapmotor_api.exceptions import LeapmotorPermissionError

if TYPE_CHECKING:
    from collections.abc import Callable

    from leapmotor_api.async_client import AsyncLeapmotorApiClient
    from leapmotor_api.models import (
        SoftwareInfo,
        SoftwarePackage,
        SoftwareReleaseNote,
        SoftwareVersion,
        Vehicle,
    )

    from leapconnect.application.notifications import NotificationDispatcher
    from leapconnect.application.ports.repositories import AppRepository

_LOGGER = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 6 * 3600
UPDATE_EVENT = "software_update_available"
NOTIFIED_SETTING_PREFIX = "software_update_notified:"
NOTIFICATION_NOTES_MAX_CHARS = 600
HA_SUMMARY_MAX_CHARS = 255  # Home Assistant's limit for release_summary
# A download link that expires within this margin is fetched again first.
LINK_EXPIRY_MARGIN = timedelta(hours=1)

# Leading letters of the ECU part code (``LP-IVI010-AA`` → ``IVI``).
_COMPONENT_LABELS = {
    "IVI": "Infotainment",
    "ICU": "Instrument cluster",
    "VCU": "Vehicle control unit",
    "BMU": "Battery management",
    "BMS": "Battery management",
    "HVAC": "Climate control",
    "EPBM": "Electric parking brake",
    "EPBS": "Electric parking brake",
    "EVCC": "Charging communication",
}
_PART_RE = re.compile(r"^[A-Z0-9]+-([A-Z]+)\d")
_UNKNOWN_VERSION_RE = re.compile(r"^[0.]*$")  # a T03 reports "0.00.00"


@dataclass(frozen=True)
class SoftwareLookup:
    """One answer of ``/hotspot/fetch``; ``info`` is None for a non-owner account."""

    vin: str
    info: SoftwareInfo | None
    checked_at: datetime
    fetched_at: float = field(default=0.0, repr=False)  # monotonic clock

    @property
    def owner_only(self) -> bool:
        return self.info is None

    @property
    def pending(self) -> SoftwareVersion | None:
        """The update waiting to be installed, if any."""
        return self.info.new_version if self.info else None


class SoftwareUpdates:
    """Per-VIN cache of the software information (TTL, single-flight)."""

    def __init__(
        self,
        ttl_seconds: float = CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[str, SoftwareLookup] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def clear(self) -> None:
        """Forget every answer (another account may now be connected)."""
        self._entries.clear()

    def cached(self, vin: str) -> SoftwareLookup | None:
        return self._entries.get(vin)

    async def get(
        self,
        client: AsyncLeapmotorApiClient,
        vehicle: Vehicle,
        *,
        refresh: bool = False,
    ) -> SoftwareLookup:
        """The cached answer while fresh, else a new one from the cloud.

        Cloud errors other than the owner-only refusal propagate and are not
        cached, so the next call tries again.
        """
        vin = vehicle.vin
        lock = self._locks.setdefault(vin, asyncio.Lock())
        async with lock:
            entry = self._entries.get(vin)
            if entry and not refresh and self._clock() - entry.fetched_at < self._ttl:
                return entry
            try:
                info = await client.get_software_info(vehicle)
            except LeapmotorPermissionError:
                info = None
            entry = SoftwareLookup(
                vin=vin,
                info=info,
                checked_at=datetime.now(UTC),
                fetched_at=self._clock(),
            )
            self._entries[vin] = entry
            return entry

    async def for_download(
        self, client: AsyncLeapmotorApiClient, vehicle: Vehicle
    ) -> SoftwareLookup:
        """Like ``get``, asking the cloud again when a download link is expiring."""
        lookup = await self.get(client, vehicle)
        pending = lookup.pending
        if pending and any(link_expiring(p) for p in pending.packages):
            lookup = await self.get(client, vehicle, refresh=True)
        return lookup


# -- presentation helpers -------------------------------------------------------


def known_version(version: SoftwareVersion | None) -> str | None:
    """The version string, or None when the cloud doesn't know it (``0.00.00``)."""
    if version is None or not version.version:
        return None
    return None if _UNKNOWN_VERSION_RE.match(version.version) else version.version


def pick_release_notes(
    version: SoftwareVersion, language: str
) -> tuple[str | None, list[SoftwareReleaseNote]]:
    """The notes in ``language`` (with the library's fallbacks) and their language."""
    notes = version.release_notes_for(language)
    picked = next(
        (code for code, entries in version.release_notes.items() if entries is notes),
        None,
    )
    return picked, notes


def note_text(text: str | None) -> str:
    """Release-note content as plain text: the cloud numbers items with a tab."""
    return (text or "").replace("\t", " ").strip()


def component_label(package: SoftwarePackage) -> str | None:
    """A readable name for the ECU a package targets, when known."""
    for candidate in (package.ecu_id or "", package.product or ""):
        if candidate in _COMPONENT_LABELS:
            return _COMPONENT_LABELS[candidate]
        m = _PART_RE.match(candidate)
        if m and m.group(1) in _COMPONENT_LABELS:
            return _COMPONENT_LABELS[m.group(1)]
    return None


def build_date(package: SoftwarePackage) -> str | None:
    """The package build date (``softNumber``, ``YYYYMMDD``) as ISO, if valid."""
    raw = package.soft_number or ""
    try:
        return datetime.strptime(raw, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def format_size(size_bytes: int) -> str:
    """Decimal size, as the official app shows it (``1.89 GB``)."""
    for unit, factor in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if size_bytes >= factor:
            return f"{size_bytes / factor:.2f} {unit}"
    return f"{size_bytes} B"


def notes_summary(notes: list[SoftwareReleaseNote], max_chars: int) -> str:
    """The notes as ``title: content`` lines, cut at ``max_chars``."""
    text = "\n".join(
        f"{n.title}: {note_text(n.content)}" if n.title else note_text(n.content)
        for n in notes
    )
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def home_assistant_state(lookup: SoftwareLookup, language: str) -> dict | None:
    """Payload of the HA MQTT ``update`` entity; None for a non-owner account.

    HA compares installed and latest version, so the installed one is sent as
    the cloud reports it, ``0.00.00`` included: with ``null`` a pending update
    would show as unknown.
    """
    info = lookup.info
    if info is None:
        return None
    installed = (info.current_version.version if info.current_version else None) or (
        "unknown"
    )
    pending = info.new_version
    state: dict = {
        "installed_version": installed,
        "latest_version": (pending.version if pending else None) or installed,
        "title": "Leapmotor software",
    }
    if pending:
        _, notes = pick_release_notes(pending, language)
        state["release_summary"] = notes_summary(notes, HA_SUMMARY_MAX_CHARS)
    return state


# -- package download -----------------------------------------------------------


def link_expiring(package: SoftwarePackage, now: datetime | None = None) -> bool:
    """True if the package's download link expires within ``LINK_EXPIRY_MARGIN``."""
    expires = package.link_expires_at
    if not package.download_url or expires is None:
        return False
    return expires - LINK_EXPIRY_MARGIN <= (now or datetime.now(UTC))


def downloadable(package: SoftwarePackage) -> bool:
    """The package has a link and a safe file name to serve it under."""
    return bool(package.download_url and package.served_file_name)


def find_package(version: SoftwareVersion, seq: int) -> SoftwarePackage | None:
    """The downloadable package with ``seq``."""
    return next((p for p in version.packages if p.seq == seq and downloadable(p)), None)


def archive_name(vehicle: Vehicle, version: SoftwareVersion) -> str:
    """File name of the whole-update ZIP, e.g. ``Leapmotor-T03-1.03.12.zip``."""
    parts = ["Leapmotor", vehicle.car_type or vehicle.vin, version.version or "update"]
    return re.sub(r"[^A-Za-z0-9._-]+", "_", "-".join(parts)) + ".zip"


def download_manifest(
    vehicle: Vehicle, version: SoftwareVersion, language: str
) -> dict:
    """``manifest.json`` of the whole-update ZIP: what each file is, no links."""
    notes_language, notes = pick_release_notes(version, language)
    return {
        "vin": vehicle.vin,
        "model": vehicle.car_type,
        "version": version.version,
        "campaign_id": version.request_version_id,
        "note": (
            "Leapmotor serves these packages encrypted (.encrypt): this is an "
            "archive copy, it can't be installed from here. The md5/sha256 the "
            "cloud lists don't match the encrypted files, so none are included."
        ),
        "release_notes": {
            "language": notes_language,
            "sections": [
                {"title": n.title, "content": note_text(n.content)} for n in notes
            ],
        },
        "packages": [
            {
                "file": p.served_file_name,
                "encrypted": p.encrypted,
                "product": p.product,
                "component": component_label(p),
                "ecu_id": p.ecu_id,
                "version": p.soft_version,
                "build_date": build_date(p),
                "size_bytes": p.file_size,
            }
            for p in version.packages
            if downloadable(p)
        ],
    }


# -- notification ---------------------------------------------------------------


async def notify_pending_update(
    repo: AppRepository,
    dispatcher: NotificationDispatcher,
    vehicle: Vehicle,
    lookup: SoftwareLookup,
    language: str,
) -> bool:
    """Raise ``software_update_available`` once per pending version.

    The last notified version is kept per VIN in the settings table. Returns
    True when the event was raised.
    """
    pending = lookup.pending
    if pending is None or not pending.version:
        return False
    key = f"{NOTIFIED_SETTING_PREFIX}{vehicle.vin}"
    if await repo.get_setting(key) == pending.version:
        return False
    info = lookup.info
    installed = known_version(info.current_version if info else None)
    _, notes = pick_release_notes(pending, language)
    await dispatcher.dispatch_custom(
        UPDATE_EVENT,
        vehicle.vin,
        vehicle.vehicle_nickname or vehicle.car_type or vehicle.vin,
        {
            "version": pending.version,
            "installed": installed or "unknown",
            "size": format_size(pending.download_size),
            "packages": len(pending.packages),
            "notes": notes_summary(notes, NOTIFICATION_NOTES_MAX_CHARS)
            or "No release notes.",
        },
        history_value=pending.version,
        cooldown_key=f"{UPDATE_EVENT}:{pending.version}",
    )
    await repo.save_setting(key, pending.version)
    return True
