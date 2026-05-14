import pytest
from app.core.security import create_access_token


def test_register_success(client):
    response = client.post("/auth/register", json={"email": "new@example.com", "password": "pass1234"})
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@example.com"
    assert "id" in data


def test_register_duplicate_email(client, test_user):
    # Router returns 409 Conflict for duplicate email (correct HTTP semantics)
    response = client.post("/auth/register", json={"email": "test@example.com", "password": "anypass"})
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


def test_login_success(client, test_user):
    response = client.post("/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client, test_user):
    response = client.post("/auth/login", json={"email": "test@example.com", "password": "wrongpass"})
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    response = client.post("/auth/login", json={"email": "ghost@example.com", "password": "pass"})
    assert response.status_code == 401


def test_protected_route_without_token(client):
    response = client.get("/upload/files")
    assert response.status_code == 401


def test_protected_route_with_token(client, auth_headers):
    response = client.get("/upload/files", headers=auth_headers)
    assert response.status_code == 200


def test_get_current_user_invalid_token(client):
    """Covers deps.py: invalid/unparseable token raises 401."""
    response = client.get("/upload/files", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401


def test_get_current_user_nonexistent_user(client):
    """Covers deps.py: valid token with user_id not in DB raises 401."""
    # create_access_token adds 'type': 'access' automatically
    token = create_access_token(data={"sub": "99999"})
    response = client.get("/upload/files", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_login_returns_refresh_token(client, test_user):
    """Login response must include refresh_token."""
    response = client.post("/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    assert response.status_code == 200
    data = response.json()
    assert "refresh_token" in data
    assert data["refresh_token"] is not None


def test_refresh_token_endpoint(client, test_user):
    """POST /auth/refresh returns new access + refresh tokens."""
    login = client.post("/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    data = login.json()
    user_id = data["id"]
    refresh_token = data["refresh_token"]

    response = client.post("/auth/refresh", json={"user_id": user_id, "refresh_token": refresh_token})
    assert response.status_code == 200
    new_data = response.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    # Token rotation: new refresh token must differ from old
    assert new_data["refresh_token"] != refresh_token


def test_refresh_token_invalid(client, test_user):
    """Invalid refresh token returns 401."""
    login = client.post("/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    user_id = login.json()["id"]
    response = client.post("/auth/refresh", json={"user_id": user_id, "refresh_token": "notvalidtoken"})
    assert response.status_code == 401


def test_logout_endpoint(client, test_user):
    """POST /auth/logout invalidates session (returns 200)."""
    login = client.post("/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    data = login.json()
    response = client.post("/auth/logout", json={"user_id": data["id"], "refresh_token": data["refresh_token"]})
    assert response.status_code == 200
