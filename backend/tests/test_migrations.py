from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from primestats.db import Base


def test_migrations_match_models(engine):
    """Die Alembic-Migrationen erzeugen exakt das Schema der SQLAlchemy-Modelle."""
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
