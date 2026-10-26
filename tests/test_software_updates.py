"""Tests for the vehicle software (OTA) information."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from leapmotor_api.exceptions import LeapmotorApiError, LeapmotorPermissionError
from leapmotor_api.models import SoftwareInfo, Vehicle

from leapconnect.application.software_updates import (
    NOTIFIED_SETTING_PREFIX,
    UPDATE_EVENT,
    SoftwareUpdates,
    component_label,
    format_size,
    home_assistant_state,
    notify_pending_update,
)

VIN = "LTEST000000000001"
CDN = "https://ota-cdn.example.invalid/ota"
SIGNED = "?Expires=4102444800&Signature=secret-sig&Key-Pair-Id=secret-kp"
EVCC_URL = f"{CDN}/LP-EVCC120-AA_V2.00.07_R_20260325.bin.encrypt{SIGNED}"
IVI_URL = f"{CDN}/LP-IVI010-AA_V1.03.12_R_20260716.zip.encrypt{SIGNED}"

# Trimmed /hotspot/fetch answer of a T03 with a pending update.
DATA = {
    "newVersion": {
        "requestVersionId": 268958,
        "generalVersion": "1.03.12",
        "state": 1,
        "logJsonMultiLang": [
            {
                "language": "zh-CN",
                "data": [
                    {"title": "本次 OTA 新增功能", "content": "1、\t海外多语言支持"}
                ],
            },
            {
                "language": "en-US",
                "data": [
                    {
                        "title": "New features in this OTA update",
                        "content": "1.\tExpanded Language Support: Slovenian.",
                    }
                ],
            },
            {
                "language": "it-IT",
                "data": [
                    {
                        "title": "Nuove funzionalità di questo aggiornamento OTA",
                        "content": "1.\tSupporto linguistico ampliato: lo sloveno.",
                    },
                    {
                        "title": "Ottimizzazioni incluse in questo aggiornamento OTA",
                        "content": "1.\tClimatizzazione: comfort del riscaldamento.",
                    },
                ],
            },
        ],
        "updateItemList": [
            {
                "seq": 16,
                "downloadURL": EVCC_URL,
                "product": "LP-EVCC120-AA",
                "softversion": "2.00.07",
                "softNumber": "20260325",
                "md5": "md5-secret",
                "sha256": "sha-secret",
                "sign": "sign-secret",
                "fileSize": 600192,
                "pyid": "0x7B2",
            },
            {
                "seq": 23,
                "downloadURL": IVI_URL,
                "product": "LP-IVI010-AA",
                "softversion": "1.03.12",
                "softNumber": "20260716",
                "fileSize": 1715272438,
                "pyid": "IVI",
            },
            {
                "seq": 3,
                "product": "LP-FSC120-AA",
                "softNumber": "bogus",
                "fileSize": 1803924,
                "pyid": "0x756",
            },
        ],
    },
    "currentVersion": {
        "time": 1766605790000,
        "generalVersion": "0.00.00",
        "logJsonMultiLang": [],
    },
}


def _vehicle(vin=VIN):
    return Vehicle.from_dict(
        {"vin": vin, "carType": "T03", "vinNickname": "Leap"}, is_shared=False
    )


def _client(info=None, error=None):
    client = AsyncMock()
    if error:
        client.get_software_info.side_effect = error
    else:
        client.get_software_info.return_value = info or SoftwareInfo.from_dict(DATA)
    return client


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeRepo:
    def __init__(self):
        self.settings = {}

    async def get_setting(self, key):
        return self.settings.get(key)

    async def save_setting(self, key, value):
        self.settings[key] = value


# -- cache ------------------------------------------------------------------------


async def test_answer_is_cached_until_the_ttl_expires():
    clock = FakeClock()
    cache = SoftwareUpdates(ttl_seconds=60, clock=clock)
    client = _client()

    first = await cache.get(client, _vehicle())
    assert await cache.get(client, _vehicle()) is first
    assert client.get_software_info.await_count == 1

    clock.now += 61
    await cache.get(client, _vehicle())
    assert client.get_software_info.await_count == 2


async def test_refresh_bypasses_the_cache():
    cache = SoftwareUpdates()
    client = _client()
    await cache.get(client, _vehicle())
    await cache.get(client, _vehicle(), refresh=True)
    assert client.get_software_info.await_count == 2


async def test_shared_account_is_owner_only_and_cached():
    cache = SoftwareUpdates()
    client = _client(error=LeapmotorPermissionError("No such permission"))

    lookup = await cache.get(client, _vehicle())
    assert lookup.owner_only
    assert lookup.pending is None
    await cache.get(client, _vehicle())
    assert client.get_software_info.await_count == 1


async def test_other_cloud_errors_propagate_and_are_not_cached():
    cache = SoftwareUpdates()
    client = _client(error=LeapmotorApiError("boom"))
    with pytest.raises(LeapmotorApiError):
        await cache.get(client, _vehicle())
    assert cache.cached(VIN) is None


# -- presentation -----------------------------------------------------------------


def test_component_labels():
    info = SoftwareInfo.from_dict(DATA)
    labels = [component_label(p) for p in info.new_version.packages]
    assert labels == ["Charging communication", "Infotainment", None]


def test_format_size_is_decimal():
    assert format_size(1890801854) == "1.89 GB"
    assert format_size(600192) == "600.19 KB"
    assert format_size(12) == "12 B"


def test_home_assistant_state_keeps_the_cloud_installed_version():
    state = home_assistant_state(
        SimpleNamespace(info=SoftwareInfo.from_dict(DATA)), "it-IT"
    )
    assert state["installed_version"] == "0.00.00"
    assert state["latest_version"] == "1.03.12"
    assert state["release_summary"].startswith("Nuove funzionalità")
    assert len(state["release_summary"]) <= 255
    assert "\t" not in state["release_summary"]
    assert home_assistant_state(SimpleNamespace(info=None), "it-IT") is None


def test_home_assistant_state_up_to_date():
    info = SoftwareInfo.from_dict({"currentVersion": {"generalVersion": "3.41.30"}})
    state = home_assistant_state(SimpleNamespace(info=info), "en-US")
    assert state["installed_version"] == state["latest_version"] == "3.41.30"
    assert "release_summary" not in state


# -- notification -----------------------------------------------------------------


async def test_pending_update_is_notified_once_per_version():
    repo, dispatcher = FakeRepo(), AsyncMock()
    lookup = await SoftwareUpdates().get(_client(), _vehicle())

    assert await notify_pending_update(repo, dispatcher, _vehicle(), lookup, "it-IT")
    assert not await notify_pending_update(
        repo, dispatcher, _vehicle(), lookup, "it-IT"
    )

    dispatcher.dispatch_custom.assert_awaited_once()
    args, kwargs = dispatcher.dispatch_custom.await_args
    event, vin, name, context = args
    assert (event, vin, name) == (UPDATE_EVENT, VIN, "Leap")
    assert context["version"] == "1.03.12"
    assert context["installed"] == "unknown"
    assert context["packages"] == 3
    assert "Supporto linguistico" in context["notes"]
    assert kwargs["history_value"] == "1.03.12"
    assert repo.settings[f"{NOTIFIED_SETTING_PREFIX}{VIN}"] == "1.03.12"


async def test_no_notification_without_a_pending_update():
    repo, dispatcher = FakeRepo(), AsyncMock()
    info = SoftwareInfo.from_dict({"currentVersion": {"generalVersion": "3.41.30"}})
    lookup = await SoftwareUpdates().get(_client(info), _vehicle())
    assert not await notify_pending_update(
        repo, dispatcher, _vehicle(), lookup, "it-IT"
    )
    dispatcher.dispatch_custom.assert_not_awaited()


# -- endpoint ---------------------------------------------------------------------


@pytest.fixture
def software_client(auth_client):
    """Authenticated client with the container's cloud client stubbed out."""
    from leapconnect.container import container

    saved = container.client, container.vehicles
    stub = _client()
    container.client = stub
    container.vehicles = [_vehicle()]
    container.software_updates.clear()
    yield auth_client, stub
    container.client, container.vehicles = saved
    container.software_updates.clear()


