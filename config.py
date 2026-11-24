"""Load application settings and secrets from the environment or `.env`."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent


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
    german_words_file: Path = Path("words_german.txt")
    english_words_file: Path = Path("words_english.txt")
    german_8_letter_words_file: Path = Path("words_8letters_german.txt")
    german_4_letter_words_file: Path = Path("words_4letters_german.txt")

    def resolve_path(self, path: Path) -> Path:
        """Resolve relative configured file paths from the project directory."""
        return path if path.is_absolute() else PROJECT_ROOT / path


settings = Settings()  # Loaded from .env file
