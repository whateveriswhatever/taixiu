from decimal import Decimal
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.transaction import TransactionStatus, TransactionType, WalletTransaction
from app.models.wallet import Wallet
from app.schemas.wallet import (
    DepositRequest,
    HoldBetRequest,
    SettleBetRequest,
    SettleResult,
    WithdrawRequest,
)


class WalletService:
    async def get_or_create_wallet(
        self, db: AsyncSession, user_id: int, for_update: bool = False
    ) -> Wallet:
        """Lấy thông tin ví hoặc tự động khởi tạo nếu là người chơi mới."""
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update()

        result = await db.execute(stmt)
        wallet = result.scalar_one_or_none()

        if wallet is None:
            initial_bonus = Decimal(str(settings.INITIAL_WELCOME_BONUS))
            wallet = Wallet(
                user_id=user_id,
                balance=initial_bonus,
                locked_balance=Decimal("0.00"),
                currency="VND",
                is_active=True,
            )
            db.add(wallet)
            await db.flush()
            await db.refresh(wallet)

            # Ghi nhận giao dịch bonus ban đầu nếu có
            if initial_bonus > Decimal("0.00"):
                bonus_tx = WalletTransaction(
                    wallet_id=wallet.id,
                    user_id=user_id,
                    amount=initial_bonus,
                    balance_before=Decimal("0.00"),
                    balance_after=initial_bonus,
                    locked_before=Decimal("0.00"),
                    locked_after=Decimal("0.00"),
                    type=TransactionType.BONUS.value,
                    status=TransactionStatus.COMPLETED.value,
                    description="Thưởng khởi nghiệp trải nghiệm Tài Xỉu",
                )
                db.add(bonus_tx)
                await db.flush()

        return wallet

    async def get_by_user_id(
        self, db: AsyncSession, user_id: int, for_update: bool = False
    ) -> Optional[Wallet]:
        """Truy vấn ví theo user_id."""
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def deposit(
        self, db: AsyncSession, user_id: int, data: DepositRequest
    ) -> Tuple[Wallet, WalletTransaction]:
        """Nạp tiền vào tài khoản người chơi (Hỗ trợ Idempotency)."""
        # Kiểm tra idempotency nếu có reference_id
        if data.reference_id:
            stmt = select(WalletTransaction).where(
                WalletTransaction.reference_id == data.reference_id,
                WalletTransaction.type == TransactionType.DEPOSIT.value,
            )
            res = await db.execute(stmt)
            existing_tx = res.scalar_one_or_none()
            if existing_tx:
                wallet = await self.get_or_create_wallet(db, user_id)
                return wallet, existing_tx

        wallet = await self.get_or_create_wallet(db, user_id, for_update=True)
        if not wallet.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ví của tài khoản đã bị khóa",
            )

        amount = Decimal(str(data.amount))
        balance_before = wallet.balance
        balance_after = balance_before + amount

        wallet.balance = balance_after

        tx = WalletTransaction(
            wallet_id=wallet.id,
            user_id=user_id,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            locked_before=wallet.locked_balance,
            locked_after=wallet.locked_balance,
            type=TransactionType.DEPOSIT.value,
            status=TransactionStatus.COMPLETED.value,
            reference_id=data.reference_id,
            description=data.description or "Nạp tiền vào ví",
        )
        db.add(tx)
        await db.flush()
        await db.refresh(tx)
        await db.refresh(wallet)
        return wallet, tx

    async def withdraw(
        self, db: AsyncSession, user_id: int, data: WithdrawRequest
    ) -> Tuple[Wallet, WalletTransaction]:
        """Rút tiền từ ví (Kiểm tra số dư khả dụng và khóa hàng chờ tránh race condition)."""
        if data.reference_id:
            stmt = select(WalletTransaction).where(
                WalletTransaction.reference_id == data.reference_id,
                WalletTransaction.type == TransactionType.WITHDRAW.value,
            )
            res = await db.execute(stmt)
            existing_tx = res.scalar_one_or_none()
            if existing_tx:
                wallet = await self.get_or_create_wallet(db, user_id)
                return wallet, existing_tx

        wallet = await self.get_or_create_wallet(db, user_id, for_update=True)
        if not wallet.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ví của tài khoản đã bị khóa",
            )

        amount = Decimal(str(data.amount))
        if wallet.balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Số dư khả dụng ({wallet.balance:,.2f}) không đủ để rút ({amount:,.2f})",
            )

        balance_before = wallet.balance
        balance_after = balance_before - amount

        wallet.balance = balance_after

        tx = WalletTransaction(
            wallet_id=wallet.id,
            user_id=user_id,
            amount=-amount,
            balance_before=balance_before,
            balance_after=balance_after,
            locked_before=wallet.locked_balance,
            locked_after=wallet.locked_balance,
            type=TransactionType.WITHDRAW.value,
            status=TransactionStatus.COMPLETED.value,
            reference_id=data.reference_id,
            description=data.description or "Rút tiền từ ví",
        )
        db.add(tx)
        await db.flush()
        await db.refresh(tx)
        await db.refresh(wallet)
        return wallet, tx

    async def hold_balance(
        self, db: AsyncSession, data: HoldBetRequest
    ) -> Tuple[Wallet, WalletTransaction]:
        """Tạm giữ tiền cược khi người chơi đặt cửa Tài/Xỉu (Service-to-Service)."""
        # Kiểm tra idempotency cho cược
        stmt = select(WalletTransaction).where(
            WalletTransaction.reference_id == data.reference_id,
            WalletTransaction.type == TransactionType.BET_HOLD.value,
        )
        res = await db.execute(stmt)
        existing_tx = res.scalar_one_or_none()
        if existing_tx:
            wallet = await self.get_or_create_wallet(db, data.user_id)
            return wallet, existing_tx

        wallet = await self.get_or_create_wallet(db, data.user_id, for_update=True)
        if not wallet.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ví của tài khoản đã bị khóa",
            )

        amount = Decimal(str(data.amount))
        if wallet.balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Số dư không đủ ({wallet.balance:,.2f}) để đặt cược ({amount:,.2f})",
            )

        balance_before = wallet.balance
        balance_after = balance_before - amount
        locked_before = wallet.locked_balance
        locked_after = locked_before + amount

        wallet.balance = balance_after
        wallet.locked_balance = locked_after

        tx = WalletTransaction(
            wallet_id=wallet.id,
            user_id=data.user_id,
            amount=-amount,
            balance_before=balance_before,
            balance_after=balance_after,
            locked_before=locked_before,
            locked_after=locked_after,
            type=TransactionType.BET_HOLD.value,
            status=TransactionStatus.COMPLETED.value,
            reference_id=data.reference_id,
            description=data.description or "Tạm giữ cược Tài Xỉu",
        )
        db.add(tx)
        await db.flush()
        await db.refresh(tx)
        await db.refresh(wallet)
        return wallet, tx

    async def settle_bet(
        self, db: AsyncSession, data: SettleBetRequest
    ) -> Tuple[Wallet, WalletTransaction]:
        """Quyết toán kết quả cược phiên Tài Xỉu (Thắng/Thua/Hoàn cược)."""
        settle_ref = f"settle_{data.reference_id}"
        stmt = select(WalletTransaction).where(
            WalletTransaction.reference_id == settle_ref
        )
        res = await db.execute(stmt)
        existing_tx = res.scalar_one_or_none()
        if existing_tx:
            wallet = await self.get_or_create_wallet(db, data.user_id)
            return wallet, existing_tx

        wallet = await self.get_or_create_wallet(db, data.user_id, for_update=True)
        hold_amount = Decimal(str(data.hold_amount))

        balance_before = wallet.balance
        locked_before = wallet.locked_balance

        # Trừ phần đã hold
        locked_after = max(Decimal("0.00"), locked_before - hold_amount)
        wallet.locked_balance = locked_after

        if data.result == SettleResult.WIN:
            payout = Decimal(str(data.payout_amount))
            balance_after = balance_before + payout
            wallet.balance = balance_after
            tx_type = TransactionType.BET_WIN.value
            tx_amount = payout
            desc_text = f"Thắng cược Tài Xỉu (Nhận: {payout:,.2f})"

        elif data.result == SettleResult.REFUND:
            balance_after = balance_before + hold_amount
            wallet.balance = balance_after
            tx_type = TransactionType.BET_REFUND.value
            tx_amount = hold_amount
            desc_text = f"Hoàn trả cược Tài Xỉu ({hold_amount:,.2f})"

        else:  # LOSE
            balance_after = balance_before
            tx_type = TransactionType.BET_LOSE.value
            tx_amount = -hold_amount
            desc_text = f"Thua cược Tài Xỉu ({hold_amount:,.2f})"

        tx = WalletTransaction(
            wallet_id=wallet.id,
            user_id=data.user_id,
            amount=tx_amount,
            balance_before=balance_before,
            balance_after=balance_after,
            locked_before=locked_before,
            locked_after=locked_after,
            type=tx_type,
            status=TransactionStatus.COMPLETED.value,
            reference_id=settle_ref,
            description=data.description or desc_text,
        )
        db.add(tx)
        await db.flush()
        await db.refresh(tx)
        await db.refresh(wallet)
        return wallet, tx

    async def get_transactions(
        self,
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        tx_type: Optional[str] = None,
    ) -> List[WalletTransaction]:
        """Lấy lịch sử biến động số dư của người chơi."""
        stmt = (
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user_id)
            .order_by(desc(WalletTransaction.created_at))
            .offset(skip)
            .limit(limit)
        )
        if tx_type:
            stmt = stmt.where(WalletTransaction.type == tx_type.upper())

        result = await db.execute(stmt)
        return list(result.scalars().all())


wallet_service = WalletService()

