"""Shared dependencies handed to the handlers through ``context.bot_data``."""

from __future__ import annotations

from dataclasses import dataclass

from telegram.ext import ContextTypes

from app.config.settings import Settings
from app.database.database import Database
from app.database.settings_repository import SettingsRepository

DEPENDENCIES_KEY = "dependencies"


@dataclass(frozen=True)
class BotDependencies:
    settings: Settings
    database: Database
    settings_repo: SettingsRepository


def get_dependencies(context: ContextTypes.DEFAULT_TYPE) -> BotDependencies:
    return context.bot_data[DEPENDENCIES_KEY]
