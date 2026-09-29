"""Inline keyboard of the admin panel.

Pure Python implementation, no python-telegram-bot dependency.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InlineKeyboardButton:
    """Inline keyboard button."""
    text: str
    callback_data: str


@dataclass
class InlineKeyboardMarkup:
    """Inline keyboard markup."""
    inline_keyboard: list[list[InlineKeyboardButton]]


# Namespaced callback data so future buttons cannot collide with these.
CHANGE_IP_CALLBACK = "admin:change_ip"


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("🔄 تغییر IP", callback_data=CHANGE_IP_CALLBACK)]
        ]
    )