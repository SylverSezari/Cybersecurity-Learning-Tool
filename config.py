from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Load deployment configuration and secrets from environment or `.env`.

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    database_url: str

    secret_key: SecretStr
    algorithm: str = "HS256"
    
    admin: str
    admin_password: SecretStr
    
settings = Settings()  # Loaded from .env file