from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    env: str = "dev"
    log_level: str = "INFO"
    model_extraction: str = "claude-haiku-4-5"
    model_synthesis: str = "claude-sonnet-4-6"
    run_budget_usd: float = 0.20
    output_dir: Path = Path("./outputs")

    @field_validator("output_dir", mode="after")
    @classmethod
    def _create_output_dir(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v


settings = Settings()
