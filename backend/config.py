"""Central configuration for Mnemos.

All secrets are read from environment variables; never commit a real .env file.
The defaults are suitable for local development and can be overridden at deploy time.
"""

from functools import lru_cache
import os


_TRUE_VALUES = {"1", "true", "yes", "on"}


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


class Settings:
    """Small dependency-free settings object, compatible with Python 3.10+."""

    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "Mnemos")
        self.app_version = os.getenv("APP_VERSION", "0.1.0")
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        # Nebius Token Factory uses an OpenAI-compatible API. Set the key in the
        # environment; NEBIUS_API_KEY is accepted as a convenient fallback name.
        self.nebius_api_key = (
            os.getenv("NEBIUS_TOKEN_FACTORY_KEY")
            or os.getenv("NEBIUS_API_KEY")
            or ""
        )
        self.nebius_base_url = os.getenv(
            "NEBIUS_TOKEN_FACTORY_BASE_URL",
            os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1"),
        ).rstrip("/")
        self.nebius_reasoning_model = os.getenv(
            "NEBIUS_REASONING_MODEL", "nvidia/nemotron-3-super-120b-a12b"
        )
        self.nebius_fast_model = os.getenv(
            "NEBIUS_FAST_MODEL", "nvidia/Nemotron-3-Nano-30B"
        )
        self.nebius_request_timeout = float(os.getenv("NEBIUS_REQUEST_TIMEOUT", "60"))

        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        # Set a long random secret in deployed environments. The fallback is only
        # for local development and must be replaced before public deployment.
        self.auth_secret = os.getenv(
            "MNEMOS_AUTH_SECRET", "local-development-only-change-this-secret"
        )
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./mnemos.db")
        self.frontend_api_url = os.getenv("MNEMOS_API_URL", "http://127.0.0.1:8000").rstrip("/")
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501"
            ).split(",")
            if origin.strip()
        ]
        self.enable_demo_mode = _as_bool(os.getenv("MNEMOS_DEMO_MODE"), False)

    @property
    def has_nebius_key(self) -> bool:
        return bool(self.nebius_api_key.strip())

    @property
    def has_tavily_key(self) -> bool:
        return bool(self.tavily_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings; clear the cache in tests after changing env vars."""
    return Settings()


settings = get_settings()
