"""Identity & setup routes: certificates, account credentials, local user, auth."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from leapconnect.api.deps import SESSION_COOKIE_NAME, ContainerDep, RepoDep
from leapconnect.api.schemas import (
    AccountSetupResponse,
    AccountTestResponse,
    AuthLoginResponse,
    CertificateFetchResponse,
    CertificateStatusResponse,
    CertificateUploadResponse,
    SetupStatusResponse,
    StatusResponse,
    UserCreateResponse,
    UserInfoResponse,
    UserUpdateResponse,
    VehicleSchema,
)
from leapconnect.config import CERTS_DIR
from leapconnect.domain.identity.sessions import SESSION_MAX_AGE

_LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["identity"])


def _set_session_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
    )


@router.get("/api/setup/status", response_model=SetupStatusResponse)
async def setup_status(
    request: Request, repo: RepoDep, container: ContainerDep
) -> SetupStatusResponse:
    """Check if the app is configured (user + certificates + credentials)."""

    user = await repo.get_user()
    has_user = user is not None

    # Check session authentication
    token = request.cookies.get(SESSION_COOKIE_NAME)
    authenticated = container.sessions.validate(token)

    account = await repo.get_account()
    has_account = account is not None
    has_certs = False
    certs_valid = False

    if account:
        has_certs = bool(account.get("cert_path") and account.get("key_path"))
        certs_valid = (
            has_certs
            and Path(account["cert_path"]).is_file()
            and Path(account["key_path"]).is_file()
        )
    else:
        # Check certs from settings (uploaded but no account yet)
        cert_path = await repo.get_setting("cert_path") or ""
        key_path = await repo.get_setting("key_path") or ""
        if cert_path and key_path:
            has_certs = True
            certs_valid = Path(cert_path).is_file() and Path(key_path).is_file()

    # Detect cert files on disk even if the DB has no record of them
    certs_found_on_disk = (
        not has_certs
        and (CERTS_DIR / "app.crt").is_file()
        and (CERTS_DIR / "app.key").is_file()
    )

    return SetupStatusResponse(
        has_user=has_user,
        has_account=has_account,
        has_certificates=has_certs,
        certificates_valid=certs_valid,
        certs_found_on_disk=certs_found_on_disk,
        authenticated=authenticated,
        connected=container.connected,
        vehicles=[VehicleSchema.from_model(v) for v in container.vehicles],
        display_name=user.get("display_name") if user else None,
    )


@router.post("/api/setup/certificates", response_model=CertificateUploadResponse)
async def upload_certificates(
    repo: RepoDep,
    cert_file: UploadFile = File(...),  # noqa: B008
    key_file: UploadFile = File(...),  # noqa: B008
) -> CertificateUploadResponse:
    """Upload certificate files (cert + key) for API authentication."""

    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    cert_dest = CERTS_DIR / "app.crt"
    key_dest = CERTS_DIR / "app.key"

    try:
        with open(cert_dest, "wb") as f:
            shutil.copyfileobj(cert_file.file, f)
        with open(key_dest, "wb") as f:
            shutil.copyfileobj(key_file.file, f)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to save files: {exc}"
        ) from exc

    # Restrict permissions on the key file
    key_dest.chmod(0o600)

    await repo.save_setting("cert_path", str(cert_dest))
    await repo.save_setting("key_path", str(key_dest))

    return CertificateUploadResponse(
        status="ok", cert_path=str(cert_dest), key_path=str(key_dest)
    )


@router.post("/api/setup/certificates/adopt", response_model=CertificateUploadResponse)
async def adopt_certificates(repo: RepoDep) -> CertificateUploadResponse:
    """Adopt certificate files already present on disk without re-uploading."""

    cert_dest = CERTS_DIR / "app.crt"
    key_dest = CERTS_DIR / "app.key"

    if not cert_dest.is_file() or not key_dest.is_file():
        raise HTTPException(
            status_code=404, detail="Certificate files not found on disk"
        )

    await repo.save_setting("cert_path", str(cert_dest))
    await repo.save_setting("key_path", str(key_dest))

    return CertificateUploadResponse(
        status="ok", cert_path=str(cert_dest), key_path=str(key_dest)
    )


@router.get("/api/setup/certificates", response_model=CertificateStatusResponse)
async def get_certificates(repo: RepoDep) -> CertificateStatusResponse:
    """Check whether certificate files are present."""

    account = await repo.get_account()
    if account:
        cert_path = account.get("cert_path", "")
        key_path = account.get("key_path", "")
    else:
        cert_path = await repo.get_setting("cert_path") or ""
        key_path = await repo.get_setting("key_path") or ""

    return CertificateStatusResponse(
        cert_exists=bool(cert_path) and Path(cert_path).is_file(),
        key_exists=bool(key_path) and Path(key_path).is_file(),
    )


GITHUB_CERTS_REPO = "markoceri/leapmotor-certs"
GITHUB_CERTS_URL = f"https://github.com/{GITHUB_CERTS_REPO}"
GITHUB_CERTS_API = f"https://api.github.com/repos/{GITHUB_CERTS_REPO}/releases/latest"
GITHUB_UA = "LeapConnect"
GITHUB_ACCEPT_JSON = "application/vnd.github+json"

# Expected certificate filenames in the GitHub release assets
_CERT_ASSET_NAMES = {
    "app_cert.pem",
    "app.crt",
    "app_cert.crt",
}
_KEY_ASSET_NAMES = {
    "app_key.pem",
    "app.key",
    "app_key.key",
}


@router.post(
    "/api/setup/certificates/fetch",
    response_model=CertificateFetchResponse,
)
async def fetch_certificates_from_github(repo: RepoDep) -> CertificateFetchResponse:
    """Download certificates from the leapmotor-certs GitHub release."""

    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            # Fetch the latest release metadata
            release_resp = await client.get(
                GITHUB_CERTS_API,
                headers={
                    "User-Agent": GITHUB_UA,
                    "Accept": GITHUB_ACCEPT_JSON,
                },
            )
            release_resp.raise_for_status()
            release = release_resp.json()

            tag = release.get("tag_name", "unknown")
            assets = release.get("assets", [])
            if not assets:
                raise HTTPException(
                    status_code=502,
                    detail="No assets found in GitHub release",
                )

            # Find cert and key assets by filename
            cert_url = None
            key_url = None
            for asset in assets:
                name = asset.get("name", "").lower()
                url = asset.get("browser_download_url")
                if name in _CERT_ASSET_NAMES and not cert_url:
                    cert_url = url
                elif name in _KEY_ASSET_NAMES and not key_url:
                    key_url = url

            if not cert_url:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Certificate asset not found in release. "
                        f"Expected one of: {', '.join(sorted(_CERT_ASSET_NAMES))}"
                    ),
                )
            if not key_url:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Private key asset not found in release. "
                        f"Expected one of: {', '.join(sorted(_KEY_ASSET_NAMES))}"
                    ),
                )

            # Download both files (GitHub redirects to SAS URLs)
            cert_resp = await client.get(cert_url, follow_redirects=True)
            cert_resp.raise_for_status()

            key_resp = await client.get(key_url, follow_redirects=True)
            key_resp.raise_for_status()

            cert_dest = CERTS_DIR / "app.crt"
            key_dest = CERTS_DIR / "app.key"

            cert_dest.write_bytes(cert_resp.content)
            key_dest.write_bytes(key_resp.content)
            key_dest.chmod(0o600)

            await repo.save_setting("cert_path", str(cert_dest))
            await repo.save_setting("key_path", str(key_dest))

            _LOGGER.info("Certificates fetched from GitHub release %s", tag)
            return CertificateFetchResponse(
                status="ok",
                cert_path=str(cert_dest),
                key_path=str(key_dest),
                source=f"{GITHUB_CERTS_URL}/releases/tag/{tag}",
            )

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub request failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# LeapConnect local user & dashboard authentication
# ---------------------------------------------------------------------------


@router.post("/api/setup/user", response_model=UserCreateResponse)
async def create_user(
    request: Request, repo: RepoDep, container: ContainerDep
) -> Response:
    """Create a LeapConnect application user."""

    body = await request.json()
    display_name = body.get("display_name", "").strip()
    password = body.get("password", "").strip()

    if not display_name or not password:
        raise HTTPException(
            status_code=422, detail="display_name and password are required"
        )
    if len(password) < 4:
        raise HTTPException(
            status_code=422, detail="Password must be at least 4 characters"
        )

    existing = await repo.get_user()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

    user = await repo.create_user(display_name, password)

    # Auto-login: create session for the new user
    token = container.sessions.create()
    resp = JSONResponse(
        content=UserCreateResponse(
            status="ok", display_name=user["display_name"]
        ).model_dump()
    )
    _set_session_cookie(resp, token)
    return resp


@router.post("/api/auth/session", response_model=AuthLoginResponse)
async def auth_login(
    request: Request, repo: RepoDep, container: ContainerDep
) -> Response:
    """Authenticate with the LeapConnect user password."""

    body = await request.json()
    password = body.get("password", "").strip()

    if not password:
        raise HTTPException(status_code=422, detail="Password is required")

    throttle_key = request.client.host if request.client else "unknown"
    retry_after = container.login_throttle.retry_after(throttle_key)
    if retry_after is not None:
        seconds = int(retry_after) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Retry in {seconds}s.",
            headers={"Retry-After": str(seconds)},
        )

    valid = await repo.verify_user_password(password)
    if not valid:
        container.login_throttle.record_failure(throttle_key)
        raise HTTPException(status_code=401, detail="Invalid password")
    container.login_throttle.record_success(throttle_key)

    user = await repo.get_user()
    token = container.sessions.create()
    resp = JSONResponse(
        content=AuthLoginResponse(
            status="ok",
            display_name=user["display_name"] if user else "",
        ).model_dump()
    )
    _set_session_cookie(resp, token)
    return resp


@router.delete("/api/auth/session", response_model=StatusResponse)
async def auth_logout(request: Request, container: ContainerDep) -> Response:
    """Logout from the LeapConnect session."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    container.sessions.invalidate(token)
    resp = JSONResponse(content=StatusResponse(status="ok").model_dump())
    resp.delete_cookie(key=SESSION_COOKIE_NAME)
    return resp


