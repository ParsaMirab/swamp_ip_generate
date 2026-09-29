"""Entry point of the Swamp IP Generator bot.

Run it with::

    python main.py
"""

from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from app.bot.aiohttp_request import AiohttpRequest
from app.bot.dependencies import DEPENDENCIES_KEY, BotDependencies
from app.bot.handlers.admin import build_admin_conversation
from app.bot.handlers.user import register_user_handlers
from app.config.settings import ConfigurationError, Settings, load_settings
from app.database.database import Database
from app.database.settings_repository import SettingsRepository


logger = logging.getLogger(__name__)


BOT_COMMANDS = (
    BotCommand("start", "شروع"),
    BotCommand("help", "راهنما"),
    BotCommand("admin", "پنل مدیریت (فقط ادمین)"),
)


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(list(BOT_COMMANDS))


async def _post_shutdown(application: Application) -> None:
    dependencies: BotDependencies | None = application.bot_data.get(
        DEPENDENCIES_KEY
    )

    if dependencies is not None:
        dependencies.database.close()


async def _on_error(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    logger.error(
        "Unhandled exception while processing an update",
        exc_info=context.error,
    )


def build_application(settings: Settings) -> Application:
    """Wire up the database, dependencies and every handler."""

    database = Database(settings.database_path)
    database.initialize()

    # Use aiohttp for all Telegram API requests.
    request = AiohttpRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=60.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    get_updates_request = AiohttpRequest(
        connection_pool_size=4,
        connect_timeout=30.0,
        read_timeout=60.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    application = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .request(request)
        .get_updates_request(get_updates_request)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    application.bot_data[DEPENDENCIES_KEY] = BotDependencies(
        settings=settings,
        database=database,
        settings_repo=SettingsRepository(database),
    )

    application.add_error_handler(_on_error)

    # Registration order matters:
    # the admin conversation must be checked first.
    application.add_handler(build_admin_conversation())
    register_user_handlers(application)

    return application


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # HTTPX is no longer used by our Telegram request layer.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        settings = load_settings()
    except ConfigurationError as exc:
        logger.critical("%s", exc)
        raise SystemExit(1) from exc

    application = build_application(settings)

    logger.info(
        "Swamp IP Generator is up. Admin IDs: %s",
        sorted(settings.admin_ids),
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        bootstrap_retries=-1,
    )


if __name__ == "__main__":
    main()