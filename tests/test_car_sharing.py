"""Tests for answering car-share invitations (recipient side)."""

from unittest.mock import AsyncMock

import pytest
from leapmotor_api.models import ShareInvitation, Vehicle

from leapconnect.application.car_sharing import (
    InvitationNotFoundError,
    answer_share_invitation,
)

VIN = "LSHARED0000000001"


def _invitation(vin=VIN):
    return ShareInvitation.from_dict(
        {
            "msgid": 7,
            "shareUserid": "owner-42",
            "carCode": vin,
            "carType": "B10",
            "carAlias": "Family car",
            "nickName": "Alex",
            "email": "owner@example.com",
            "shareTime": 1760000000000,
        }
    )


def _stub_client(invitations):
    client = AsyncMock()
    client.get_share_invitations.return_value = invitations
    client.get_vehicle_list.return_value = [
        Vehicle.from_dict({"vin": VIN, "carType": "B10"}, is_shared=True)
    ]
    return client


# -- use case ---------------------------------------------------------------------


async def test_accept_answers_the_matching_invitation():
    other = _invitation("LOTHER00000000002")
    client = _stub_client([other, _invitation()])

    invitation = await answer_share_invitation(client, VIN, accept=True)

    assert invitation.share_user_id == "owner-42"
    client.accept_share_invitation.assert_awaited_once_with(invitation)
    client.reject_share_invitation.assert_not_awaited()


async def test_reject_answers_the_matching_invitation():
    client = _stub_client([_invitation()])
    await answer_share_invitation(client, VIN, accept=False)
    client.reject_share_invitation.assert_awaited_once()
    client.accept_share_invitation.assert_not_awaited()


async def test_unknown_vin_is_not_answered():
    client = _stub_client([_invitation()])
    with pytest.raises(InvitationNotFoundError):
        await answer_share_invitation(client, "LNOPE000000000003", accept=True)
    client.accept_share_invitation.assert_not_awaited()


# -- endpoints --------------------------------------------------------------------


@pytest.fixture
def sharing_client(auth_client):
    """Authenticated client with the container's cloud client stubbed out."""
    from leapconnect.container import container

    saved = container.client, container.vehicles
    stub = _stub_client([_invitation()])
    container.client = stub
    yield auth_client, stub, container
    container.client, container.vehicles = saved


def test_list_invitations(sharing_client):
    http, _, _ = sharing_client
    resp = http.get("/api/share-invitations")
    assert resp.status_code == 200
    (inv,) = resp.json()["invitations"]
    assert inv["vin"] == VIN
    assert inv["owner_nickname"] == "Alex"
    assert inv["car_alias"] == "Family car"
    assert "share_user_id" not in inv  # the owner id stays server-side


def test_accept_refreshes_the_vehicle_list(sharing_client):
    http, stub, container = sharing_client
    resp = http.post(f"/api/share-invitations/{VIN}/accept")
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert [v["vin"] for v in body["vehicles"]] == [VIN]
    assert [v.vin for v in container.vehicles] == [VIN]
    stub.accept_share_invitation.assert_awaited_once()


def test_answering_unknown_invitation_is_404(sharing_client):
    http, stub, _ = sharing_client
    resp = http.post("/api/share-invitations/LNOPE000000000003/reject")
    assert resp.status_code == 404
    stub.reject_share_invitation.assert_not_awaited()
