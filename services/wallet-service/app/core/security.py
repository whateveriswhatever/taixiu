from typing import Any, Dict
import jwt

from app.core.config import settings


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate user JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token đã hết hạn")
    except jwt.InvalidTokenError:
        raise ValueError("Token không hợp lệ")


def verify_internal_key(key: str) -> bool:
    """Check internal service-to-service API key."""
    return key == settings.INTERNAL_API_KEY

