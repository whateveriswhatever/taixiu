from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminDep, CurrentPlayerIdDep, DbDep
from app.core.provably_fair import verify_round_fairness
from app.schemas.game import (
    BetRequest,
    BetResponse,
    RoundResponse,
    VerifyFairnessRequest,
    VerifyFairnessResponse,
)
from app.services.game_engine import game_engine

router = APIRouter()


@router.get(
    "/current-round",
    response_model=RoundResponse,
    summary="Lấy thông tin phiên cược hiện tại (Live Countdown & Hash Provably Fair)",
)
async def get_current_round(db: DbDep) -> RoundResponse:
    """Trả về phiên đang mở cược hoặc đang lắc với thời gian đếm ngược còn lại."""
    round_obj = await game_engine.get_or_create_active_round(db)
    return game_engine.serialize_round(round_obj)


@router.post(
    "/bet",
    response_model=BetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đặt cược vào phiên hiện tại",
)
async def place_bet(
    db: DbDep,
    player_id: CurrentPlayerIdDep,
    data: BetRequest,
) -> BetResponse:
    """Đặt cược vào cửa Tài / Xỉu / Bão / Cặp số và khóa tiền tương ứng ở Wallet Service."""
    bet = await game_engine.place_bet(db=db, user_id=player_id, data=data)
    return BetResponse.model_validate(bet)


@router.get(
    "/my-bets",
    response_model=List[BetResponse],
    summary="Xem lịch sử đặt cược của người chơi",
)
async def get_my_bets(
    db: DbDep,
    player_id: CurrentPlayerIdDep,
    round_id: Optional[int] = Query(None, description="Lọc theo mã phiên"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng vé cược cần lấy"),
) -> List[BetResponse]:
    """Xem danh sách các vé cược của cá nhân."""
    bets = await game_engine.get_user_bets(db=db, user_id=player_id, round_id=round_id, limit=limit)
    return [BetResponse.model_validate(b) for b in bets]


@router.get(
    "/rounds/history",
    response_model=List[RoundResponse],
    summary="Lấy lịch sử các phiên trước (Phục vụ Soi Cầu Tài Xỉu)",
)
async def get_round_history(
    db: DbDep,
    limit: int = Query(50, ge=1, le=100, description="Số lượng phiên kết quả cần lấy"),
) -> List[RoundResponse]:
    """Lấy danh sách các phiên đã kết thúc kèm theo kết quả 3 xí ngầu và Server Seed đã công bố."""
    rounds = await game_engine.get_history(db=db, limit=limit)
    return [game_engine.serialize_round(r) for r in rounds]


@router.post(
    "/rounds/verify",
    response_model=VerifyFairnessResponse,
    summary="Công cụ kiểm chứng tính minh bạch (Provably Fair Verifier)",
)
async def verify_fairness(
    data: VerifyFairnessRequest,
) -> VerifyFairnessResponse:
    """Người chơi tự kiểm chứng xem kết quả xúc xắc có đúng theo Server Seed và Hash cam kết ban đầu không."""
    result = verify_round_fairness(
        server_seed=data.server_seed,
        server_seed_hash=data.server_seed_hash,
        client_seed=data.client_seed,
        nonce=data.round_id,
    )
    return VerifyFairnessResponse(**result)


# ============================================================================
# CÁC API QUẢN TRỊ / ĐIỀU PHỐI VÒNG LẶP GAME (Admin / Scheduler Worker)
# ============================================================================

@router.post(
    "/admin/advance",
    response_model=RoundResponse,
    summary="[Admin/Worker] Chuyển tiếp trạng thái phiên cược (Đóng cược -> Lắc -> Trả thưởng)",
)
async def advance_round(
    db: DbDep,
    _: AdminDep,
    action: str = Query(..., description="'shake' (Đóng cược và lắc) hoặc 'settle' (Mở bát và trả thưởng)"),
) -> RoundResponse:
    """Dùng cho background timer/worker hoặc admin điều phối nhịp game."""
    active_round = await game_engine.get_or_create_active_round(db)

    if action == "shake":
        updated_round = await game_engine.advance_round_to_shaking(db, active_round.id)
    elif action == "settle":
        updated_round = await game_engine.advance_round_to_settled(db, active_round.id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action không hợp lệ. Chọn 'shake' hoặc 'settle'",
        )

    return game_engine.serialize_round(updated_round)

