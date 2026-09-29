"""Simple in-memory conversation state manager.

Replaces python-telegram-bot's ConversationHandler.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConversationData:
    """Data stored per conversation (user + chat)."""

    state: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)


class ConversationManager:
    """Manages conversation state for each user/chat pair."""

    def __init__(self) -> None:
        # Key: (user_id, chat_id) -> ConversationData
        self._conversations: dict[tuple[int, int], ConversationData] = {}

    def _key(self, user_id: int, chat_id: int) -> tuple[int, int]:
        return (user_id, chat_id)

    def get_state(self, user_id: int, chat_id: int) -> Optional[str]:
        """Get the current conversation state."""
        data = self._conversations.get(self._key(user_id, chat_id))
        return data.state if data else None

    def set_state(self, user_id: int, chat_id: int, state: Optional[str]) -> None:
        """Set the conversation state."""
        key = self._key(user_id, chat_id)
        if key not in self._conversations:
            self._conversations[key] = ConversationData()
        self._conversations[key].state = state
        logger.debug("Conversation state set for %s: %s", key, state)

    def clear_state(self, user_id: int, chat_id: int) -> None:
        """Clear the conversation state and data."""
        key = self._key(user_id, chat_id)
        if key in self._conversations:
            del self._conversations[key]
            logger.debug("Conversation cleared for %s", key)

    def get_data(self, user_id: int, chat_id: int) -> dict[str, Any]:
        """Get all conversation data."""
        data = self._conversations.get(self._key(user_id, chat_id))
        return data.data if data else {}

    def set_data(self, user_id: int, chat_id: int, key: str, value: Any) -> None:
        """Set a value in conversation data."""
        conv_key = self._key(user_id, chat_id)
        if conv_key not in self._conversations:
            self._conversations[conv_key] = ConversationData()
        self._conversations[conv_key].data[key] = value

    def get_data_value(self, user_id: int, chat_id: int, key: str, default: Any = None) -> Any:
        """Get a specific value from conversation data."""
        data = self._conversations.get(self._key(user_id, chat_id))
        if data:
            return data.data.get(key, default)
        return default

    def clear_data(self, user_id: int, chat_id: int) -> None:
        """Clear only the data, keep the state."""
        data = self._conversations.get(self._key(user_id, chat_id))
        if data:
            data.data.clear()


# Global instance
conversation_manager = ConversationManager()