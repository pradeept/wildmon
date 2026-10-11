from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "wildmon"
    jwt_secret: str = "local-development-only-change-me"
    web_origin: str = "http://localhost:3000"
    storage_mode: str = "local"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "us-east-1"
    gemma_base_url: str = ""
    gemma_api_key: str = ""
    gemma_model: str = ""
    gemma_timeout_seconds: float = 120
    backboard_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
