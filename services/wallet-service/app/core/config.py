from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Tài Xỉu Wallet Service"
    API_V1_STR: str = "/api/v1"

    # JWT Authentication (shared secret with Auth Service)
    SECRET_KEY: str = "taixiu_super_secure_jwt_secret_key_change_me_in_prod_2026"
    ALGORITHM: str = "HS256"

    # Internal Service-to-Service Secret
    INTERNAL_API_KEY: str = "internal_service_secret_taixiu_game_engine_key_2026"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./wallet.db"

    # Welcome bonus for new players
    INITIAL_WELCOME_BONUS: float = 100000.0

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

