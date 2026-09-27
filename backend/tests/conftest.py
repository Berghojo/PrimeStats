import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from primestats.config import Settings, normalize_database_url
from primestats.demo import DemoSource, demo_team_entries
from primestats.services import PrimeStats
from primestats.store import Store, make_engine

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
TEST_DATABASE_URL = normalize_database_url(
    os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/primestats_test"))
TABLES = "team_games, team_members, teams, timeline_summaries, timelines, matches, accounts"


@pytest.fixture(scope="session")
def demo_source():
    return DemoSource(seed=7, now=NOW)


@pytest.fixture(scope="session")
def engine():
    from sqlalchemy.engine import make_url
    if "test" not in (make_url(TEST_DATABASE_URL).database or ""):
        pytest.exit("TEST_DATABASE_URL muss auf eine Test-Datenbank zeigen (Name enthält 'test') – "
                    "die Tests leeren das Schema.", returncode=2)
    engine = make_engine(TEST_DATABASE_URL)
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        message = f"Keine Test-Datenbank erreichbar ({TEST_DATABASE_URL}): {exc.orig}"
        if os.getenv("CI"):
            pytest.fail(message)  # in CI niemals stillschweigend überspringen
        pytest.skip(message)
    from primestats.migrate import upgrade
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    upgrade(engine)  # testet nebenbei die Alembic-Migrationen
    yield engine
    engine.dispose()


@pytest.fixture
def store(engine):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    return Store(engine)


@pytest.fixture
def service(store, demo_source):
    return PrimeStats(store, demo_source)


@pytest.fixture
def imported(service, demo_source):
    """Demo-Scrims so importieren, als hätte sie der LCU-Uploader hochgeladen."""
    from primestats.demo import import_demo_scrims
    import_demo_scrims(service, demo_source)
    return service


@pytest.fixture
def demo_team(service):
    name, tag, entries = demo_team_entries()
    members, errors = service.resolve_members(entries)
    assert not errors
    team_id = service.store.create_team(name, tag, 4, members)
    return service.store.get_team(team_id)


@pytest.fixture
def synced_team(imported, service, demo_team):
    job = service.jobs.start(demo_team, background=False)
    assert job.status == "done", job.error
    return demo_team


@pytest.fixture
def client(store, demo_source, tmp_path):
    yield from _client(store, demo_source, tmp_path)


UPLOAD_TOKEN = "test-token"


def _client(store, source, tmp_path, **overrides):
    from fastapi.testclient import TestClient

    from primestats.app import create_app
    from primestats.demo import import_demo_scrims
    options = dict(demo=True, ddragon_fetch=False, cache_dir=tmp_path, auto_migrate=False,
                   database_url=TEST_DATABASE_URL, upload_token=UPLOAD_TOKEN)
    options.update(overrides)
    app = create_app(Settings(**options), source=source, store=store)
    with TestClient(app) as client:
        if isinstance(source, DemoSource):
            import_demo_scrims(client.app.state.service, source)
        yield client


@pytest.fixture
def offline_client(store, tmp_path):
    from primestats.services import OfflineSource
    yield from _client(store, OfflineSource(), tmp_path, demo=False)
