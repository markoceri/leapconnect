"""Stream OTA packages from the Leapmotor CDN.

The ``downloadURL`` of a package is a signed CloudFront link (about six months
of validity, see ``SoftwarePackage.link_expires_at``) fetched with a plain GET:
no login, client certificate or Leapmotor header. The files are served
encrypted as ``<fileName>.encrypt`` (``SoftwarePackage.served_file_name``) and
``fileSize`` is their served size; the md5/sha256 the cloud lists don't match
the downloaded bytes, so the files are an archive copy only.

Everything is streamed: nothing is kept in memory or written to disk, so a
1.9 GB update goes through a small host as well. The signed query string never
reaches the logs: httpx logs every request URL at INFO, so it is redacted.
"""

from __future__ import annotations

import logging
import time
import zipfile
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

_TIMEOUT = httpx.Timeout(30.0, read=120.0)
CHUNK_SIZE = 256 * 1024

# Response headers worth passing on to the browser for one package.
FORWARDED_HEADERS = (
    "content-length",
    "content-range",
    "accept-ranges",
    "etag",
    "last-modified",
)


class OtaCdnError(Exception):
    """The CDN refused the package (expired link, missing file, …)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _redact(value: object) -> object:
    text = str(value)
    if "Signature=" in text or "Key-Pair-Id=" in text:
        return text.split("?", 1)[0] + "?<signed>"
    return value


class _RedactSignedLinks(logging.Filter):
    """Drop the signature from the request URLs httpx logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_redact(a) for a in record.args)
        return True


logging.getLogger("httpx").addFilter(_RedactSignedLinks())


@asynccontextmanager
async def open_package(
    url: str, *, range_header: str | None = None, if_range: str | None = None
) -> AsyncIterator[httpx.Response]:
    """An open streaming response for one package; raises ``OtaCdnError``.

    The error messages never carry the link: httpx puts it in its own.
    """
    headers = {"Accept-Encoding": "identity"}
    if range_header:
        headers["Range"] = range_header
        if if_range:
            headers["If-Range"] = if_range
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        try:
            response = await client.send(
                client.build_request("GET", url, headers=headers), stream=True
            )
        except httpx.HTTPError as exc:
            raise OtaCdnError(f"CDN unreachable ({type(exc).__name__})") from None
        try:
            if response.status_code not in (200, 206):
                raise OtaCdnError(
                    f"CDN answered HTTP {response.status_code}", response.status_code
                )
            yield response
        finally:
            await response.aclose()


class _Sink:
    """Write-only, non-seekable target: zipfile then streams with data descriptors."""

    def __init__(self) -> None:
        self._chunks: list[bytes] = []

    def write(self, data: bytes) -> int:
        self._chunks.append(bytes(data))
        return len(data)

    def flush(self) -> None:
        pass

    def drain(self) -> bytes:
        data = b"".join(self._chunks)
        self._chunks.clear()
        return data


async def zip_packages(
    files: Iterable[tuple[str, str]], extra: dict[str, bytes]
) -> AsyncIterator[bytes]:
    """A ZIP (stored, ZIP64) of ``extra`` files then each ``(name, url)`` package.

    The packages are encrypted and don't compress, so they are stored as-is.
    A CDN error mid-way ends the stream, leaving a truncated archive.
    """
    sink = _Sink()
    now = time.localtime()[:6]
    with zipfile.ZipFile(sink, "w", zipfile.ZIP_STORED) as archive:
        for name, data in extra.items():
            archive.writestr(zipfile.ZipInfo(name, now), data)
        yield sink.drain()
        for name, url in files:
            async with open_package(url) as response:
                info = zipfile.ZipInfo(name, now)
                with archive.open(info, "w", force_zip64=True) as entry:
                    async for chunk in response.aiter_raw(CHUNK_SIZE):
                        entry.write(chunk)
                        yield sink.drain()
            yield sink.drain()
    yield sink.drain()
