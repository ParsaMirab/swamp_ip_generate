"""Shared dependencies handed to the handlers through context."""

from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import Settings
from app.database.database import Database
from app.database.settings_repository import SettingsRepository

DEPENDENCIES_KEY = "dependencies"


@dataclass(frozen=True)
class BotDependencies:
    settings: Settings
    database: Database
    settings_repo: SettingsRepository


def get_dependencies(context) -> BotDependencies:
    """Get dependencies from context."""
    return context.dependencies