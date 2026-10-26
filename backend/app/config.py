"""Application configuration via pydantic-settings (HANDOFF §11).

Model IDs are read from the environment / `.env` and never hardcoded.
The `.env` file is anchored at the repo root so config is identical no
matter which directory the process is launched from.
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
    )

    meta_api_key: str = ""
    meta_api_base_url: str = ""
    sam_model_id: str = ""
    judge_model_id: str = ""
    image_model_id: str = ""
    data_dir: str = "./data"
    mvtec_dir: str = "./data/mvtec"
    cors_origins: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _resolve_data_dirs(self) -> "Settings":
        for field in ("data_dir", "mvtec_dir"):
            value = Path(getattr(self, field))
            if not value.is_absolute():
                object.__setattr__(self, field, str((REPO_ROOT / value).resolve()))
        return self


settings = Settings()
