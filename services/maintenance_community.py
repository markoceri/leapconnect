"""Community maintenance repositories — discovery & fetching.

A *repository* is a GitHub repo (or a plain URL) that publishes one or more
maintenance *packs* (JSON). Discovery prefers a root manifest
``leapconnect-maintenance.json``; otherwise the ``packs/`` directory is listed
via the GitHub contents API. All network access lives here so the rest of the
app stays I/O-free and testable.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from services.maintenance_service import normalize_pack

_LOGGER = logging.getLogger(__name__)

MANIFEST_FILENAME = "leapconnect-maintenance.json"
PACKS_DIR = "packs"
_TIMEOUT = httpx.Timeout(15.0)
_HEADERS = {
    "User-Agent": "LeapConnect-Maintenance",
    "Accept": "application/vnd.github+json",
}


class CommunityError(Exception):
    """Raised when a repository or pack cannot be fetched/parsed."""


def parse_github_url(url: str) -> tuple[str, str, str | None]:
    """Parse a GitHub repo reference into (owner, repo, branch|None).

    Accepts ``https://github.com/owner/repo``, ``.../tree/<branch>`` and the
    ``owner/repo`` shorthand. Raises :class:`CommunityError` otherwise.
    """
    s = (url or "").strip().rstrip("/")
    s = re.sub(r"\.git$", "", s)
    m = re.match(
        r"^(?:https?://github\.com/)?([^/\s]+)/([^/\s]+)"
        r"(?:/tree/([^/\s]+))?$",
        s,
    )
    if not m:
        raise CommunityError(f"Not a valid GitHub repository URL: {url!r}")
    owner, repo, branch = m.group(1), m.group(2), m.group(3)
    return owner, repo, branch


def _raw_url(owner: str, repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"


async def _default_branch(client: httpx.AsyncClient, owner: str, repo: str) -> str:
    try:
        resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}")
        if resp.status_code == 200:
            return resp.json().get("default_branch") or "main"
    except httpx.HTTPError as exc:  # pragma: no cover - network failure
        _LOGGER.warning("default_branch lookup failed for %s/%s: %s", owner, repo, exc)
    return "main"


async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict | list | None:
    resp = await client.get(url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    try:
        return resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise CommunityError(f"Invalid JSON at {url}: {exc}") from exc


async def discover_repo(url: str) -> dict:
    """Discover a repository's metadata and available packs.

    Returns ``{type, url, name, author, description, branch, packs:[...]}``
    where each pack entry is ``{slug, file, name, model_compat}``.
    """
    owner, repo, branch = parse_github_url(url)
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        if not branch:
            branch = await _default_branch(client, owner, repo)

        # 1) Prefer an explicit manifest at the repo root.
        manifest = await _fetch_json(
            client, _raw_url(owner, repo, branch, MANIFEST_FILENAME)
        )
        if isinstance(manifest, dict) and isinstance(manifest.get("packs"), list):
            packs = []
            for p in manifest["packs"]:
                if not isinstance(p, dict):
                    continue
                file = p.get("file") or f"{PACKS_DIR}/{p.get('slug')}.json"
                slug = p.get("slug") or re.sub(r"\.json$", "", file.split("/")[-1])
                packs.append(
                    {
                        "slug": slug,
                        "file": file,
                        "name": p.get("name") or slug,
                        "model_compat": p.get("model_compat"),
                    }
                )
            return {
                "type": "github",
                "url": f"https://github.com/{owner}/{repo}",
                "name": manifest.get("name") or f"{owner}/{repo}",
                "author": manifest.get("author") or owner,
                "description": manifest.get("description"),
                "branch": branch,
                "packs": packs,
            }

        # 2) Fallback: list the packs/ directory via the contents API.
        listing = await _fetch_json(
            client,
            f"https://api.github.com/repos/{owner}/{repo}/contents/"
            f"{PACKS_DIR}?ref={branch}",
        )
        packs = []
        if isinstance(listing, list):
            for entry in listing:
                name = entry.get("name", "")
                if entry.get("type") == "file" and name.endswith(".json"):
                    slug = re.sub(r"\.json$", "", name)
                    packs.append(
                        {
                            "slug": slug,
                            "file": f"{PACKS_DIR}/{name}",
                            "name": slug,
                            "model_compat": None,
                        }
                    )
        if not packs:
            raise CommunityError(
                "No maintenance packs found: add a "
                f"'{MANIFEST_FILENAME}' manifest or a '{PACKS_DIR}/' directory."
            )
        return {
            "type": "github",
            "url": f"https://github.com/{owner}/{repo}",
            "name": f"{owner}/{repo}",
            "author": owner,
            "description": None,
            "branch": branch,
            "packs": packs,
        }


async def fetch_pack_file(owner_repo_url: str, branch: str, file: str) -> dict:
    """Fetch and normalize a single pack file from a GitHub repo."""
    owner, repo, _ = parse_github_url(owner_repo_url)
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        payload = await _fetch_json(client, _raw_url(owner, repo, branch, file))
    if payload is None:
        raise CommunityError(f"Pack file not found: {file}")
    return normalize_pack(payload)


async def fetch_pack_url(raw_url: str) -> dict:
    """Fetch and normalize a pack from an arbitrary raw JSON URL."""
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        payload = await _fetch_json(client, raw_url)
    if payload is None:
        raise CommunityError(f"Pack not found at {raw_url}")
    return normalize_pack(payload)
