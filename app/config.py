from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""
    
    # App Info
    app_name: str = "FESCO Bill Tracker"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database
    database_url: str = "sqlite:///./fesco_tracker.db"
    
    # JWT (future use)
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Cache
    cache_ttl_minutes: int = 10
    
    # FESCO Scraper
    fesco_timeout: int = 15
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()