"""Admin panel: ``/admin`` → «تغییر IP» → persist the new host.

Authorization is checked on *every* entry point (command, callback button and
the message that carries the IP), so nothing in this module can be reached by a
regular user — not even by replaying the callback data.
"""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot import texts
from app.bot.dependencies import get_dependencies
from app.bot.keyboards.admin import CHANGE_IP_CALLBACK, admin_panel_keyboard
from app.bot.states import AdminState
from app.services.host_validator import InvalidHostError, validate_host

logger = logging.getLogger(__name__)


def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return get_dependencies(context).settings.is_admin(
        update.effective_user.id if update.effective_user else None
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """``/admin`` entry point: show the panel with the current IP."""
    message = update.effective_message
    if message is None:
        return ConversationHandler.END

    if not _is_admin(update, context):
        logger.warning("Unauthorized /admin attempt by user %s", update.effective_user)
        await message.reply_text(texts.NOT_ADMIN)
        return ConversationHandler.END

    current_host = await get_dependencies(context).settings_repo.get_replacement_ip()
    await message.reply_text(
        texts.admin_panel(current_host),
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel_keyboard(),
    )
    return ConversationHandler.END


async def change_ip_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """«🔄 تغییر IP» button: ask the admin for the new IP and wait for it."""
    query = update.callback_query
    if query is None:
        return ConversationHandler.END

    if not _is_admin(update, context):
        logger.warning(
            "Unauthorized %s callback by user %s", CHANGE_IP_CALLBACK, update.effective_user
        )
        await query.answer(texts.NOT_ADMIN, show_alert=True)
        return ConversationHandler.END

    await query.answer()

    if query.message is None:
        await query.edit_message_text(texts.ADMIN_CALLBACK_EXPIRED)
        return ConversationHandler.END

    await query.message.reply_text(texts.ASK_FOR_IP)
    return AdminState.WAITING_FOR_IP


async def receive_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Validate the IP the admin sent and persist it."""
    message = update.effective_message
    if message is None:
        return ConversationHandler.END

    if not _is_admin(update, context):
        await message.reply_text(texts.NOT_ADMIN)
        return ConversationHandler.END

    try:
        host = validate_host(message.text or "")
    except InvalidHostError as exc:
        await message.reply_text(texts.invalid_ip(str(exc)))
        return AdminState.WAITING_FOR_IP

    try:
        await get_dependencies(context).settings_repo.set_replacement_ip(host)
    except Exception:
        logger.exception("Failed to persist the replacement IP")
        await message.reply_text(texts.INTERNAL_ERROR)
        return ConversationHandler.END

    logger.info("Replacement IP updated to %s by %s", host, update.effective_user)
    await message.reply_text(texts.ip_saved(host), parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """``/cancel``: leave the flow without changing anything."""
    if update.effective_message is not None:
        await update.effective_message.reply_text(texts.CANCELLED)
    return ConversationHandler.END


def build_admin_conversation() -> ConversationHandler:
    """Assemble the (single state) admin conversation."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_panel),
            CallbackQueryHandler(
                change_ip_entry, pattern=rf"^{re.escape(CHANGE_IP_CALLBACK)}$"
            ),
        ],
        states={
            AdminState.WAITING_FOR_IP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ip),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("admin", admin_panel),
        ],
        name="admin_conversation",
    )
