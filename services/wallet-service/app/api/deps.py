from typing import Annotated, AsyncGenerator
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.core.security import decode_token, verify_internal_key

security_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_player_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> int:
    """Xác thực token người chơi và trích xuất user_id."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu xác thực tài khoản (Token không được cung cấp)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không chứa định danh người chơi hợp lệ",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return int(user_id_str)


CurrentPlayerIdDep = Annotated[int, Depends(get_current_player_id)]


async def verify_internal_or_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    x_internal_service_key: Annotated[str | None, Header(alias="X-Internal-Service-Key")] = None,
) -> bool:
    """Xác thực giao tiếp nội bộ giữa các microservices (hoặc Admin)."""
    # 1. Kiểm tra header Service Key
    if x_internal_service_key and verify_internal_key(x_internal_service_key):
        return True

    # 2. Hoặc kiểm tra JWT admin role
    if credentials and credentials.credentials:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("role") in ["admin", "service"]:
                return True
        except Exception:
            pass

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Từ chối truy cập: Chỉ cho phép gọi nội bộ (Service-to-Service) hoặc Quản trị viên",
    )


InternalServiceDep = Annotated[bool, Depends(verify_internal_or_admin)]

