from datetime import datetime, timezone

import pytest

from primestats import create_app
from primestats.config import Settings
from primestats.demo import DemoSource, demo_team_entries
from primestats.services import PrimeStats
from primestats.store import Store

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="session")
def demo_source():
    return DemoSource(seed=7, now=NOW)


@pytest.fixture
def store():
    return Store(":memory:")


@pytest.fixture
def service(store, demo_source):
    return PrimeStats(store, demo_source)


@pytest.fixture
def demo_team(service):
    name, tag, entries = demo_team_entries()
    members, errors = service.resolve_members(entries)
    assert not errors
    team_id = service.store.create_team(name, tag, 4, members)
    return service.store.get_team(team_id)


@pytest.fixture
def synced_team(service, demo_team):
    job = service.jobs.start(demo_team, background=False)
    assert job.status == "done", job.error
    return demo_team


@pytest.fixture
def app(tmp_path, store, demo_source):
    settings = Settings(demo=True, ddragon_fetch=False, data_dir=tmp_path, secret_key="test")
    app = create_app(settings, source=demo_source, store=store)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()
