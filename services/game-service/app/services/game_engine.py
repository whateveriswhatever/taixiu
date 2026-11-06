from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.wallet_client import WalletClient, wallet_client as default_wallet_client
from app.core.config import settings
from app.core.provably_fair import generate_dice, generate_server_seed, hash_server_seed
from app.models.bet import Bet, BetStatus, BetType
from app.models.round import GameRound, RoundStatus
from app.schemas.game import BetRequest, RoundResponse


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class GameEngine:
    async def get_active_round(self, db: AsyncSession) -> Optional[GameRound]:
        """Truy vấn phiên cược đang mở hoặc đang lắc."""
        stmt = (
            select(GameRound)
            .where(GameRound.status.in_([RoundStatus.BETTING.value, RoundStatus.SHAKING.value]))
            .order_by(desc(GameRound.id))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_active_round(self, db: AsyncSession) -> GameRound:
        """Lấy phiên đang hoạt động hoặc khởi tạo phiên cược mới với Provably Fair Seed."""
        active = await self.get_active_round(db)
        if active is not None:
            return active

        # Tạo phiên mới
        server_seed = generate_server_seed()
        server_seed_hash = hash_server_seed(server_seed)
        now = utc_now()
        betting_end_at = now + timedelta(seconds=settings.BETTING_DURATION_SECONDS)

        new_round = GameRound(
            status=RoundStatus.BETTING.value,
            server_seed=server_seed,
            server_seed_hash=server_seed_hash,
            client_seed="taixiu_client_seed_v1",
            betting_start_at=now,
            betting_end_at=betting_end_at,
            total_tai_amount=Decimal("0.00"),
            total_xiu_amount=Decimal("0.00"),
            total_bets_count=0,
        )
        db.add(new_round)
        await db.flush()
        await db.refresh(new_round)
        return new_round

    def serialize_round(self, round_obj: GameRound) -> RoundResponse:
        """Đóng gói dữ liệu RoundResponse với tính bảo mật seed."""
        now = utc_now()
        betting_end = ensure_utc(round_obj.betting_end_at)
        if round_obj.status == RoundStatus.BETTING.value:
            time_remaining = max(0, int((betting_end - now).total_seconds())) if betting_end else 0
        elif round_obj.status == RoundStatus.SHAKING.value:
            time_remaining = max(0, settings.SHAKING_DURATION_SECONDS)
        else:
            time_remaining = 0

        # Chỉ tiết lộ Server Seed khi phiên đã SETTLED
        revealed_seed = round_obj.server_seed if round_obj.status == RoundStatus.SETTLED.value else None

        return RoundResponse(
            id=round_obj.id,
            status=round_obj.status,
            server_seed_hash=round_obj.server_seed_hash,
            server_seed=revealed_seed,
            client_seed=round_obj.client_seed,
            dice1=round_obj.dice1,
            dice2=round_obj.dice2,
            dice3=round_obj.dice3,
            total_points=round_obj.total_points,
            result_type=round_obj.result_type,
            time_remaining=time_remaining,
            total_tai_amount=round_obj.total_tai_amount,
            total_xiu_amount=round_obj.total_xiu_amount,
            total_bets_count=round_obj.total_bets_count,
            betting_start_at=ensure_utc(round_obj.betting_start_at),
            betting_end_at=betting_end,
            settled_at=ensure_utc(round_obj.settled_at),
        )

    async def place_bet(
        self,
        db: AsyncSession,
        user_id: int,
        data: BetRequest,
        client: Optional[WalletClient] = None,
    ) -> Bet:
        """Đặt cược vào phiên hiện tại và tạm giữ số dư ở Wallet Service."""
        w_client = client or default_wallet_client
        active_round = await self.get_or_create_active_round(db)

        # 1. Kiểm tra trạng thái phiên
        if active_round.status != RoundStatus.BETTING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phiên hiện tại đã đóng cược, vui lòng chờ phiên tiếp theo",
            )

        # 2. Kiểm tra hạn mức đặt cược
        amount = Decimal(str(data.amount))
        if amount < Decimal(str(settings.MIN_BET_AMOUNT)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mức cược tối thiểu là {settings.MIN_BET_AMOUNT:,.0f} VND",
            )
        if amount > Decimal(str(settings.MAX_BET_AMOUNT)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mức cược tối đa là {settings.MAX_BET_AMOUNT:,.0f} VND",
            )

        # 3. Tạo record cược tạm thời
        bet = Bet(
            round_id=active_round.id,
            user_id=user_id,
            bet_type=data.bet_type.value,
            bet_value=data.bet_value,
            amount=amount,
            payout=Decimal("0.00"),
            status=BetStatus.PENDING.value,
        )
        db.add(bet)
        await db.flush()
        await db.refresh(bet)

        # 4. Tạm giữ số dư qua Wallet Service
        ref_id = f"round_{active_round.id}_bet_{bet.id}"
        desc = f"Cược {data.bet_type.value} phiên #{active_round.id}"
        await w_client.hold_bet(
            user_id=user_id,
            amount=amount,
            reference_id=ref_id,
            description=desc,
        )

        # 5. Cập nhật thống kê phiên
        if data.bet_type == BetType.TAI:
            active_round.total_tai_amount += amount
        elif data.bet_type == BetType.XIU:
            active_round.total_xiu_amount += amount
        active_round.total_bets_count += 1

        await db.flush()
        await db.refresh(bet)
        return bet

    def calculate_payout(
        self, bet: Bet, dice: Tuple[int, int, int]
    ) -> Tuple[bool, Decimal]:
        """Tính toán kết quả thắng/thua và số tiền trả thưởng (bao gồm cả gốc)."""
        d1, d2, d3 = dice
        total = d1 + d2 + d3
        is_triple = (d1 == d2 == d3)
        amount = bet.amount

        # 1. Cửa TÀI: 11 - 17 và không có Bão
        if bet.bet_type == BetType.TAI.value:
            if 11 <= total <= 17 and not is_triple:
                return True, amount * Decimal("2.00")
            return False, Decimal("0.00")

        # 2. Cửa XỈU: 4 - 10 và không có Bão
        if bet.bet_type == BetType.XIU.value:
            if 4 <= total <= 10 and not is_triple:
                return True, amount * Decimal("2.00")
            return False, Decimal("0.00")

        # 3. Cửa BÃO BẤT KỲ (1 ăn 30)
        if bet.bet_type == BetType.TRIPLE_ANY.value:
            if is_triple:
                return True, amount * Decimal("31.00")
            return False, Decimal("0.00")

        # 4. Cửa BÃO CỤ THỂ (1 ăn 180)
        if bet.bet_type == BetType.TRIPLE_SPECIFIC.value:
            if is_triple and d1 == bet.bet_value:
                return True, amount * Decimal("181.00")
            return False, Decimal("0.00")

        # 5. Cửa CẶP SỐ (1 ăn 10)
        if bet.bet_type == BetType.PAIR.value:
            dice_list = [d1, d2, d3]
            if dice_list.count(bet.bet_value) >= 2:
                return True, amount * Decimal("11.00")
            return False, Decimal("0.00")

        # 6. Cửa ĐIỂM CHÍNH XÁC
        if bet.bet_type == BetType.EXACT_POINT.value:
            if total == bet.bet_value:
                point_multipliers = {
                    4: 61, 17: 61,
                    5: 31, 16: 31,
                    6: 19, 15: 19,
                    7: 13, 14: 13,
                    8: 9,  13: 9,
                    9: 7, 10: 7, 11: 7, 12: 7,
                }
                mult = Decimal(str(point_multipliers.get(total, 2)))
                return True, amount * mult
            return False, Decimal("0.00")

        return False, Decimal("0.00")

    async def advance_round_to_shaking(self, db: AsyncSession, round_id: int) -> GameRound:
        """Đóng cược và tiến hành lắc xí ngầu (sinh kết quả Provably Fair)."""
        stmt = select(GameRound).where(GameRound.id == round_id).with_for_update()
        res = await db.execute(stmt)
        round_obj = res.scalar_one_or_none()
        if not round_obj:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên cược")

        if round_obj.status != RoundStatus.BETTING.value:
            return round_obj

        # Sinh kết quả xúc xắc theo Provably Fair
        d1, d2, d3 = generate_dice(round_obj.server_seed, round_obj.client_seed, round_obj.id)
        total = d1 + d2 + d3
        is_triple = (d1 == d2 == d3)

        if is_triple:
            result_type = "TRIPLE"
        elif total >= 11:
            result_type = "TAI"
        else:
            result_type = "XIU"

        round_obj.dice1 = d1
        round_obj.dice2 = d2
        round_obj.dice3 = d3
        round_obj.total_points = total
        round_obj.result_type = result_type
        round_obj.status = RoundStatus.SHAKING.value

        await db.flush()
        await db.refresh(round_obj)
        return round_obj

    async def advance_round_to_settled(
        self, db: AsyncSession, round_id: int, client: Optional[WalletClient] = None
    ) -> GameRound:
        """Mở bát, tính toán thắng/thua và trả thưởng qua Wallet Service."""
        w_client = client or default_wallet_client
        stmt = (
            select(GameRound)
            .options(selectinload(GameRound.bets))
            .where(GameRound.id == round_id)
            .with_for_update()
        )
        res = await db.execute(stmt)
        round_obj = res.scalar_one_or_none()
        if not round_obj:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên cược")

        if round_obj.status == RoundStatus.SETTLED.value:
            return round_obj

        # Nếu chưa lắc xúc xắc thì lắc trước
        if round_obj.status == RoundStatus.BETTING.value:
            await self.advance_round_to_shaking(db, round_id)
            await db.refresh(round_obj)

        dice = (round_obj.dice1, round_obj.dice2, round_obj.dice3)

        # Duyệt qua các vé cược và quyết toán
        for bet in round_obj.bets:
            is_win, payout = self.calculate_payout(bet, dice)
            ref_id = f"round_{round_obj.id}_bet_{bet.id}"

            if is_win:
                bet.status = BetStatus.WON.value
                bet.payout = payout
                await w_client.settle_bet(
                    user_id=bet.user_id,
                    reference_id=ref_id,
                    result="WIN",
                    hold_amount=bet.amount,
                    payout_amount=payout,
                    description=f"Thắng cược #{ref_id} ({payout:,.0f} VND)",
                )
            else:
                bet.status = BetStatus.LOST.value
                bet.payout = Decimal("0.00")
                await w_client.settle_bet(
                    user_id=bet.user_id,
                    reference_id=ref_id,
                    result="LOSE",
                    hold_amount=bet.amount,
                    payout_amount=Decimal("0.00"),
                    description=f"Thua cược #{ref_id}",
                )

        round_obj.status = RoundStatus.SETTLED.value
        round_obj.settled_at = utc_now()
        await db.flush()
        await db.refresh(round_obj)
        return round_obj

    async def get_history(
        self, db: AsyncSession, limit: int = 50
    ) -> List[GameRound]:
        """Lấy danh sách các phiên đã kết thúc (dùng cho soi cầu)."""
        stmt = (
            select(GameRound)
            .where(GameRound.status == RoundStatus.SETTLED.value)
            .order_by(desc(GameRound.id))
            .limit(limit)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def get_user_bets(
        self, db: AsyncSession, user_id: int, round_id: Optional[int] = None, limit: int = 50
    ) -> List[Bet]:
        """Lấy lịch sử cược của người chơi."""
        stmt = (
            select(Bet)
            .where(Bet.user_id == user_id)
            .order_by(desc(Bet.id))
            .limit(limit)
        )
        if round_id:
            stmt = stmt.where(Bet.round_id == round_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())


game_engine = GameEngine()
