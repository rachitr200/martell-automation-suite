import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.db import get_session
from app.deps import get_integrations
from app.integrations import Integrations
from app.main import app
from app.models import Base
from tests.helpers import SECRET


class RecordingCRM:
    def __init__(self):
        self.calls: list[dict] = []

    def upsert_contact(self, **kwargs):
        self.calls.append(kwargs)


class RecordingAccess:
    def __init__(self):
        self.granted: list[tuple] = []
        self.revoked: list[str] = []
        self.fail = False

    def grant(self, *, email, plan):
        if self.fail:
            raise RuntimeError("access provider down")
        self.granted.append((email, plan))

    def revoke(self, *, email):
        if self.fail:
            raise RuntimeError("access provider down")
        self.revoked.append(email)


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine)


@pytest.fixture
def integrations():
    return Integrations(crm=RecordingCRM(), access=RecordingAccess())


@pytest.fixture
def settings():
    return Settings(
        database_url="sqlite://", stripe_webhook_secret=SECRET, max_attempts=3, admin_token=""
    )


@pytest.fixture
def client(session_factory, integrations, settings):
    def _session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_integrations] = lambda: integrations
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()
