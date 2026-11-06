from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SettleResult(str, Enum):
    WIN = "WIN"        # Thắng cược
    LOSE = "LOSE"      # Thua cược
    REFUND = "REFUND"  # Hoàn trả cược


class WalletResponse(BaseModel):
    id: int
    user_id: int
    balance: Decimal
    locked_balance: Decimal
    total_balance: Decimal
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepositRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Số tiền nạp (phải lớn hơn 0)")
    reference_id: Optional[str] = Field(None, description="Mã giao dịch nạp đối chiếu")
    description: Optional[str] = Field("Nạp tiền vào ví", description="Mô tả giao dịch")


class WithdrawRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Số tiền rút (phải lớn hơn 0)")
    reference_id: Optional[str] = Field(None, description="Mã giao dịch rút đối chiếu")
    description: Optional[str] = Field("Rút tiền từ ví", description="Mô tả giao dịch")


class HoldBetRequest(BaseModel):
    user_id: int = Field(..., description="ID người chơi đặt cược")
    amount: Decimal = Field(..., gt=0, description="Số tiền cược cần tạm giữ")
    reference_id: str = Field(..., description="Khóa định danh cược (ví dụ: round_100_bet_12)")
    description: Optional[str] = Field("Tạm giữ tiền cược Tài Xỉu", description="Mô tả")


class SettleBetRequest(BaseModel):
    user_id: int = Field(..., description="ID người chơi")
    reference_id: str = Field(..., description="Khóa định danh giao dịch cược gốc")
    result: SettleResult = Field(..., description="Kết quả phiên cược: WIN, LOSE, REFUND")
    hold_amount: Decimal = Field(..., gt=0, description="Số tiền đã tạm giữ trước đó")
    payout_amount: Decimal = Field(
        default=Decimal("0.00"), ge=0, description="Tổng số tiền nhận về khi thắng (gốc + lãi)"
    )
    description: Optional[str] = Field("Quyết toán kết quả cược Tài Xỉu", description="Mô tả")


class TransactionResponse(BaseModel):
    id: int
    wallet_id: int
    user_id: int
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    locked_before: Decimal
    locked_after: Decimal
    type: str
    status: str
    reference_id: Optional[str] = None
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

