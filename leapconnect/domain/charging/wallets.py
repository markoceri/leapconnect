"""A charging provider account's wallets and payments (pure domain).

A provider is paid from a wallet: in money (EUR) or in its own tokens, worth
``token_rate`` tokens per unit of money. The wallet movements tell what was
actually paid for each billed session, which is checked against the bill.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

# Paid and billed amounts agree within this (rounding of the token rate)
MATCH_TOLERANCE = 0.02  # in money


@dataclass(frozen=True)
class ProviderWallet:
    """A wallet and its balance, in its currency."""

    provider: str
    currency: str
    balance: float
    is_token: bool = False
    is_primary: bool = False
    name: str | None = None
    symbol: str | None = None
    # Tokens per unit of money (token wallets; None when not known yet)
    token_rate: float | None = None

    @property
    def money_value(self) -> float | None:
        """The balance in money: as it is, or tokens ÷ the rate."""
        if not self.is_token:
            return self.balance
        if not self.token_rate:
            return None
        return round(self.balance / self.token_rate, 2)


def spendable(wallets: Sequence[ProviderWallet]) -> float | None:
    """What the account can spend, in money; ``None`` when a token wallet's
    worth is unknown and nothing else is known."""
    values = [w.money_value for w in wallets]
    known = [v for v in values if v is not None]
    if not known:
        return None
    return round(sum(known), 2)


def is_low(wallets: Sequence[ProviderWallet], threshold: float | None) -> bool:
    """The spendable balance is under ``threshold`` (no threshold: never)."""
    if threshold is None:
        return False
    total = spendable(wallets)
    return total is not None and total < threshold


@dataclass(frozen=True)
class ProviderPayment:
    """A wallet movement: negative pays, positive refunds or tops up."""

    provider: str
    payment_id: str
    amount: float  # in ``currency``
    currency: str | None = None
    is_token: bool = False
    category: str | None = None  # e.g. "charging", "transfer"
    description: str | None = None
    session_id: str | None = None  # the billed session it settled
    created_at: datetime | None = None  # naive UTC


# How what was paid compares with the bill
PAID_TOTAL = "total"  # the billed total (energy and fees)
PAID_ENERGY = "energy"  # the billed total without the fees
PAID_OTHER = "other"


@dataclass(frozen=True)
class PaymentCheck:
    """What was paid for a billed session, in money."""

    payments: tuple[ProviderPayment, ...]
    paid: float  # net, positive: paid minus refunded
    refunded: float
    matches: str | None  # PAID_TOTAL | PAID_ENERGY | PAID_OTHER; None: nothing paid


def check_payments(
    payments: Sequence[ProviderPayment],
    session_id: str,
    billed_total: float | None,
    billed_fees: float = 0.0,
    token_rate: float | None = None,
) -> PaymentCheck:
    """The movements of a billed session, their net in money and whether it
    matches the billed total, the total without the fees, or neither.
    Token movements are converted with ``token_rate`` (the session's)."""
    own = tuple(p for p in payments if p.session_id == session_id)

    def money(p: ProviderPayment) -> float | None:
        if not p.is_token:
            return p.amount
        return p.amount / token_rate if token_rate else None

    values = [money(p) for p in own]
    known = [v for v in values if v is not None]
    paid = round(-sum(known), 2)
    refunded = round(sum(v for v in known if v > 0), 2)
    if not known:
        return PaymentCheck(own, 0.0, 0.0, None)
    matches = PAID_OTHER
    if billed_total is not None:
        if abs(paid - billed_total) <= MATCH_TOLERANCE:
            matches = PAID_TOTAL
        elif (
            billed_fees and abs(paid - (billed_total - billed_fees)) <= MATCH_TOLERANCE
        ):
            matches = PAID_ENERGY
    return PaymentCheck(own, paid, refunded, matches)