def test_endpoint_returns_update_in_the_preferred_language(software_client):
    http, _ = software_client
    assert http.put("/api/preferences", json={"language": "it-IT"}).status_code == 200

    resp = http.get(f"/api/vehicles/{VIN}/software")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["current"]["version"] is None  # 0.00.00
    assert body["current"]["installed_at"] == 1766605790000
    update = body["update"]
    assert update["version"] == "1.03.12"
    assert update["campaign_id"] == 268958
    assert update["notes_language"] == "it-IT"
    assert (
        update["notes"][0]["content"] == "1. Supporto linguistico ampliato: lo sloveno."
    )
    assert update["languages"] == ["en-US", "it-IT", "zh-CN"]
    assert update["size_bytes"] == 600192 + 1715272438 + 1803924
    # Largest package first, with a readable component and ISO build date
    ivi = update["packages"][0]
    assert ivi["component"] == "Infotainment"
    assert ivi["build_date"] == "2026-07-16"
    fsc = next(p for p in update["packages"] if p["product"] == "LP-FSC120-AA")
    assert fsc["build_date"] is None
    # Signed links, hashes and signatures never leave the backend
    assert "secret" not in resp.text
    assert "downloadURL" not in resp.text


def test_endpoint_falls_back_to_english(software_client):
    http, _ = software_client
    http.put("/api/preferences", json={"language": "fr-FR"})
    body = http.get(f"/api/vehicles/{VIN}/software").json()
    assert body["update"]["notes_language"] == "en-US"


