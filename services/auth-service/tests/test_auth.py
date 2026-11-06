import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "auth-service"


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    payload = {
        "username": "player_one",
        "password": "password123",
        "display_name": "Tài Thần 99",
        "email": "player1@example.com",
        "phone": "0912345678",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "player_one"
    assert data["display_name"] == "Tài Thần 99"
    assert data["email"] == "player1@example.com"
    assert data["role"] == "player"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    payload = {
        "username": "player_one",
        "password": "anotherpassword",
        "display_name": "Clone Player",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "Tên đăng nhập đã tồn tại" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {
        "username": "player_two",
        "password": "password123",
        "display_name": "Player Two",
        "email": "player1@example.com",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "Email này đã được sử dụng" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    payload = {
        "username": "player_one",
        "password": "password123",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    payload = {
        "username": "player_one",
        "password": "wrongpassword",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "không chính xác" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient):
    # 1. Login to get token
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "player_one", "password": "password123"},
    )
    token = login_res.json()["access_token"]

    # 2. Get profile with Authorization header
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    profile = res.json()
    assert profile["username"] == "player_one"
    assert profile["display_name"] == "Tài Thần 99"


@pytest.mark.asyncio
async def test_get_profile_unauthorized(client: AsyncClient):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    # Login to get refresh token
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "player_one", "password": "password123"},
    )
    refresh_token = login_res.json()["refresh_token"]

    # Request new tokens
    res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "player_one", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_res = await client.put(
        "/api/v1/auth/me",
        headers=headers,
        json={"display_name": "Vua Xỉu 2026", "avatar_url": "https://img.example.com/avatar.png"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["display_name"] == "Vua Xỉu 2026"
    assert update_res.json()["avatar_url"] == "https://img.example.com/avatar.png"


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "player_one", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Change password
    change_res = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": "password123", "new_password": "newsecretpassword"},
    )
    assert change_res.status_code == 200

    # Test login with old password fails
    fail_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "player_one", "password": "password123"},
    )
    assert fail_res.status_code == 401

    # Test login with new password succeeds
    success_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "player_one", "password": "newsecretpassword"},
    )
    assert success_res.status_code == 200


@pytest.mark.asyncio
async def test_register_invalid_inputs(client: AsyncClient):
    # Too short username
    res1 = await client.post(
        "/api/v1/auth/register",
        json={"username": "ab", "password": "password123", "display_name": "Short"},
    )
    assert res1.status_code == 422

    # Invalid characters in username (spaces, symbols)
    res2 = await client.post(
        "/api/v1/auth/register",
        json={"username": "bad user!", "password": "password123", "display_name": "Bad User"},
    )
    assert res2.status_code == 422

    # Password too short (< 6 chars)
    res3 = await client.post(
        "/api/v1/auth/register",
        json={"username": "valid_user", "password": "123", "display_name": "Short Pass"},
    )
    assert res3.status_code == 422


@pytest.mark.asyncio
async def test_invalid_token_rejected(client: AsyncClient):
    headers = {"Authorization": "Bearer invalid.fake.token"}
    res = await client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_endpoint(client: AsyncClient):
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "player_one", "password": "newsecretpassword"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.post("/api/v1/auth/logout", headers=headers)
    assert res.status_code == 200
    assert res.json()["message"] == "Đăng xuất thành công"

