"""Inline keyboard of the admin panel."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Namespaced callback data so future buttons cannot collide with these.
CHANGE_IP_CALLBACK = "admin:change_ip"


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔄 تغییر IP", callback_data=CHANGE_IP_CALLBACK)]]
    )
