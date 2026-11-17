from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "railtrace"
    db_user: str = "railtrace"
    db_password: SecretStr = SecretStr("railtrace")
    db_driver: str = "postgresql+psycopg"
    db_echo: bool = False

    db_url: str | None = None

    api_port: int = 8000

    @computed_field
    @property
    def database_url(self) -> str:
        if self.db_url:
            return self.db_url
        return URL.create(
            drivername=self.db_driver,
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
