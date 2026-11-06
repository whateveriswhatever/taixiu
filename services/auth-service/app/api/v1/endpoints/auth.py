from fastapi import APIRouter, HTTPException, status

from app.api.deps import ActiveUserDep, DbDep
from app.schemas.user import (
    ChangePasswordRequest,
    RefreshTokenRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import auth_service

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký tài khoản người chơi mới",
)
async def register(
    db: DbDep,
    data: UserRegister,
) -> UserResponse:
    """Tạo tài khoản người chơi mới với tên đăng nhập, mật khẩu và tên hiển thị."""
    user = await auth_service.register(db=db, data=data)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Đăng nhập tài khoản người chơi",
)
async def login(
    db: DbDep,
    data: UserLogin,
) -> TokenResponse:
    """Xác thực thông tin đăng nhập và cấp Access Token cùng Refresh Token."""
    user = await auth_service.authenticate(
        db=db, username=data.username, password=data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đã bị tạm khóa bởi quản trị viên",
        )

    return auth_service.create_tokens(user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Làm mới Access Token bằng Refresh Token",
)
async def refresh_token(
    db: DbDep,
    data: RefreshTokenRequest,
) -> TokenResponse:
    """Sử dụng Refresh Token còn hiệu lực để cấp cặp Token mới."""
    return await auth_service.refresh_tokens(db=db, refresh_token_str=data.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Lấy thông tin tài khoản người chơi đang đăng nhập",
)
async def get_current_user_profile(
    current_user: ActiveUserDep,
) -> UserResponse:
    """Xem thông tin chi tiết của người chơi hiện tại."""
    return UserResponse.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Cập nhật thông tin tài khoản người chơi",
)
async def update_current_user_profile(
    db: DbDep,
    current_user: ActiveUserDep,
    data: UpdateProfileRequest,
) -> UserResponse:
    """Cập nhật tên hiển thị hoặc avatar của người chơi."""
    updated_user = await auth_service.update_profile(
        db=db, user=current_user, data=data
    )
    return UserResponse.model_validate(updated_user)


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Đổi mật khẩu tài khoản",
)
async def change_password(
    db: DbDep,
    current_user: ActiveUserDep,
    data: ChangePasswordRequest,
) -> dict:
    """Đổi mật khẩu bảo vệ tài khoản."""
    await auth_service.change_password(db=db, user=current_user, data=data)
    return {"message": "Đổi mật khẩu thành công"}


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Đăng xuất",
)
async def logout(
    current_user: ActiveUserDep,
) -> dict:
    """Xử lý đăng xuất phía client (xóa token khỏi local storage / cookie)."""
    return {"message": "Đăng xuất thành công"}

