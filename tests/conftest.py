import pytest

from database import Base
from main import app
from tests.support import TestingSessionLocal, engine, make_client


@pytest.fixture
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(setup_database):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(setup_database):
    test_client = make_client()
    with test_client:
        yield test_client
    app.dependency_overrides.clear()
