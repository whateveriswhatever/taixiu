from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import (
    ChangePasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserRegister,
)


class AuthService:
    async def get_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username.lower().strip())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def register(self, db: AsyncSession, data: UserRegister) -> User:
        # Check existing username
        existing_username = await self.get_by_username(db, data.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên đăng nhập đã tồn tại trong hệ thống",
            )

        # Check existing email if provided
        if data.email:
            stmt = select(User).where(User.email == data.email.lower().strip())
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email này đã được sử dụng",
                )

        # Check existing phone if provided
        if data.phone:
            stmt = select(User).where(User.phone == data.phone.strip())
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Số điện thoại này đã được sử dụng",
                )

        # Hash password and create user
        hashed = hash_password(data.password)
        user = User(
            username=data.username,
            email=data.email.lower().strip() if data.email else None,
            phone=data.phone.strip() if data.phone else None,
            hashed_password=hashed,
            display_name=data.display_name,
            role="player",
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    async def authenticate(
        self, db: AsyncSession, username: str, password: str
    ) -> Optional[User]:
        user = await self.get_by_username(db, username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def create_tokens(self, user: User) -> TokenResponse:
        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )
        refresh_token = create_refresh_token(user_id=user.id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_tokens(self, db: AsyncSession, refresh_token_str: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token không phải là refresh token",
            )

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Dữ liệu token không hợp lệ",
            )

        user = await self.get_by_id(db, int(user_id_str))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy thông tin tài khoản người chơi",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản người chơi đã bị khóa",
            )

        return self.create_tokens(user)

    async def change_password(
        self, db: AsyncSession, user: User, data: ChangePasswordRequest
    ) -> None:
        if not verify_password(data.old_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mật khẩu hiện tại không chính xác",
            )

        user.hashed_password = hash_password(data.new_password)
        await db.flush()

    async def update_profile(
        self, db: AsyncSession, user: User, data: UpdateProfileRequest
    ) -> User:
        if data.display_name is not None:
            user.display_name = data.display_name
        if data.avatar_url is not None:
            user.avatar_url = data.avatar_url
        await db.flush()
        await db.refresh(user)
        return user


auth_service = AuthService()

