"""User flow: ``/start`` → receive a config → return it with the new host."""

from __future__ import annotations

import logging

from app.bot import texts
from app.bot.context import BotContext
from app.bot.dependencies import get_dependencies
from app.services.config_replacer import (
    InvalidConfigError,
    UnsupportedProtocolError,
    replace_config_host,
)

logger = logging.getLogger(__name__)


async def start(update: dict, context: BotContext) -> None:
    """Welcome message shown by ``/start`` (and ``/help``)."""
    await context.send_message(texts.WELCOME)


async def handle_config(update: dict, context: BotContext) -> None:
    """Replace the host of the config the user sent."""
    message = update.get("message", {})
    text = message.get("text", "")

    if not text:
        return

    # Skip if this is handled by admin conversation
    if context.user_id and context.chat_id:
        from app.bot.conversation import conversation_manager
        state = conversation_manager.get_state(context.user_id, context.chat_id)
        if state == "admin:waiting_for_ip":
            return  # Let admin handler process this

    current_host = await context.dependencies.settings_repo.get_replacement_ip()
    if not current_host:
        await context.send_message(texts.NO_IP_CONFIGURED)
        return

    try:
        result = replace_config_host(text, current_host)
    except UnsupportedProtocolError:
        logger.info("Unsupported config from %s", context.user_id)
        await context.send_message(texts.UNSUPPORTED_CONFIG)
        return
    except InvalidConfigError:
        logger.info("Invalid config from %s", context.user_id)
        await context.send_message(texts.INVALID_CONFIG)
        return
    except Exception:
        # Never leak internals to the user.
        logger.exception("Unexpected error while processing a config")
        await context.send_message(texts.INTERNAL_ERROR)
        return

    logger.info(
        "Config processed for %s: %s -> %s",
        context.user_id,
        result.old_host,
        result.new_host,
    )
    await context.send_message(texts.config_ready(result.config), parse_mode="HTML")


async def unknown_command(update: dict, context: BotContext) -> None:
    """Answer commands the bot does not know instead of staying silent."""
    await context.send_message(texts.UNKNOWN_COMMAND)


def register_user_handlers(router) -> None:
    """Register the public handlers."""
    router.add_command_handler("start", start)
    router.add_command_handler("help", start)
    router.add_message_handler(handle_config)
    router.set_default_handler(unknown_command)