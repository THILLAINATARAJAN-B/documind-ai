from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache
from typing import List
import os


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=(
            os.path.join(os.path.dirname(__file__), "../../.env"),
            os.path.join(os.path.dirname(__file__), "../../../.env"),
        ),
        extra="ignore"
    )

    openai_api_key: str
    database_url: str
    redis_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Refresh token config
    refresh_token_expire_days: int = 7
    # Rate limiting (requests per minute per user)
    rate_limit_per_minute: int = 20
    environment: str = "development"
    upload_dir: str = "./uploads"
    faiss_store_dir: str = "./faiss_store"
    max_file_size_mb: int = 50
    # CORS — comma-separated list of allowed origins
    # Example: "http://localhost:4200,http://frontend:4200"
    allowed_origins: str = "http://localhost:4200,http://localhost:80"

    def get_allowed_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