@router.get("/api/setup/user", response_model=UserInfoResponse)
async def get_user_info(repo: RepoDep) -> UserInfoResponse:
    """Get current LeapConnect user info."""

    user = await repo.get_user()
    return UserInfoResponse(
        has_user=user is not None,
        display_name=user["display_name"] if user else None,
    )


@router.put("/api/setup/user", response_model=UserUpdateResponse)
async def update_user(request: Request, repo: RepoDep) -> UserUpdateResponse:
    """Update LeapConnect user display name and/or password."""

    body = await request.json()
    display_name = body.get("display_name")
    password = body.get("password")
    current_password = body.get("current_password", "").strip()

    if not current_password:
        raise HTTPException(status_code=422, detail="current_password is required")

    if not await repo.verify_user_password(current_password):
        raise HTTPException(status_code=403, detail="Current password is incorrect")

    if display_name is not None:
        display_name = display_name.strip()
        if not display_name:
            raise HTTPException(status_code=422, detail="display_name cannot be empty")

    if password is not None:
        password = password.strip()
        if len(password) < 4:
            raise HTTPException(
                status_code=422,
                detail="Password must be at least 4 characters",
            )

    user = await repo.update_user(display_name=display_name, password=password)
    if not user:
        raise HTTPException(status_code=404, detail="No user found")

    return UserUpdateResponse(status="ok", display_name=user["display_name"])


