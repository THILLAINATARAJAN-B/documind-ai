import pytest
import os
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "testsecretkey123456789abcdefghij")
os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")
os.environ.setdefault("FAISS_STORE_DIR", "/tmp/faiss_store")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

from app.main import app
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.models.models import User
import app.core.redis_client as redis_module


class FakeRedis:
    """
    In-memory Redis stub that correctly handles setex/get/delete/incr/expire.
    Using a plain MagicMock with get.return_value=None breaks the refresh-token
    test because login stores a key via setex but get always returns None.
    """
    def __init__(self):
        self._store: dict = {}

    def setex(self, key, ttl, value):
        self._store[key] = value
        return True

    def set(self, key, value, ex=None):
        self._store[key] = value
        return True

    def get(self, key):
        return self._store.get(key)

    def delete(self, key):
        self._store.pop(key, None)
        return 1

    def incr(self, key):
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = str(val)
        return val

    def expire(self, key, ttl):
        return True

    def ping(self):
        return True

    def reset(self):
        self._store.clear()


# Module-level fake so tests don't need a real Redis server
fake_redis = FakeRedis()
redis_module.redis_client = fake_redis

TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def reset_fake_redis():
    """Clear fake Redis store between every test so state doesn't bleed."""
    fake_redis.reset()
    yield
    fake_redis.reset()


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_get_redis():
        return fake_redis

    from app.core.redis_client import get_redis
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    user = User(
        email="test@example.com",
        hashed_password=hash_password("testpass123")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(client, test_user):
    response = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "testpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
