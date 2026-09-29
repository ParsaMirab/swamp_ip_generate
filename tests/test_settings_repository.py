import asyncio

from app.database.database import Database
from app.database.settings_repository import SettingsRepository


def test_replacement_ip_survives_a_restart(tmp_path):
    database_path = tmp_path / "swamp.sqlite3"

    async def scenario() -> None:
        database = Database(database_path)
        database.initialize()
        repository = SettingsRepository(database)
        assert await repository.get_replacement_ip() is None

        await repository.set_replacement_ip("144.31.157.131")
        database.close()

        # A fresh connection simulates a bot restart.
        reopened = Database(database_path)
        reopened.initialize()
        reopened_repository = SettingsRepository(reopened)
        assert await reopened_repository.get_replacement_ip() == "144.31.157.131"

        await reopened_repository.set_replacement_ip("10.0.0.9")
        assert await reopened_repository.get_replacement_ip() == "10.0.0.9"
        reopened.close()

    asyncio.run(scenario())


def test_database_file_and_directory_are_created(tmp_path):
    database_path = tmp_path / "nested" / "swamp.sqlite3"

    async def scenario() -> None:
        database = Database(database_path)
        database.initialize()
        repository = SettingsRepository(database)
        await repository.set_replacement_ip("1.2.3.4")
        database.close()

        assert database_path.exists()

    asyncio.run(scenario())
