import pytest
import os
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "testsecretkey123456789abcdefghij")
os.environ.setdefault("UPLOAD_DIR", "./uploads")
os.environ.setdefault("FAISS_STORE_DIR", "./faiss_store")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from app.main import app
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.models.models import User
import app.core.redis_client as redis_module

# Mock Redis globally so tests don't need a real Redis server
mock_redis = MagicMock()
mock_redis.get.return_value = None
mock_redis.set.return_value = True
mock_redis.setex.return_value = True
mock_redis.incr.return_value = 1
mock_redis.expire.return_value = True
redis_module.redis_client = mock_redis

TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_get_redis():
        return mock_redis

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