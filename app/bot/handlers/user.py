"""User flow: ``/start`` → receive a config → return it with the new host."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.bot import texts
from app.bot.dependencies import get_dependencies
from app.services.config_replacer import (
    InvalidConfigError,
    UnsupportedProtocolError,
    replace_config_host,
)

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message shown by ``/start`` (and ``/help``)."""
    if update.effective_message is not None:
        await update.effective_message.reply_text(texts.WELCOME)


async def handle_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replace the host of the config the user sent."""
    message = update.effective_message
    if message is None or not message.text:
        return

    current_host = await get_dependencies(context).settings_repo.get_replacement_ip()
    if not current_host:
        await message.reply_text(texts.NO_IP_CONFIGURED)
        return

    try:
        result = replace_config_host(message.text, current_host)
    except UnsupportedProtocolError:
        logger.info("Unsupported config from %s", update.effective_user)
        await message.reply_text(texts.UNSUPPORTED_CONFIG)
        return
    except InvalidConfigError:
        logger.info("Invalid config from %s", update.effective_user)
        await message.reply_text(texts.INVALID_CONFIG)
        return
    except Exception:
        # Never leak internals to the user.
        logger.exception("Unexpected error while processing a config")
        await message.reply_text(texts.INTERNAL_ERROR)
        return

    logger.info(
        "Config processed for %s: %s -> %s",
        update.effective_user,
        result.old_host,
        result.new_host,
    )
    await message.reply_text(texts.config_ready(result.config), parse_mode=ParseMode.HTML)


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answer commands the bot does not know instead of staying silent."""
    if update.effective_message is not None:
        await update.effective_message.reply_text(texts.UNKNOWN_COMMAND)


def register_user_handlers(application: Application) -> None:
    """Register the public handlers.

    They join the very same group as the admin conversation, which must be added
    first: inside a group only the first matching handler runs, so an admin
    answering the «IP جدید» prompt is handled by the conversation while a
    regular user's config falls through to :func:`handle_config`.
    """
    application.add_handler(CommandHandler(["start", "help"], start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_config)
    )
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
