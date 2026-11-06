import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Tên đăng nhập (3-50 ký tự)")
    display_name: str = Field(..., min_length=2, max_length=100, description="Tên hiển thị trong game")
    email: Optional[EmailStr] = Field(None, description="Địa chỉ email")
    phone: Optional[str] = Field(None, description="Số điện thoại")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        clean_v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9_]+$", clean_v):
            raise ValueError("Tên đăng nhập chỉ được chứa chữ cái, số và dấu gạch dưới")
        return clean_v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        clean_v = v.strip()
        if len(clean_v) < 2:
            raise ValueError("Tên hiển thị phải có ít nhất 2 ký tự")
        return clean_v


class UserRegister(UserBase):
    password: str = Field(..., min_length=6, max_length=128, description="Mật khẩu (tối thiểu 6 ký tự)")


class UserLogin(BaseModel):
    username: str = Field(..., description="Tên đăng nhập")
    password: str = Field(..., description="Mật khẩu")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