def test_endpoint_owner_only(software_client):
    http, stub = software_client
    stub.get_software_info.side_effect = LeapmotorPermissionError("No such permission")
    body = http.get(f"/api/vehicles/{VIN}/software?refresh=true").json()
    assert body["status"] == "owner_only"
    assert body["current"] is None and body["update"] is None


def test_language_preference_is_validated(auth_client):
    assert (
        auth_client.put("/api/preferences", json={"language": "it-IT"}).json()[
            "language"
        ]
        == "it-IT"
    )
    resp = auth_client.put("/api/preferences", json={"language": "<script>"})
    assert resp.status_code == 422


# -- package download -------------------------------------------------------------

EVCC_BYTES = bytes(range(256)) * 40
IVI_BYTES = b"ivi-encrypted-payload" * 100


@pytest.fixture
def fake_cdn(monkeypatch):
    """Serve the test packages from an in-memory CDN; records the requests."""
    import httpx

    from leapconnect.infrastructure import ota_cdn

    files = {
        "/ota/LP-EVCC120-AA_V2.00.07_R_20260325.bin.encrypt": EVCC_BYTES,
        "/ota/LP-IVI010-AA_V1.03.12_R_20260716.zip.encrypt": IVI_BYTES,
    }
    cdn = SimpleNamespace(requests=[], refuse=False)

    def handler(request):
        cdn.requests.append(request)
        if cdn.refuse:
            return httpx.Response(403, text="Access denied")
        data = files[request.url.path]
        headers = {"Accept-Ranges": "bytes", "ETag": '"abc"'}
        rng = request.headers.get("range")
        if rng:
            start = int(rng.removeprefix("bytes=").split("-")[0])
            headers["Content-Range"] = f"bytes {start}-{len(data) - 1}/{len(data)}"
            return httpx.Response(
                206, stream=httpx.ByteStream(data[start:]), headers=headers
            )
        headers["Content-Length"] = str(len(data))
        return httpx.Response(200, stream=httpx.ByteStream(data), headers=headers)

    real = httpx.AsyncClient
    monkeypatch.setattr(
        ota_cdn.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    return cdn


def test_endpoint_lists_downloadable_packages(software_client):
    http, _ = software_client
    packages = http.get(f"/api/vehicles/{VIN}/software").json()["update"]["packages"]
    by_seq = {p["seq"]: p for p in packages}
    assert by_seq[16]["file_name"] == "LP-EVCC120-AA_V2.00.07_R_20260325.bin.encrypt"
    assert by_seq[16]["downloadable"] is True
    assert by_seq[3]["downloadable"] is False  # no link


def test_download_one_package(software_client, fake_cdn, caplog):
    http, _ = software_client
    caplog.set_level("DEBUG")
    resp = http.get(f"/api/vehicles/{VIN}/software/packages/16/download")
    assert resp.status_code == 200
    assert resp.content == EVCC_BYTES
    assert resp.headers["content-length"] == str(len(EVCC_BYTES))
    assert resp.headers["accept-ranges"] == "bytes"
    assert (
        'filename="LP-EVCC120-AA_V2.00.07_R_20260325.bin.encrypt"'
        in resp.headers["content-disposition"]
    )
    sent = fake_cdn.requests[0]
    assert "authorization" not in sent.headers and "cookie" not in sent.headers
    assert "secret" not in caplog.text  # httpx logs the URL, signature redacted


def test_download_forwards_range(software_client, fake_cdn):
    http, _ = software_client
    resp = http.get(
        f"/api/vehicles/{VIN}/software/packages/16/download",
        headers={"Range": "bytes=1000-", "If-Range": '"abc"'},
    )
    assert resp.status_code == 206
    assert resp.content == EVCC_BYTES[1000:]
    assert resp.headers["content-range"] == f"bytes 1000-{len(EVCC_BYTES) - 1}/10240"
    assert fake_cdn.requests[0].headers["if-range"] == '"abc"'


def test_download_errors(software_client, fake_cdn):
    http, stub = software_client
    base = f"/api/vehicles/{VIN}/software"
    assert http.get(f"{base}/packages/99/download").status_code == 404
    assert http.get(f"{base}/packages/3/download").status_code == 404  # no link

    fake_cdn.refuse = True
    resp = http.get(f"{base}/packages/16/download")
    assert resp.status_code == 502
    assert "HTTP 403" in resp.json()["detail"] and "secret" not in resp.text

    stub.get_software_info.return_value = SoftwareInfo.from_dict(
        {"currentVersion": DATA["currentVersion"]}
    )
    http.get(f"{base}?refresh=true")
    assert http.get(f"{base}/download").status_code == 404

    stub.get_software_info.side_effect = LeapmotorPermissionError("No such permission")
    http.get(f"{base}?refresh=true")
    assert http.get(f"{base}/packages/16/download").status_code == 403


def test_download_whole_update_as_zip(software_client, fake_cdn):
    import io
    import json
    import zipfile

    http, _ = software_client
    resp = http.get(f"/api/vehicles/{VIN}/software/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert 'filename="Leapmotor-T03-1.03.12.zip"' in resp.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(resp.content))
    assert archive.testzip() is None
    assert archive.read("LP-EVCC120-AA_V2.00.07_R_20260325.bin.encrypt") == EVCC_BYTES
    assert archive.read("LP-IVI010-AA_V1.03.12_R_20260716.zip.encrypt") == IVI_BYTES
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["version"] == "1.03.12"
    assert [p["product"] for p in manifest["packages"]] == [
        "LP-EVCC120-AA",
        "LP-IVI010-AA",
    ]
    assert manifest["packages"][0]["encrypted"] is True
    assert "secret" not in json.dumps(manifest)


async def test_expiring_links_are_fetched_again():
    expired = {
        "newVersion": {
            "generalVersion": "1.03.12",
            "updateItemList": [
                {"seq": 1, "downloadURL": f"{CDN}/a.bin.encrypt?Expires=1000"}
            ],
        }
    }
    client = _client(info=SoftwareInfo.from_dict(expired))
    cache = SoftwareUpdates()
    await cache.for_download(client, _vehicle())
    assert client.get_software_info.await_count == 2

    client = _client()  # links valid until 2100
    await SoftwareUpdates().for_download(client, _vehicle())
    assert client.get_software_info.await_count == 1
