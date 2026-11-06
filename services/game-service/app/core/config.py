from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Tài Xỉu Game Engine Service"
    API_V1_STR: str = "/api/v1"

    # JWT Authentication
    SECRET_KEY: str = "taixiu_super_secure_jwt_secret_key_change_me_in_prod_2026"
    ALGORITHM: str = "HS256"

    # Wallet Service Integration
    WALLET_SERVICE_URL: str = "http://localhost:8002/api/v1/wallet"
    INTERNAL_API_KEY: str = "internal_service_secret_taixiu_game_engine_key_2026"

    # Game round durations in seconds
    BETTING_DURATION_SECONDS: int = 35
    SHAKING_DURATION_SECONDS: int = 10
    SETTLING_DURATION_SECONDS: int = 5

    # Bet limits
    MIN_BET_AMOUNT: float = 1000.0
    MAX_BET_AMOUNT: float = 50000000.0

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./game.db"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

