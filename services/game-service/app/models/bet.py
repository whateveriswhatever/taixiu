from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.round import GameRound


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BetType(str, Enum):
    TAI = "TAI"                          # Cửa Tài: 11 - 17 (không bão)
    XIU = "XIU"                          # Cửa Xỉu: 4 - 10 (không bão)
    TRIPLE_ANY = "TRIPLE_ANY"            # Bão bất kỳ (1:30)
    TRIPLE_SPECIFIC = "TRIPLE_SPECIFIC"  # Bão cụ thể (1:180), bet_value = 1..6
    PAIR = "PAIR"                        # Cặp số (1:10), bet_value = 1..6
    EXACT_POINT = "EXACT_POINT"          # Điểm chính xác (4..17)


class BetStatus(str, Enum):
    PENDING = "PENDING"
    WON = "WON"
    LOST = "LOST"
    REFUNDED = "REFUNDED"


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("game_rounds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    bet_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    bet_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Giá trị cụ thể nếu có

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payout: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=BetStatus.PENDING.value, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    round: Mapped["GameRound"] = relationship("GameRound", back_populates="bets")

    def __repr__(self) -> str:
        return f"<Bet(id={self.id}, user_id={self.user_id}, round_id={self.round_id}, type='{self.bet_type}', amount={self.amount})>"

