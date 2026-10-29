import pytest


@pytest.fixture
def legacy_schema():
    """Schema bis Version 3 (Serie hat eine einzelne Spalte load_id) für Migrationstests."""

    def build() -> str:
        from loadlog.db import _SCHEMA, _SERIES_LOADS

        return _SCHEMA.replace(_SERIES_LOADS, "").replace(
            "id INTEGER PRIMARY KEY,\n  number INTEGER NOT NULL, name TEXT",
            "id INTEGER PRIMARY KEY, load_id INTEGER REFERENCES loads(id) ON DELETE SET NULL,\n  number INTEGER NOT NULL, name TEXT",
        )

    return build


@pytest.fixture
def db():
    from loadlog.db import Database

    return Database(":memory:")
