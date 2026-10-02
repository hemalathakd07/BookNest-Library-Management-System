from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models
from database import Base, get_db
from main import app

# Private in-memory database. Tests never use the PostgreSQL development database.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


def override_get_db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def register_user(client, name, email, password="student123"):
    response = client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password
        }
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client, email, password="student123"):
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def add_staff_user(db, role, email, name="Library Staff", password="staffpass1"):
    from auth_utils import hash_password

    user = models.User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_client():
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
