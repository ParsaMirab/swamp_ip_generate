"""Update router - routes Telegram updates to appropriate handlers.

Replaces python-telegram-bot's Application handler registration and dispatch.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Awaitable

from app.bot.conversation import conversation_manager
from app.bot.context import BotContext
from app.bot.dependencies import BotDependencies
from app.bot.telegram_client import TelegramClient

logger = logging.getLogger(__name__)

# Type for handler functions
Handler = Callable[[dict[str, Any], BotContext], Awaitable[None]]


class BotRouter:
    """Routes updates to registered handlers."""

    def __init__(
        self,
        telegram: TelegramClient,
        dependencies: BotDependencies,
    ) -> None:
        self._telegram = telegram
        self._dependencies = dependencies
        self._command_handlers: dict[str, Handler] = {}
        self._message_handlers: list[Handler] = []
        self._callback_handlers: dict[str, Handler] = {}
        self._default_handler: Handler | None = None

    # --- Registration methods ---

    def add_command_handler(self, command: str, handler: Handler) -> None:
        """Register a handler for a specific command (e.g., 'start', 'admin')."""
        self._command_handlers[command.lower()] = handler
        logger.debug("Registered command handler: /%s", command)

    def add_message_handler(self, handler: Handler) -> None:
        """Register a handler for text messages (non-commands)."""
        self._message_handlers.append(handler)
        logger.debug("Registered message handler")

    def add_callback_handler(self, pattern: str, handler: Handler) -> None:
        """Register a handler for a callback query pattern (exact match or regex)."""
        self._callback_handlers[pattern] = handler
        logger.debug("Registered callback handler: %s", pattern)

    def set_default_handler(self, handler: Handler) -> None:
        """Set the default handler for unmatched updates."""
        self._default_handler = handler
        logger.debug("Registered default handler")

    # --- Update handling ---

    async def handle(self, update: dict[str, Any]) -> None:
        """Process a single update."""
        update_id = update.get("update_id", "unknown")
        logger.debug("Processing update_id=%s", update_id)

        try:
            # Extract user and chat info
            user = update.get("message", {}).get("from") or \
                   update.get("callback_query", {}).get("from") or \
                   update.get("inline_query", {}).get("from") or \
                   update.get("chat_member", {}).get("from") or \
                   update.get("my_chat_member", {}).get("from") or \
                   {}

            chat = update.get("message", {}).get("chat") or \
                   update.get("callback_query", {}).get("message", {}).get("chat") or \
                   {}

            # Build context
            context = BotContext(
                bot=self._telegram,
                user=user,
                chat=chat,
                update=update,
                conversation=conversation_manager,
                dependencies=self._dependencies,
            )

            # Route based on update type
            if "message" in update:
                await self._handle_message(update["message"], context)
            elif "callback_query" in update:
                await self._handle_callback_query(update["callback_query"], context)
            elif "inline_query" in update:
                await self._handle_inline_query(update["inline_query"], context)
            elif "chat_member" in update:
                await self._handle_chat_member(update["chat_member"], context)
            elif "my_chat_member" in update:
                await self._handle_my_chat_member(update["my_chat_member"], context)
            else:
                logger.debug("Unhandled update type: %s", list(update.keys()))

        except Exception:
            logger.exception("Error handling update_id=%s", update_id)

    async def _handle_message(self, message: dict[str, Any], context: BotContext) -> None:
        """Handle a message update."""
        text = message.get("text", "")

        # Check for command
        if text.startswith("/"):
            command = text[1:].split("@")[0].split()[0].lower()
            handler = self._command_handlers.get(command)
            if handler:
                logger.debug("Routing command /%s to handler", command)
                await handler(message, context)
                return

            # Unknown command
            if self._default_handler:
                await self._default_handler(message, context)
            return

        # Check conversation state first
        user_id = context.user_id
        chat_id = context.chat_id

        if user_id is not None and chat_id is not None:
            state = conversation_manager.get_state(user_id, chat_id)
            if state:
                logger.debug("Conversation state active: %s", state)
                # State-specific handlers would be registered as message handlers
                # and checked in order

        # Regular message handlers
        for handler in self._message_handlers:
            await handler(message, context)

    async def _handle_callback_query(
        self,
        callback_query: dict[str, Any],
        context: BotContext,
    ) -> None:
        """Handle a callback query update."""
        data = callback_query.get("data", "")
        query_id = callback_query.get("id")

        # Answer callback query immediately to remove loading state
        if query_id:
            try:
                await self._telegram.answer_callback_query(query_id)
            except Exception:
                logger.exception("Failed to answer callback query")

        # Try exact match first
        handler = self._callback_handlers.get(data)
        if handler:
            logger.debug("Routing callback %s to handler", data)
            await handler(callback_query, context)
            return

        # Try regex patterns
        for pattern, handler in self._callback_handlers.items():
            if re.fullmatch(pattern, data):
                logger.debug("Routing callback %s to regex handler %s", data, pattern)
                await handler(callback_query, context)
                return

        logger.debug("No handler for callback: %s", data)

    async def _handle_inline_query(
        self,
        inline_query: dict[str, Any],
        context: BotContext,
    ) -> None:
        """Handle an inline query update."""
        logger.debug("Inline query received (not implemented)")

    async def _handle_chat_member(
        self,
        chat_member: dict[str, Any],
        context: BotContext,
    ) -> None:
        """Handle a chat member update."""
        logger.debug("Chat member update received (not implemented)")

    async def _handle_my_chat_member(
        self,
        my_chat_member: dict[str, Any],
        context: BotContext,
    ) -> None:
        """Handle a my chat member update."""
        logger.debug("My chat member update received (not implemented)")