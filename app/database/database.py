"""Thin, thread-safe SQLite wrapper.

The bot only needs to persist a couple of key/value settings, so a single
connection guarded by a lock is enough — no ORM, no migrations, no extra
dependency. Blocking calls are dispatched to a worker thread by
:class:`~app.database.settings_repository.SettingsRepository`.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Database:
    """Owns the SQLite connection used to persist bot settings."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """Create the database file (and directory) plus the schema."""
        with self._lock:
            connection = self._connect_locked()
            connection.executescript(_SCHEMA)
            connection.commit()

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self._connect_locked().execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row is not None else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            connection = self._connect_locked()
            connection.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            connection.commit()

    def _connect_locked(self) -> sqlite3.Connection:
        """Return the shared connection. Must be called while holding the lock."""
        if self._connection is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            self._connection = connection
        return self._connection
