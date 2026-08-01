"""Configuration module using pydantic-settings for loading and validating environment variables."""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(Exception):
    """Raised when required configuration or environment variables are missing."""

    pass


class Config(BaseSettings):
    """Application configuration managed via pydantic-settings."""

    google_maps_api_key: str = Field(
        ...,
        alias="GOOGLE_MAPS_API_KEY",
        description="Google Maps API Key with Geocoding API and Places API enabled",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def api_key(self) -> str:
        """Convenience accessor for google_maps_api_key."""
        return self.google_maps_api_key

    @classmethod
    def from_env(cls, explicit_key: Optional[str] = None) -> "Config":
        """Load configuration from environment variables, .env file, or explicit argument override.

        Args:
            explicit_key: Optional explicit API key override.

        Returns:
            Config instance with validated API key.

        Raises:
            ConfigurationError: If no valid API key is found.
        """
        if explicit_key:
            return cls(GOOGLE_MAPS_API_KEY=explicit_key)
        try:
            return cls()
        except Exception as err:
            raise ConfigurationError(
                "GOOGLE_MAPS_API_KEY environment variable is not set. "
                "Please export GOOGLE_MAPS_API_KEY='your_key' or set it in a .env file."
            ) from err
