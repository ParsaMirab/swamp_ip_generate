"""Async access to the bot settings stored in SQLite."""

from __future__ import annotations

import asyncio
from typing import Optional

from app.database.database import Database

# Key under which the admin configured replacement host/IP is stored.
REPLACEMENT_IP_KEY = "replacement_ip"


class SettingsRepository:
    """Key/value store for the values the admin manages at runtime.

    The SQLite driver is blocking, so every call is handed to a worker thread to
    keep Telegram's event loop responsive.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return await asyncio.to_thread(self._database.get_setting, key, default)

    async def set(self, key: str, value: str) -> None:
        await asyncio.to_thread(self._database.set_setting, key, value)

    async def get_replacement_ip(self) -> Optional[str]:
        return await self.get(REPLACEMENT_IP_KEY)

    async def set_replacement_ip(self, host: str) -> None:
        await self.set(REPLACEMENT_IP_KEY, host)
