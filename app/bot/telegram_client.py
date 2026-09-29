"""Telegram Bot API client using aiohttp.

All HTTP requests to Telegram Bot API go through this client.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramError(Exception):
    """Error returned by Telegram Bot API."""

    code: int
    description: str
    parameters: Optional[dict[str, Any]] = None

    def __str__(self) -> str:
        return f"Telegram API error {self.code}: {self.description}"


class TelegramClient:
    """Minimal Telegram Bot API client backed by aiohttp."""

    API_BASE = "https://api.telegram.org/bot"

    def __init__(self, token: str) -> None:
        self._token = token
        self._base_url = f"{self.API_BASE}{token}"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=None,
                connect=30,
                sock_connect=30,
                sock_read=60,
            )
            connector = aiohttp.TCPConnector(
                limit=16,
                family=2,
                ssl=True,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                trust_env=False,
            )
            logger.info("Telegram client session created")
        return self._session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            logger.info("Telegram client session closed")

    def _build_url(self, method: str) -> str:
        return f"{self._base_url}/{method}"

    async def _request(
        self,
        method: str,
        data: Optional[dict[str, Any]] = None,
        retry_after: float = 0,
    ) -> dict[str, Any]:
        """Execute a Telegram API request with retry logic."""
        session = await self._get_session()
        url = self._build_url(method)

        for attempt in range(5):
            try:
                if data:
                    async with session.post(url, json=data) as response:
                        response_data = await response.json()
                else:
                    async with session.get(url) as response:
                        response_data = await response.json()

                if response_data.get("ok"):
                    return response_data.get("result", {})

                # Handle API errors
                error_code = response_data.get("error_code", 0)
                description = response_data.get("description", "Unknown error")
                parameters = response_data.get("parameters")

                if error_code == 429:
                    # Too Many Requests - respect retry_after
                    retry_after = parameters.get("retry_after", 1) if parameters else 1
                    logger.warning(
                        "Rate limited by Telegram, waiting %.1fs (attempt %d/5)",
                        retry_after,
                        attempt + 1,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if error_code in (401, 403, 409):
                    logger.error("Telegram API error %d: %s", error_code, description)
                    raise TelegramError(
                        code=error_code,
                        description=description,
                        parameters=parameters,
                    )

                if 500 <= error_code < 600:
                    # Server errors - retry with backoff
                    backoff = min(2**attempt, 30)
                    logger.warning(
                        "Telegram server error %d, retrying in %ds (attempt %d/5)",
                        error_code,
                        backoff,
                        attempt + 1,
                    )
                    await asyncio.sleep(backoff)
                    continue

                logger.error("Telegram API error %d: %s", error_code, description)
                raise TelegramError(
                    code=error_code,
                    description=description,
                    parameters=parameters,
                )

            except aiohttp.ClientError as exc:
                backoff = min(2**attempt, 30)
                logger.warning(
                    "Network error: %s, retrying in %ds (attempt %d/5)",
                    exc,
                    backoff,
                    attempt + 1,
                )
                await asyncio.sleep(backoff)
                continue

        raise TelegramError(
            code=0,
            description="Max retries exceeded",
        )

    # --- Telegram Bot API methods ---

    async def get_me(self) -> dict[str, Any]:
        """Get basic information about the bot."""
        return await self._request("getMe")

    async def get_updates(
        self,
        offset: int = 0,
        limit: int = 100,
        timeout: int = 20,
        allowed_updates: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get updates via long polling."""
        params = {
            "offset": offset,
            "limit": limit,
            "timeout": timeout,
        }
        if allowed_updates:
            params["allowed_updates"] = allowed_updates

        result = await self._request("getUpdates", data=params)
        return result if isinstance(result, list) else []

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[dict[str, Any]] = None,
        disable_web_page_preview: bool = False,
        reply_to_message_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Send a text message."""
        data = {
            "chat_id": chat_id,
            "text": text,
        }
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = reply_markup
        if disable_web_page_preview:
            data["disable_web_page_preview"] = True
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id

        return await self._request("sendMessage", data=data)

    async def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Edit a text message."""
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = reply_markup

        return await self._request("editMessageText", data=data)

    async def delete_message(
        self,
        chat_id: int | str,
        message_id: int,
    ) -> dict[str, Any]:
        """Delete a message."""
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
        }
        return await self._request("deleteMessage", data=data)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        """Answer a callback query."""
        data = {
            "callback_query_id": callback_query_id,
        }
        if text:
            data["text"] = text
        if show_alert:
            data["show_alert"] = True

        return await self._request("answerCallbackQuery", data=data)

    async def send_photo(
        self,
        chat_id: int | str,
        photo: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Send a photo."""
        data = {
            "chat_id": chat_id,
            "photo": photo,
        }
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = reply_markup

        return await self._request("sendPhoto", data=data)

    async def send_document(
        self,
        chat_id: int | str,
        document: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Send a document."""
        data = {
            "chat_id": chat_id,
            "document": document,
        }
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        if reply_markup:
            data["reply_markup"] = reply_markup

        return await self._request("sendDocument", data=data)

    async def set_my_commands(
        self,
        commands: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Set the list of bot commands."""
        data = {
            "commands": commands,
        }
        return await self._request("setMyCommands", data=data)

    # Convenience methods for common operations

    async def send_admin_message(self, chat_id: int, text: str, **kwargs: Any) -> dict[str, Any]:
        """Send a message with HTML parse mode (for admin panel)."""
        return await self.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            **kwargs,
        )