from typing import List, Optional
from fastapi import APIRouter, Query, status

from app.api.deps import CurrentPlayerIdDep, DbDep, InternalServiceDep
from app.schemas.wallet import (
    DepositRequest,
    HoldBetRequest,
    SettleBetRequest,
    TransactionResponse,
    WalletResponse,
    WithdrawRequest,
)
from app.services.wallet_service import wallet_service

router = APIRouter()


@router.get(
    "/me",
    response_model=WalletResponse,
    summary="Xem số dư ví của người chơi đang đăng nhập",
)
async def get_my_wallet(
    db: DbDep,
    player_id: CurrentPlayerIdDep,
) -> WalletResponse:
    """Lấy số dư ví (khả dụng, đang cược, tổng tài sản) của người chơi hiện tại."""
    wallet = await wallet_service.get_or_create_wallet(db, user_id=player_id)
    return WalletResponse.model_validate(wallet)


@router.get(
    "/transactions",
    response_model=List[TransactionResponse],
    summary="Xem lịch sử giao dịch & biến động số dư của người chơi",
)
async def get_my_transactions(
    db: DbDep,
    player_id: CurrentPlayerIdDep,
    skip: int = Query(0, ge=0, description="Vị trí bắt đầu"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng giao dịch cần lấy"),
    type: Optional[str] = Query(None, description="Lọc theo loại giao dịch (DEPOSIT, WITHDRAW, BET_HOLD, ...)"),
) -> List[TransactionResponse]:
    """Truy vấn sổ cái giao dịch cá nhân."""
    txs = await wallet_service.get_transactions(
        db=db, user_id=player_id, skip=skip, limit=limit, tx_type=type
    )
    return [TransactionResponse.model_validate(tx) for tx in txs]


@router.post(
    "/deposit",
    response_model=WalletResponse,
    status_code=status.HTTP_200_OK,
    summary="Nạp tiền vào ví người chơi",
)
async def deposit(
    db: DbDep,
    player_id: CurrentPlayerIdDep,
    data: DepositRequest,
) -> WalletResponse:
    """Người chơi hoặc Cổng thanh toán nạp tiền vào ví."""
    wallet, _ = await wallet_service.deposit(db=db, user_id=player_id, data=data)
    return WalletResponse.model_validate(wallet)


@router.post(
    "/withdraw",
    response_model=WalletResponse,
    status_code=status.HTTP_200_OK,
    summary="Rút tiền từ ví người chơi",
)
async def withdraw(
    db: DbDep,
    player_id: CurrentPlayerIdDep,
    data: WithdrawRequest,
) -> WalletResponse:
    """Rút tiền từ số dư khả dụng về ngân hàng / ví điện tử."""
    wallet, _ = await wallet_service.withdraw(db=db, user_id=player_id, data=data)
    return WalletResponse.model_validate(wallet)


# ============================================================================
# CÁC API NỘI BỘ (Service-to-Service: Game Service <-> Wallet Service)
# ============================================================================

@router.post(
    "/hold",
    response_model=WalletResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Tạm giữ số dư khi đặt cược",
)
async def hold_bet(
    db: DbDep,
    _: InternalServiceDep,
    data: HoldBetRequest,
) -> WalletResponse:
    """Game Service gọi để tạm giữ tiền cược khi người chơi đặt cửa Tài/Xỉu."""
    wallet, _ = await wallet_service.hold_balance(db=db, data=data)
    return WalletResponse.model_validate(wallet)


@router.post(
    "/settle",
    response_model=WalletResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Quyết toán kết quả ván cược",
)
async def settle_bet(
    db: DbDep,
    _: InternalServiceDep,
    data: SettleBetRequest,
) -> WalletResponse:
    """Game Service gọi để quyết toán thắng/thua/hoàn tiền khi kết thúc phiên."""
    wallet, _ = await wallet_service.settle_bet(db=db, data=data)
    return WalletResponse.model_validate(wallet)


@router.get(
    "/{user_id}",
    response_model=WalletResponse,
    summary="[Internal / Admin] Xem thông tin ví theo user_id",
)
async def get_wallet_by_user_id(
    db: DbDep,
    _: InternalServiceDep,
    user_id: int,
) -> WalletResponse:
    """Tra cứu ví người chơi theo ID."""
    wallet = await wallet_service.get_or_create_wallet(db, user_id=user_id)
    return WalletResponse.model_validate(wallet)

