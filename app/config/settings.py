"""Environment based configuration for the bot.

Every secret is read from the environment (usually a local ``.env`` file) so that
nothing sensitive is ever hardcoded in the source tree.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# <project root>/app/config/settings.py -> <project root>
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "swamp.sqlite3"


class ConfigurationError(RuntimeError):
    """Raised when the environment is missing or contains invalid values."""


def _parse_admin_ids(raw: str) -> frozenset[int]:
    """Parse ``ADMIN_IDS`` such as ``"123456789, 987654321"``."""
    admin_ids: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            admin_ids.add(int(value))
        except ValueError as exc:
            raise ConfigurationError(
                f"ADMIN_IDS contains a non-numeric entry: {value!r}"
            ) from exc
    return frozenset(admin_ids)


def _resolve_database_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of the bot configuration."""

    bot_token: str
    admin_ids: frozenset[int]
    database_path: Path

    def is_admin(self, user_id: int | None) -> bool:
        """Return ``True`` only for Telegram IDs listed in ``ADMIN_IDS``."""
        return user_id is not None and user_id in self.admin_ids


def load_settings(env_file: Path | None = None) -> Settings:
    """Load and validate the configuration from the environment."""
    load_dotenv(env_file if env_file is not None else PROJECT_ROOT / ".env")

    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token or bot_token.endswith("REPLACE_WITH_YOUR_BOT_TOKEN"):
        raise ConfigurationError(
            "BOT_TOKEN is not configured. Copy .env.example to .env and set BOT_TOKEN."
        )

    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    if not admin_ids:
        raise ConfigurationError(
            "ADMIN_IDS is empty. Set at least one Telegram user ID, e.g. ADMIN_IDS=123456789."
        )

    database_path = _resolve_database_path(
        (os.getenv("DATABASE_PATH") or str(DEFAULT_DATABASE_PATH)).strip()
    )

    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        database_path=database_path,
    )
