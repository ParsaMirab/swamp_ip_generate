"""Entry point of the Swamp IP Generator bot.

Run it with::

    python main.py
"""

from __future__ import annotations

import asyncio
import logging
import signal

from app.bot.handlers.admin import register_admin_handlers
from app.bot.handlers.user import register_user_handlers
from app.bot.polling import run_polling
from app.bot.router import BotRouter
from app.bot.telegram_client import TelegramClient
from app.bot.dependencies import BotDependencies
from app.config.settings import ConfigurationError, Settings, load_settings
from app.database.database import Database
from app.database.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    {"command": "start", "description": "شروع"},
    {"command": "help", "description": "راهنما"},
    {"command": "admin", "description": "پنل مدیریت (فقط ادمین)"},
]


async def setup_bot_commands(telegram: TelegramClient) -> None:
    """Set bot commands in Telegram."""
    await telegram.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands set")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    try:
        settings = load_settings()
    except ConfigurationError as exc:
        logger.critical("%s", exc)
        raise SystemExit(1) from exc

    # Initialize database
    database = Database(settings.database_path)
    database.initialize()

    # Create Telegram client
    telegram = TelegramClient(token=settings.bot_token)

    # Verify bot token
    try:
        me = await telegram.get_me()
        logger.info("Bot verified: @%s (id=%s)", me.get("username"), me.get("id"))
    except Exception as exc:
        logger.critical("Failed to verify bot token: %s", exc)
        raise SystemExit(1) from exc

    # Set bot commands
    await setup_bot_commands(telegram)

    # Create dependencies
    dependencies = BotDependencies(
        settings=settings,
        database=database,
        settings_repo=SettingsRepository(database),
    )

    # Create router and register handlers
    router = BotRouter(telegram=telegram, dependencies=dependencies)
    register_admin_handlers(router)
    register_user_handlers(router)

    logger.info(
        "Swamp IP Generator is up. Admin IDs: %s",
        sorted(settings.admin_ids),
    )

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals
            pass

    # Start polling
    polling_manager = await run_polling(
        telegram=telegram,
        handle_update=router.handle,
        allowed_updates=["message", "callback_query"],
        timeout=20,
    )

    logger.info("Polling started, waiting for updates...")

    # Wait for shutdown signal
    await shutdown_event.wait()

    logger.info("Shutting down...")
    await polling_manager.stop()
    await telegram.close()
    database.close()
    logger.info("Bot stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())