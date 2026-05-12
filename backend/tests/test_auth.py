import pytest
from app.core.security import create_access_token


def test_register_success(client):
    response = client.post("/auth/register", json={"email": "new@example.com", "password": "pass1234"})
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@example.com"
    assert "id" in data


def test_register_duplicate_email(client, test_user):
    response = client.post("/auth/register", json={"email": "test@example.com", "password": "anypass"})
    assert response.status_code == 400
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
    """Covers deps.py line 17: invalid/unparseable token raises 401."""
    response = client.get("/upload/files", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401


def test_get_current_user_nonexistent_user(client):
    """Covers deps.py line 20: valid token but user_id not in DB raises 401."""
    token = create_access_token(data={"sub": "99999"})
    response = client.get("/upload/files", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401