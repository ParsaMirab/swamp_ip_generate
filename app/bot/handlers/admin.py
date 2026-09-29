"""Admin panel: ``/admin`` → «تغییر IP» → persist the new host.

Authorization is checked on *every* entry point (command, callback button and
the message that carries the IP), so nothing in this module can be reached by a
regular user — not even by replaying the callback data.
"""

from __future__ import annotations

import logging
import re

from app.bot import texts
from app.bot.context import BotContext
from app.bot.dependencies import get_dependencies
from app.bot.keyboards.admin import CHANGE_IP_CALLBACK, admin_panel_keyboard
from app.bot.conversation import conversation_manager
from app.services.host_validator import InvalidHostError, validate_host

logger = logging.getLogger(__name__)

ADMIN_STATE_WAITING_FOR_IP = "admin:waiting_for_ip"


def _is_admin(update: dict, context: BotContext) -> bool:
    return context.dependencies.settings.is_admin(context.user_id)


async def admin_panel(update: dict, context: BotContext) -> None:
    """``/admin`` entry point: show the panel with the current IP."""
    if not _is_admin(update, context):
        logger.warning("Unauthorized /admin attempt by user %s", context.user_id)
        await context.send_message(texts.NOT_ADMIN)
        return

    current_host = await context.dependencies.settings_repo.get_replacement_ip()
    await context.send_message(
        texts.admin_panel(current_host),
        parse_mode="HTML",
        reply_markup=_keyboard_to_dict(admin_panel_keyboard()),
    )


async def change_ip_entry(update: dict, context: BotContext) -> None:
    """«🔄 تغییر IP» button: ask the admin for the new IP and wait for it."""
    callback_query = update.get("callback_query", {})
    query_id = callback_query.get("id")

    if not _is_admin(update, context):
        logger.warning(
            "Unauthorized %s callback by user %s",
            CHANGE_IP_CALLBACK,
            context.user_id,
        )

        if query_id:
            await context.bot.answer_callback_query(
                query_id,
                texts.NOT_ADMIN,
                show_alert=True,
            )
        return

    if query_id:
        await context.bot.answer_callback_query(query_id)

    await context.send_message(texts.ASK_FOR_IP)

    if context.user_id and context.chat_id:
        conversation_manager.set_state(
            context.user_id,
            context.chat_id,
            ADMIN_STATE_WAITING_FOR_IP,
        )

async def receive_ip(update: dict, context: BotContext) -> None:
    """Validate the IP the admin sent and persist it."""
    message = update.get("message", {})
    text = message.get("text", "")

    if not _is_admin(update, context):
        await context.send_message(texts.NOT_ADMIN)
        return

    try:
        host = validate_host(text)
    except InvalidHostError as exc:
        await context.send_message(texts.invalid_ip(str(exc)))
        return

    try:
        await context.dependencies.settings_repo.set_replacement_ip(host)
    except Exception:
        logger.exception("Failed to persist the replacement IP")
        await context.send_message(texts.INTERNAL_ERROR)
        if context.user_id and context.chat_id:
            conversation_manager.clear_state(context.user_id, context.chat_id)
        return

    logger.info("Replacement IP updated to %s by %s", host, context.user_id)
    await context.send_message(texts.ip_saved(host), parse_mode="HTML")

    # Clear conversation state
    if context.user_id and context.chat_id:
        conversation_manager.clear_state(context.user_id, context.chat_id)


async def cancel(update: dict, context: BotContext) -> None:
    """``/cancel``: leave the flow without changing anything."""
    await context.send_message(texts.CANCELLED)
    if context.user_id and context.chat_id:
        conversation_manager.clear_state(context.user_id, context.chat_id)


def _keyboard_to_dict(keyboard) -> dict:
    """Convert telegram.InlineKeyboardMarkup to dict for our client."""
    # The keyboard is already a simple structure we can serialize
    return {
        "inline_keyboard": [
            [
                {"text": btn.text, "callback_data": btn.callback_data}
                for btn in row
            ]
            for row in keyboard.inline_keyboard
        ]
    }


def register_admin_handlers(router) -> None:
    """Register admin handlers with the router."""
    router.add_command_handler("admin", admin_panel)
    router.add_command_handler("cancel", cancel)
    router.add_callback_handler(CHANGE_IP_CALLBACK, change_ip_entry)

    # Register message handler for admin state
    async def admin_message_handler(update: dict, context: BotContext) -> None:
        if context.user_id and context.chat_id:
            state = conversation_manager.get_state(context.user_id, context.chat_id)
            if state == ADMIN_STATE_WAITING_FOR_IP:
                await receive_ip(update, context)

    router.add_message_handler(admin_message_handler)