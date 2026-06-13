"""Shared Telegram configuration used by both the notifier and the bot service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TelegramConfig:
    """Telegram Bot API connection parameters."""

    bot_token: str
    chat_id: str
    bot_enabled: bool = True

    @property
    def base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    @property
    def is_valid(self) -> bool:
        return bool(self.bot_token and self.chat_id)
