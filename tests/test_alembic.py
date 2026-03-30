from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_schema(tmp_path) -> None:
    db_path = tmp_path / 'alembic_test.db'
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'alembic'))
    config.set_main_option('sqlalchemy.url', f"sqlite:///{db_path.resolve().as_posix()}")

    command.upgrade(config, 'head')

    inspector = inspect(create_engine(f"sqlite:///{db_path.resolve().as_posix()}"))
    tables = set(inspector.get_table_names())
    assert {'assets', 'candles', 'strategies', 'signals', 'users', 'watchlists', 'notification_settings', 'notifications'} <= tables