# ---------------------------------------------------------------------------
# Leapmotor account credentials
# ---------------------------------------------------------------------------


async def _validated_cert_paths(repo) -> tuple[str, str]:
    """Resolve and validate cert/key paths previously uploaded via setup."""
    cert_path = await repo.get_setting("cert_path") or ""
    key_path = await repo.get_setting("key_path") or ""

    if not cert_path or not key_path:
        raise HTTPException(status_code=422, detail="Certificates not uploaded yet")
    if not Path(cert_path).is_file():
        raise HTTPException(
            status_code=400, detail=f"Certificate file not found: {cert_path}"
        )
    if not Path(key_path).is_file():
        raise HTTPException(status_code=400, detail=f"Key file not found: {key_path}")
    return cert_path, key_path


@router.post("/api/setup/account", response_model=AccountSetupResponse)
async def save_account(
    request: Request, repo: RepoDep, container: ContainerDep
) -> AccountSetupResponse:
    """Save account credentials and attempt to connect."""

    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    p12_password = body.get("p12_password", "").strip() or None

    if not all([username, password]):
        raise HTTPException(
            status_code=422, detail="username and password are required"
        )

    cert_path, key_path = await _validated_cert_paths(repo)

    # Save credentials to DB
    await repo.save_account(
        username=username,
        password=password,
        cert_path=cert_path,
        key_path=key_path,
        p12_password=p12_password,
    )

    # Attempt connection
    try:
        vehicles = await container.connect(
            username=username,
            password=password,
            cert_path=cert_path,
            key_path=key_path,
            p12_password=p12_password,
        )
        return AccountSetupResponse(
            status="ok",
            connected=True,
            vehicles=[VehicleSchema.from_model(v) for v in vehicles],
        )
    except Exception as exc:
        # Credentials saved but connection failed — that's ok, app works offline
        return AccountSetupResponse(
            status="ok",
            connected=False,
            connection_error=str(exc),
            vehicles=[],
        )


@router.post("/api/setup/account/test", response_model=AccountTestResponse)
async def test_account(request: Request, repo: RepoDep) -> AccountTestResponse:
    """Test Leapmotor credentials without saving them."""
    from contextlib import suppress

    from leapmotor_api import LeapmotorApiClient
    from leapmotor_api.async_client import AsyncLeapmotorApiClient

    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    p12_password = body.get("p12_password", "").strip() or None

    if not all([username, password]):
        raise HTTPException(
            status_code=422, detail="username and password are required"
        )

    cert_path, key_path = await _validated_cert_paths(repo)

    # Attempt a temporary connection (do NOT affect the global client)
    test_sync = None
    try:
        test_sync = LeapmotorApiClient(
            username=username,
            password=password,
            app_cert_path=cert_path,
            app_key_path=key_path,
            account_p12_password=p12_password,
        )
        test_async = AsyncLeapmotorApiClient(test_sync)
        await test_async.login()
        test_vehicles = await test_async.get_vehicle_list()

        return AccountTestResponse(
            status="ok",
            connected=True,
            vehicles=[VehicleSchema.from_model(v) for v in test_vehicles],
        )
    except Exception as exc:
        return AccountTestResponse(
            status="ok",
            connected=False,
            connection_error=str(exc),
            vehicles=[],
        )
    finally:
        # Always clean up the temporary client
        if test_sync:
            with suppress(Exception):
                test_sync.close()
