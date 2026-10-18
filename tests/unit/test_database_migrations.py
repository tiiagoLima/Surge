"""Offline migration and explicit provisioning tests."""

import sqlite3

from alembic import command
from alembic.config import Config

from src.shared.database.migrations import (
    create_memory_database,
    introspect_schema,
    provision_database,
    stamp_legacy_database,
    validate_legacy_database,
)


def _config(path):
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    return config


def test_new_database_has_full_baseline_and_head(tmp_path) -> None:
    path = tmp_path / "new.db"
    provision_database(path)
    schema = introspect_schema(path)
    assert set(schema) >= {
        "execution_records",
        "memory_entries",
        "quotes",
        "opportunities",
        "holdings",
        "finance_transactions",
        "finance_budgets",
        "schema_metadata",
        "alembic_version",
    }
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "0002_schema_metadata"
        )
    provision_database(path)
    assert validate_legacy_database(path)["equivalent"]


def test_incremental_upgrade_preserves_data(tmp_path) -> None:
    path = tmp_path / "incremental.db"
    config = _config(path)
    command.upgrade(config, "0001_baseline")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO holdings VALUES (?, ?, ?, ?, ?)", ("TEST", 1, None, "BRL", "2026")
        )
        connection.commit()
    command.upgrade(config, "head")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT ticker FROM holdings").fetchone()[0] == "TEST"
        assert connection.execute(
            "SELECT value FROM schema_metadata WHERE key='schema_contract'"
        ).fetchone()[0]


def test_memory_provisioning_is_anchored_and_has_alembic_version() -> None:
    uri, anchor = create_memory_database()
    assert uri.startswith("file:surge_migrations_")
    assert anchor.execute("SELECT COUNT(*) FROM execution_records").fetchone()[0] == 0
    assert (
        anchor.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == "0002_schema_metadata"
    )


def test_legacy_validation_and_explicit_stamp(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    provision_database(path)
    report = validate_legacy_database(path)
    assert report["equivalent"]
    backup = tmp_path / "legacy.backup"
    stamp_legacy_database(path, backup_path=backup)
    assert backup.exists()


def test_divergent_legacy_is_not_stamped(tmp_path) -> None:
    path = tmp_path / "bad.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE holdings (ticker TEXT PRIMARY KEY)")
        connection.commit()
    report = validate_legacy_database(path)
    assert not report["equivalent"]
    try:
        stamp_legacy_database(path, backup_path=tmp_path / "bad.backup")
    except ValueError:
        pass
    else:
        raise AssertionError("divergent legacy database must not be stamped")
