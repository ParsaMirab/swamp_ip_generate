"""Internal BotContext to replace python-telegram-bot's ContextTypes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.bot.conversation import ConversationManager, conversation_manager
from app.bot.dependencies import BotDependencies
from app.bot.telegram_client import TelegramClient


@dataclass
class BotContext:
    """Context passed to handlers, replacing PTB's ContextTypes.

    Contains:
    - bot: TelegramClient for sending messages
    - user: User info from update
    - chat: Chat info from update
    - update: Raw update dict
    - conversation: ConversationManager for state management
    - dependencies: BotDependencies (settings, database, etc.)
    """

    bot: TelegramClient
    user: dict[str, Any]
    chat: dict[str, Any]
    update: dict[str, Any]
    conversation: ConversationManager
    dependencies: BotDependencies

    @property
    def user_id(self) -> Optional[int]:
        return self.user.get("id")

    @property
    def chat_id(self) -> Optional[int]:
        return self.chat.get("id")

    @property
    def user_data(self) -> dict[str, Any]:
        """Compatibility property for code expecting context.user_data."""
        if self.user_id is None or self.chat_id is None:
            return {}
        return self.conversation.get_data(self.user_id, self.chat_id)

    @property
    def chat_data(self) -> dict[str, Any]:
        """Compatibility property for code expecting context.chat_data."""
        if self.chat_id is None:
            return {}
        # Chat data is shared across users in the same chat
        return self.conversation.get_data(0, self.chat_id)

    @property
    def state(self) -> Optional[str]:
        """Get current conversation state."""
        if self.user_id is None or self.chat_id is None:
            return None
        return self.conversation.get_state(self.user_id, self.chat_id)

    @state.setter
    def state(self, value: Optional[str]) -> None:
        """Set conversation state."""
        if self.user_id is not None and self.chat_id is not None:
            self.conversation.set_state(self.user_id, self.chat_id, value)

    def clear_state(self) -> None:
        """Clear conversation state."""
        if self.user_id is not None and self.chat_id is not None:
            self.conversation.clear_state(self.user_id, self.chat_id)

    async def send_message(
        self,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a message to the current chat."""
        chat_id = self.chat_id
        if chat_id is None:
            raise ValueError("No chat_id available in context")
        return await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )

    async def edit_message_text(
        self,
        message_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Edit a message in the current chat."""
        chat_id = self.chat_id
        if chat_id is None:
            raise ValueError("No chat_id available in context")
        return await self.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        """Answer a callback query."""
        return await self.bot.answer_callback_query(
            callback_query_id=callback_query_id,
            text=text,
            show_alert=show_alert,
        )