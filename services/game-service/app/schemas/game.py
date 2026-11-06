from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.bet import BetType
from app.models.round import RoundStatus


class BetRequest(BaseModel):
    bet_type: BetType = Field(..., description="Cửa đặt cược: TAI, XIU, TRIPLE_ANY, TRIPLE_SPECIFIC, PAIR, EXACT_POINT")
    amount: Decimal = Field(..., gt=0, description="Số tiền cược (VND)")
    bet_value: Optional[int] = Field(None, description="Giá trị cụ thể: 1..6 (với Bão/Cặp số) hoặc 4..17 (với Điểm chính xác)")

    @model_validator(mode="after")
    def validate_bet_value(self) -> "BetRequest":
        if self.bet_type in [BetType.TRIPLE_SPECIFIC, BetType.PAIR]:
            if self.bet_value is None or not (1 <= self.bet_value <= 6):
                raise ValueError(f"Cửa cược {self.bet_type.value} yêu cầu bet_value từ 1 đến 6")
        elif self.bet_type == BetType.EXACT_POINT:
            if self.bet_value is None or not (4 <= self.bet_value <= 17):
                raise ValueError("Cửa cược EXACT_POINT yêu cầu điểm tổng từ 4 đến 17")
        return self


class BetResponse(BaseModel):
    id: int
    round_id: int
    user_id: int
    bet_type: str
    bet_value: Optional[int] = None
    amount: Decimal
    payout: Decimal
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoundResponse(BaseModel):
    id: int
    status: str
    server_seed_hash: str
    server_seed: Optional[str] = None  # Chỉ tiết lộ khi phiên đã SETTLED
    client_seed: str
    dice1: Optional[int] = None
    dice2: Optional[int] = None
    dice3: Optional[int] = None
    total_points: Optional[int] = None
    result_type: Optional[str] = None
    time_remaining: int
    total_tai_amount: Decimal
    total_xiu_amount: Decimal
    total_bets_count: int
    betting_start_at: datetime
    betting_end_at: datetime
    settled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class VerifyFairnessRequest(BaseModel):
    server_seed: str = Field(..., description="Server Seed được công bố sau khi kết thúc phiên")
    server_seed_hash: str = Field(..., description="Hash cam kết trước phiên cược")
    client_seed: str = Field(..., description="Client Seed")
    round_id: int = Field(..., description="Mã số phiên (Round ID / Nonce)")


class VerifyFairnessResponse(BaseModel):
    is_valid: bool
    computed_hash: str
    expected_hash: str
    dice: List[int]
    total: int
    result_type: str
    is_triple: bool

