from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.bet import Bet


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RoundStatus(str, Enum):
    BETTING = "BETTING"      # Đang mở cược
    SHAKING = "SHAKING"      # Đóng cược, đang lắc đĩa
    SETTLED = "SETTLED"      # Đã mở bát và trả thưởng
    CANCELLED = "CANCELLED"  # Phiên bị hủy


class GameRound(Base):
    __tablename__ = "game_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), default=RoundStatus.BETTING.value, nullable=False, index=True)

    # Provably Fair Seeds
    server_seed: Mapped[str] = mapped_column(String(64), nullable=False)
    server_seed_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_seed: Mapped[str] = mapped_column(String(64), default="taixiu_public_client_seed", nullable=False)

    # Kết quả xí ngầu
    dice1: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dice2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dice3: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # TAI, XIU, TRIPLE

    # Thống kê cược
    total_tai_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    total_xiu_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    total_bets_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Mốc thời gian phiên
    betting_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    betting_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    bets: Mapped[List["Bet"]] = relationship("Bet", back_populates="round", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<GameRound(id={self.id}, status='{self.status}', total={self.total_points}, result='{self.result_type}')>"

