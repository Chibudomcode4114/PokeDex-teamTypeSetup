from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "PokeDex TeamTypeMatchup"

    # Database: defaults to local SQLite, compatible with PostgreSQL
    DATABASE_URL: str = "sqlite:///./pokedex.db"

    # CORS configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # External PokeAPI Base URL
    POKEAPI_BASE_URL: str = "https://pokeapi.co/api/v2"

    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins as a parsed list of stripped strings."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
