from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[5]


class Settings(BaseSettings):
    app_name: str = "JBL WCAG Audit API"
    app_env: str = "local"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://jbl:jbl@localhost:5432/jbl_audit"
    evidence_root_dir: Path = ROOT_DIR / "var" / "evidence"
    reports_root_dir: Path = ROOT_DIR / "var" / "reports"
    browser_worker_dir: Path = ROOT_DIR / "workers" / "browser"
    browser_worker_entrypoint: Path = ROOT_DIR / "workers" / "browser" / "dist" / "src" / "cli" / "run-tier1-batch.js"
    node_executable: str = "node"
    browser_worker_timeout_seconds: int = 120

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
