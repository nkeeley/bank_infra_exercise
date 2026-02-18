"""
Application configuration using Pydantic Settings.

All configuration is loaded from environment variables, with an optional .env file
as a fallback. This pattern keeps secrets out of source code — the .env file is
gitignored, and .env.example provides a safe template for developers.

Pydantic Settings automatically:
  1. Reads from environment variables (highest priority)
  2. Falls back to .env file values
  3. Uses defaults defined here (lowest priority)

Usage:
    from app.config import settings
    print(settings.SECRET_KEY)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the Bank API.

    Required fields (no defaults) MUST be set in .env or environment:
      - SECRET_KEY: Used to sign JWT tokens
      - CARD_ENCRYPTION_KEY: Fernet key for encrypting card data at rest
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    APP_NAME: str = "Bank API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # --- Database ---
    # SQLite for MVP; swap to PostgreSQL connection string for production
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/bank.db"

    # --- Authentication ---
    # REQUIRED: No default — forces the developer to set a real secret
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Card Encryption ---
    # REQUIRED: Fernet key for encrypting card numbers and CVVs at rest
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    CARD_ENCRYPTION_KEY: str

    # --- CORS ---
    # Origins allowed to make cross-origin requests (frontend URLs)
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]


# Singleton: import this instance everywhere instead of creating new Settings()
settings = Settings()
