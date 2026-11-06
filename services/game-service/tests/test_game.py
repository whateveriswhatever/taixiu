from decimal import Decimal
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_and_ready(client: AsyncClient):
    res_health = await client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    assert res_health.json()["service"] == "game-service"

    res_ready = await client.get("/api/v1/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_get_current_round_creates_active_round(client: AsyncClient):
    res = await client.get("/api/v1/game/current-round")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "BETTING"
    assert "id" in data
    assert len(data["server_seed_hash"]) == 64
    # Server seed must remain hidden while betting is active!
    assert data["server_seed"] is None
    assert data["time_remaining"] > 0
    assert Decimal(str(data["total_tai_amount"])) == Decimal("0.00")
    assert Decimal(str(data["total_xiu_amount"])) == Decimal("0.00")


@pytest.mark.asyncio
async def test_place_bet_success(
    client: AsyncClient, player1_token: str, mock_wallet
):
    headers = {"Authorization": f"Bearer {player1_token}"}
    payload = {
        "bet_type": "TAI",
        "amount": "20000.00",
    }
    res = await client.post("/api/v1/game/bet", headers=headers, json=payload)
    assert res.status_code == 201
    bet = res.json()
    assert bet["bet_type"] == "TAI"
    assert Decimal(str(bet["amount"])) == Decimal("20000.00")
    assert bet["status"] == "PENDING"
    assert bet["user_id"] == 1

    # Verify Wallet Service hold was called
    mock_wallet["hold"].assert_called_once()

    # Verify round stats updated
    res_round = await client.get("/api/v1/game/current-round")
    round_data = res_round.json()
    assert Decimal(str(round_data["total_tai_amount"])) == Decimal("20000.00")
    assert round_data["total_bets_count"] == 1


@pytest.mark.asyncio
async def test_place_bet_validation(
    client: AsyncClient, player1_token: str
):
    headers = {"Authorization": f"Bearer {player1_token}"}

    # 1. Bet amount below minimum (< 1,000)
    res_low = await client.post(
        "/api/v1/game/bet",
        headers=headers,
        json={"bet_type": "TAI", "amount": "500.00"},
    )
    assert res_low.status_code == 400
    assert "tối thiểu" in res_low.json()["detail"]

    # 2. Bet TRIPLE_SPECIFIC without bet_value
    res_no_val = await client.post(
        "/api/v1/game/bet",
        headers=headers,
        json={"bet_type": "TRIPLE_SPECIFIC", "amount": "10000.00"},
    )
    assert res_no_val.status_code == 422

    # 3. Bet PAIR with invalid bet_value (7, must be 1..6)
    res_invalid_pair = await client.post(
        "/api/v1/game/bet",
        headers=headers,
        json={"bet_type": "PAIR", "amount": "10000.00", "bet_value": 7},
    )
    assert res_invalid_pair.status_code == 422


@pytest.mark.asyncio
async def test_advance_round_and_settlement(
    client: AsyncClient, admin_token: str, player1_token: str, mock_wallet
):
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    player_headers = {"Authorization": f"Bearer {player1_token}"}

    # 1. Place bet on XIU
    await client.post(
        "/api/v1/game/bet",
        headers=player_headers,
        json={"bet_type": "XIU", "amount": "15000.00"},
    )

    # 2. Admin advances to 'shake' (Dice rolled)
    res_shake = await client.post(
        "/api/v1/game/admin/advance?action=shake", headers=admin_headers
    )
    assert res_shake.status_code == 200
    shake_data = res_shake.json()
    assert shake_data["status"] == "SHAKING"
    assert 1 <= shake_data["dice1"] <= 6
    assert 1 <= shake_data["dice2"] <= 6
    assert 1 <= shake_data["dice3"] <= 6
    assert 3 <= shake_data["total_points"] <= 18
    assert shake_data["result_type"] in ["TAI", "XIU", "TRIPLE"]

    # 3. Betting should now be blocked
    res_blocked = await client.post(
        "/api/v1/game/bet",
        headers=player_headers,
        json={"bet_type": "TAI", "amount": "10000.00"},
    )
    assert res_blocked.status_code == 400
    assert "đóng cược" in res_blocked.json()["detail"]

    # 4. Admin advances to 'settle'
    res_settle = await client.post(
        "/api/v1/game/admin/advance?action=settle", headers=admin_headers
    )
    assert res_settle.status_code == 200
    settle_data = res_settle.json()
    assert settle_data["status"] == "SETTLED"
    # Server seed must now be revealed!
    assert settle_data["server_seed"] is not None
    assert len(settle_data["server_seed"]) == 64

    # Settle bet must have been called on wallet client
    assert mock_wallet["settle"].called


@pytest.mark.asyncio
async def test_provably_fair_verification_endpoint(
    client: AsyncClient, admin_token: str
):
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Get the last settled round from history
    res_hist = await client.get("/api/v1/game/rounds/history")
    assert res_hist.status_code == 200
    rounds = res_hist.json()
    assert len(rounds) > 0
    target_round = rounds[0]

    # Verify round with the endpoint
    verify_payload = {
        "server_seed": target_round["server_seed"],
        "server_seed_hash": target_round["server_seed_hash"],
        "client_seed": target_round["client_seed"],
        "round_id": target_round["id"],
    }
    res_verify = await client.post("/api/v1/game/rounds/verify", json=verify_payload)
    assert res_verify.status_code == 200
    ver_data = res_verify.json()
    assert ver_data["is_valid"] is True
    assert ver_data["dice"] == [target_round["dice1"], target_round["dice2"], target_round["dice3"]]
    assert ver_data["total"] == target_round["total_points"]
    assert ver_data["result_type"] == target_round["result_type"]


@pytest.mark.asyncio
async def test_get_my_bets(client: AsyncClient, player1_token: str):
    headers = {"Authorization": f"Bearer {player1_token}"}
    res = await client.get("/api/v1/game/my-bets", headers=headers)
    assert res.status_code == 200
    bets = res.json()
    assert len(bets) > 0
    first_bet = bets[0]
    assert "amount" in first_bet
    assert "bet_type" in first_bet
    assert "status" in first_bet


@pytest.mark.asyncio
async def test_admin_advance_protection(client: AsyncClient, player1_token: str):
    # Ordinary player should get 403 Forbidden when trying to advance round
    headers = {"Authorization": f"Bearer {player1_token}"}
    res = await client.post("/api/v1/game/admin/advance?action=shake", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_betting_unauthorized(client: AsyncClient):
    # Missing auth header
    res = await client.post(
        "/api/v1/game/bet",
        json={"bet_type": "TAI", "amount": "20000.00"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_wallet_insufficient_funds_rejection(
    client: AsyncClient, player1_token: str, monkeypatch
):
    from fastapi import HTTPException
    from app.clients import wallet_client
    from unittest.mock import AsyncMock

    # Simulate Wallet Service returning 400 (insufficient balance)
    mock_hold_fail = AsyncMock(
        side_effect=HTTPException(status_code=400, detail="Số dư không đủ để đặt cược")
    )
    monkeypatch.setattr(wallet_client, "hold_bet", mock_hold_fail)

    headers = {"Authorization": f"Bearer {player1_token}"}
    res = await client.post(
        "/api/v1/game/bet",
        headers=headers,
        json={"bet_type": "TAI", "amount": "20000.00"},
    )
    assert res.status_code == 400
    assert "Số dư không đủ" in res.json()["detail"]


def test_payout_rules_calculation():
    from app.models.bet import Bet
    from app.services.game_engine import game_engine

    # Case 1: TAI win (total 14: 3-5-6)
    bet_tai = Bet(amount=Decimal("10000.00"), bet_type="TAI")
    is_win, payout = game_engine.calculate_payout(bet_tai, (3, 5, 6))
    assert is_win is True
    assert payout == Decimal("20000.00")

    # Case 2: TAI loses when Triple happens (4-4-4, total 12)
    is_win, payout = game_engine.calculate_payout(bet_tai, (4, 4, 4))
    assert is_win is False
    assert payout == Decimal("0.00")

    # Case 3: XIU win (total 8: 1-3-4)
    bet_xiu = Bet(amount=Decimal("10000.00"), bet_type="XIU")
    is_win, payout = game_engine.calculate_payout(bet_xiu, (1, 3, 4))
    assert is_win is True
    assert payout == Decimal("20000.00")

    # Case 4: XIU loses on Triple 2-2-2 (total 6)
    is_win, payout = game_engine.calculate_payout(bet_xiu, (2, 2, 2))
    assert is_win is False
    assert payout == Decimal("0.00")

    # Case 5: TRIPLE_ANY win on 5-5-5 (1 ăn 30)
    bet_triple_any = Bet(amount=Decimal("10000.00"), bet_type="TRIPLE_ANY")
    is_win, payout = game_engine.calculate_payout(bet_triple_any, (5, 5, 5))
    assert is_win is True
    assert payout == Decimal("310000.00")

    # Case 6: TRIPLE_SPECIFIC 6-6-6 win (1 ăn 180)
    bet_triple_spec = Bet(amount=Decimal("10000.00"), bet_type="TRIPLE_SPECIFIC", bet_value=6)
    is_win, payout = game_engine.calculate_payout(bet_triple_spec, (6, 6, 6))
    assert is_win is True
    assert payout == Decimal("1810000.00")

    # Case 7: PAIR win (two 4s in 4-4-1, 1 ăn 10)
    bet_pair = Bet(amount=Decimal("10000.00"), bet_type="PAIR", bet_value=4)
    is_win, payout = game_engine.calculate_payout(bet_pair, (4, 4, 1))
    assert is_win is True
    assert payout == Decimal("110000.00")

    # Case 8: EXACT_POINT 10 win
    bet_point = Bet(amount=Decimal("10000.00"), bet_type="EXACT_POINT", bet_value=10)
    is_win, payout = game_engine.calculate_payout(bet_point, (2, 3, 5))
    assert is_win is True
    assert payout == Decimal("70000.00")

