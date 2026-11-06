from decimal import Decimal
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_and_ready(client: AsyncClient):
    res_health = await client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    assert res_health.json()["service"] == "wallet-service"

    res_ready = await client.get("/api/v1/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_get_wallet_auto_creates_with_welcome_bonus(
    client: AsyncClient, player1_token: str
):
    headers = {"Authorization": f"Bearer {player1_token}"}
    response = await client.get("/api/v1/wallet/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 1
    # Welcome bonus is 100,000
    assert Decimal(str(data["balance"])) == Decimal("100000.00")
    assert Decimal(str(data["locked_balance"])) == Decimal("0.00")
    assert Decimal(str(data["total_balance"])) == Decimal("100000.00")
    assert data["currency"] == "VND"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_deposit_and_idempotency(client: AsyncClient, player1_token: str):
    headers = {"Authorization": f"Bearer {player1_token}"}

    # 1. First deposit of 50,000 VND
    payload = {
        "amount": "50000.00",
        "reference_id": "deposit_order_001",
        "description": "Nạp tiền qua MoMo",
    }
    res1 = await client.post("/api/v1/wallet/deposit", headers=headers, json=payload)
    assert res1.status_code == 200
    # 100,000 + 50,000 = 150,000
    assert Decimal(str(res1.json()["balance"])) == Decimal("150000.00")

    # 2. Duplicate deposit request with same reference_id (Idempotency check)
    res2 = await client.post("/api/v1/wallet/deposit", headers=headers, json=payload)
    assert res2.status_code == 200
    # Balance should NOT increase again
    assert Decimal(str(res2.json()["balance"])) == Decimal("150000.00")


@pytest.mark.asyncio
async def test_withdraw_success_and_insufficient_funds(
    client: AsyncClient, player1_token: str
):
    headers = {"Authorization": f"Bearer {player1_token}"}

    # 1. Withdraw 30,000 VND
    res = await client.post(
        "/api/v1/wallet/withdraw",
        headers=headers,
        json={
            "amount": "30000.00",
            "reference_id": "withdraw_order_001",
            "description": "Rút về tài khoản Vietcombank",
        },
    )
    assert res.status_code == 200
    # 150,000 - 30,000 = 120,000
    assert Decimal(str(res.json()["balance"])) == Decimal("120000.00")

    # 2. Try to withdraw more than available balance (999,999,999 VND)
    res_fail = await client.post(
        "/api/v1/wallet/withdraw",
        headers=headers,
        json={"amount": "999999999.00", "description": "Rút quá số dư"},
    )
    assert res_fail.status_code == 400
    assert "không đủ" in res_fail.json()["detail"]


@pytest.mark.asyncio
async def test_hold_bet_and_idempotency(
    client: AsyncClient, internal_headers: dict, player1_token: str
):
    # Hold 20,000 VND for Tài Xỉu round #100
    payload = {
        "user_id": 1,
        "amount": "20000.00",
        "reference_id": "round_100_bet_player_1",
        "description": "Cược 20,000 vào cửa Tài",
    }

    # Call internal hold endpoint
    res = await client.post("/api/v1/wallet/hold", headers=internal_headers, json=payload)
    assert res.status_code == 200
    data = res.json()
    # Balance was 120,000 -> 100,000
    assert Decimal(str(data["balance"])) == Decimal("100000.00")
    # Locked balance was 0 -> 20,000
    assert Decimal(str(data["locked_balance"])) == Decimal("20000.00")
    # Total assets remain 120,000
    assert Decimal(str(data["total_balance"])) == Decimal("120000.00")

    # Duplicate hold request with same reference_id
    res_dup = await client.post("/api/v1/wallet/hold", headers=internal_headers, json=payload)
    assert res_dup.status_code == 200
    assert Decimal(str(res_dup.json()["balance"])) == Decimal("100000.00")
    assert Decimal(str(res_dup.json()["locked_balance"])) == Decimal("20000.00")


@pytest.mark.asyncio
async def test_settle_bet_win(client: AsyncClient, internal_headers: dict):
    # Settle round #100 with result WIN (Payout 40,000: 20k stake + 20k profit)
    payload = {
        "user_id": 1,
        "reference_id": "round_100_bet_player_1",
        "result": "WIN",
        "hold_amount": "20000.00",
        "payout_amount": "40000.00",
        "description": "Thắng cửa Tài phiên #100",
    }
    res = await client.post("/api/v1/wallet/settle", headers=internal_headers, json=payload)
    assert res.status_code == 200
    data = res.json()
    # Locked balance: 20,000 - 20,000 = 0
    assert Decimal(str(data["locked_balance"])) == Decimal("0.00")
    # Available balance: 100,000 + 40,000 = 140,000
    assert Decimal(str(data["balance"])) == Decimal("140000.00")
    assert Decimal(str(data["total_balance"])) == Decimal("140000.00")

    # Idempotency check for settle
    res_dup = await client.post("/api/v1/wallet/settle", headers=internal_headers, json=payload)
    assert res_dup.status_code == 200
    assert Decimal(str(res_dup.json()["balance"])) == Decimal("140000.00")


@pytest.mark.asyncio
async def test_hold_and_settle_lose(client: AsyncClient, internal_headers: dict):
    # 1. Hold 10,000 VND for round #101
    hold_payload = {
        "user_id": 1,
        "amount": "10000.00",
        "reference_id": "round_101_bet_player_1",
        "description": "Cược 10,000 vào cửa Xỉu",
    }
    res_hold = await client.post(
        "/api/v1/wallet/hold", headers=internal_headers, json=hold_payload
    )
    assert res_hold.status_code == 200
    # Balance: 140,000 - 10,000 = 130,000
    assert Decimal(str(res_hold.json()["balance"])) == Decimal("130000.00")
    assert Decimal(str(res_hold.json()["locked_balance"])) == Decimal("10000.00")

    # 2. Settle LOSE
    settle_payload = {
        "user_id": 1,
        "reference_id": "round_101_bet_player_1",
        "result": "LOSE",
        "hold_amount": "10000.00",
        "payout_amount": "0.00",
    }
    res_settle = await client.post(
        "/api/v1/wallet/settle", headers=internal_headers, json=settle_payload
    )
    assert res_settle.status_code == 200
    data = res_settle.json()
    # Locked balance returned to 0, available balance remains 130,000
    assert Decimal(str(data["locked_balance"])) == Decimal("0.00")
    assert Decimal(str(data["balance"])) == Decimal("130000.00")
    assert Decimal(str(data["total_balance"])) == Decimal("130000.00")


@pytest.mark.asyncio
async def test_hold_and_settle_refund(client: AsyncClient, internal_headers: dict):
    # 1. Hold 15,000 VND for round #102
    hold_payload = {
        "user_id": 1,
        "amount": "15000.00",
        "reference_id": "round_102_bet_player_1",
        "description": "Cược 15,000",
    }
    await client.post("/api/v1/wallet/hold", headers=internal_headers, json=hold_payload)

    # 2. Settle REFUND (e.g. system round canceled)
    settle_payload = {
        "user_id": 1,
        "reference_id": "round_102_bet_player_1",
        "result": "REFUND",
        "hold_amount": "15000.00",
    }
    res_settle = await client.post(
        "/api/v1/wallet/settle", headers=internal_headers, json=settle_payload
    )
    assert res_settle.status_code == 200
    data = res_settle.json()
    # Balance: 130,000 - 15,000 + 15,000 = 130,000
    assert Decimal(str(data["locked_balance"])) == Decimal("0.00")
    assert Decimal(str(data["balance"])) == Decimal("130000.00")


@pytest.mark.asyncio
async def test_get_transactions_and_filtering(
    client: AsyncClient, player1_token: str
):
    headers = {"Authorization": f"Bearer {player1_token}"}
    res = await client.get("/api/v1/wallet/transactions", headers=headers)
    assert res.status_code == 200
    txs = res.json()
    assert len(txs) > 0
    # Check transaction structure
    first_tx = txs[0]
    assert "amount" in first_tx
    assert "balance_before" in first_tx
    assert "balance_after" in first_tx
    assert "type" in first_tx

    # Filter by type=DEPOSIT
    res_filtered = await client.get(
        "/api/v1/wallet/transactions?type=DEPOSIT", headers=headers
    )
    assert res_filtered.status_code == 200
    for tx in res_filtered.json():
        assert tx["type"] == "DEPOSIT"


@pytest.mark.asyncio
async def test_internal_endpoint_protection(client: AsyncClient, player1_token: str):
    # Calling internal /hold without internal key should return 403 Forbidden
    headers = {"Authorization": f"Bearer {player1_token}"}
    payload = {
        "user_id": 1,
        "amount": "1000.00",
        "reference_id": "fake_round",
    }
    res = await client.post("/api/v1/wallet/hold", headers=headers, json=payload)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_internal_endpoints(
    client: AsyncClient, admin_token: str
):
    # Admin token can inspect any user's wallet
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = await client.get("/api/v1/wallet/1", headers=headers)
    assert res.status_code == 200
    assert res.json()["user_id"] == 1


@pytest.mark.asyncio
async def test_invalid_deposit_and_withdraw_payloads(
    client: AsyncClient, player1_token: str
):
    headers = {"Authorization": f"Bearer {player1_token}"}

    # Negative amount
    res1 = await client.post(
        "/api/v1/wallet/deposit",
        headers=headers,
        json={"amount": "-1000.00"},
    )
    assert res1.status_code == 422

    # Zero amount
    res2 = await client.post(
        "/api/v1/wallet/withdraw",
        headers=headers,
        json={"amount": "0.00"},
    )
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    # No auth header
    res = await client.get("/api/v1/wallet/me")
    assert res.status_code == 401

    # Fake token
    res_fake = await client.get(
        "/api/v1/wallet/me",
        headers={"Authorization": "Bearer fake.invalid.token"},
    )
    assert res_fake.status_code == 401

