"""Car sharing, recipient side: answer the invitations sent to this account.

The owner shares the car from the official Leapmotor app. Until the
invitation is accepted the car is missing from the vehicle list and every
vehicle call answers ``No such permission``, so LeapConnect cannot see it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leapmotor_api.async_client import AsyncLeapmotorApiClient
    from leapmotor_api.models import ShareInvitation


class InvitationNotFoundError(LookupError):
    """No pending invitation for the requested VIN."""


async def answer_share_invitation(
    client: AsyncLeapmotorApiClient, vin: str, *, accept: bool
) -> ShareInvitation:
    """Accept or reject the pending invitation for ``vin``.

    The invitation is looked up again rather than trusted from the caller,
    since the cloud needs the owner id it carries. Raises
    ``InvitationNotFoundError`` when no invitation for ``vin`` is pending.
    """
    invitations = await client.get_share_invitations()
    invitation = next((i for i in invitations if i.vin == vin), None)
    if invitation is None:
        raise InvitationNotFoundError(vin)
    if accept:
        await client.accept_share_invitation(invitation)
    else:
        await client.reject_share_invitation(invitation)
    return invitation
