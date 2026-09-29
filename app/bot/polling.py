"""Custom long polling implementation for Telegram Bot API.

Replaces python-telegram-bot's Application.run_polling().
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any, Callable, Optional

from app.bot.telegram_client import TelegramClient, TelegramError

logger = logging.getLogger(__name__)


class PollingManager:
    """Manages long polling loop with automatic retry and graceful shutdown."""

    def __init__(
        self,
        telegram: TelegramClient,
        handle_update: Callable[[dict[str, Any]], Any],
        allowed_updates: Optional[list[str]] = None,
        timeout: int = 20,
    ) -> None:
        self._telegram = telegram
        self._handle_update = handle_update
        self._allowed_updates = allowed_updates
        self._timeout = timeout
        self._offset = 0
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the polling loop."""
        if self._running:
            logger.warning("Polling already running")
            return

        self._running = True
        logger.info("Polling started")
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop the polling loop gracefully."""
        if not self._running:
            return

        logger.info("Stopping polling...")
        self._running = False

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Polling stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop with exponential backoff on errors."""
        backoff = 1

        while self._running:
            try:
                updates = await self._telegram.get_updates(
                    offset=self._offset,
                    timeout=self._timeout,
                    allowed_updates=self._allowed_updates,
                )

                if updates:
                    logger.debug("Received %d update(s)", len(updates))
                    for update in updates:
                        update_id = update.get("update_id", 0)
                        if update_id >= self._offset:
                            self._offset = update_id + 1
                            logger.debug("Processing update_id=%d", update_id)
                            await self._handle_update(update)

                    # Reset backoff on successful polling
                    backoff = 1
                else:
                    # No updates is normal - long polling timeout
                    backoff = 1

            except TelegramError as exc:
                if exc.code in (401, 403, 409):
                    logger.critical("Fatal Telegram API error: %s", exc)
                    self._running = False
                    break
                logger.warning("Telegram API error during polling: %s", exc)
                await self._sleep_with_backoff(backoff)
                backoff = min(backoff * 2, 30)

            except asyncio.CancelledError:
                logger.debug("Polling task cancelled")
                raise

            except Exception as exc:
                logger.exception("Unexpected error in polling loop: %s", exc)
                await self._sleep_with_backoff(backoff)
                backoff = min(backoff * 2, 30)

    async def _sleep_with_backoff(self, backoff: int) -> None:
        """Sleep with backoff, respecting shutdown signal."""
        logger.debug("Polling backing off for %ds", backoff)
        try:
            await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            raise


async def run_polling(
    telegram: TelegramClient,
    handle_update: Callable[[dict[str, Any]], Any],
    allowed_updates: Optional[list[str]] = None,
    timeout: int = 20,
) -> PollingManager:
    """Convenience function to create and start polling.

    Returns the PollingManager for manual stop control.
    """
    manager = PollingManager(
        telegram=telegram,
        handle_update=handle_update,
        allowed_updates=allowed_updates,
        timeout=timeout,
    )
    await manager.start()
    return manager