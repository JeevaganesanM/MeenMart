from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MeenMart API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql://postgres:postgres@localhost:5432/meenmart_dev"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # JWT authentication settings
    jwt_secret_key: str = "meenmart-insecure-dev-secret-key-32chars-min"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Payment Gateway Settings (Razorpay / GPay / UPI)
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
