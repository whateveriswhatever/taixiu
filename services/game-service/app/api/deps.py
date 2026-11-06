from typing import Annotated, AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import decode_token

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


async def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> bool:
    """Yêu cầu quyền Admin cho các tác vụ điều khiển game."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu xác thực tài khoản quản trị",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Yêu cầu quyền Quản trị viên (Admin)",
            )
        return True
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


AdminDep = Annotated[bool, Depends(require_admin)]

