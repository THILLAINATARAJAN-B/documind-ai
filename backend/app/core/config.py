from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache
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
    environment: str = "development"
    upload_dir: str = "./uploads"
    faiss_store_dir: str = "./faiss_store"
    max_file_size_mb: int = 50


@lru_cache()
def get_settings() -> Settings:
    return Settings()