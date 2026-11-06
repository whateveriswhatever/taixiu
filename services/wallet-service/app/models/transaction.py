from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.wallet import Wallet


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TransactionType(str, Enum):
    DEPOSIT = "DEPOSIT"            # Nạp tiền
    WITHDRAW = "WITHDRAW"          # Rút tiền
    BET_HOLD = "BET_HOLD"          # Tạm giữ tiền đặt cược
    BET_WIN = "BET_WIN"            # Trả thưởng khi thắng cược
    BET_LOSE = "BET_LOSE"          # Trừ tiền khi thua cược
    BET_REFUND = "BET_REFUND"      # Hoàn trả cược (phiên bị hủy/từ chối)
    BONUS = "BONUS"                # Thưởng chào mừng / khuyến mãi
    ADJUSTMENT = "ADJUSTMENT"      # Điều chỉnh từ Admin


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    locked_before: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    locked_after: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=TransactionStatus.COMPLETED.value, nullable=False)
    reference_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, user_id={self.user_id}, type='{self.type}', amount={self.amount})>"

