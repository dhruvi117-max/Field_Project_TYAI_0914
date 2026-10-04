from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime settings read from environment variables or backend/.env."""

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "retail_shelf_intelligence"
    model_weights_path: str = str(PROJECT_DIR / "models" / "shelf_yolo.pt")
    upload_dir: str = str(PROJECT_DIR / "data" / "uploads")
    audit_artifact_dir: str = str(PROJECT_DIR / "data" / "audit_artifacts")
    max_upload_mb: int = Field(default=10, ge=1, le=50)
    max_image_dimension: int = Field(default=8000, ge=512, le=16000)
    min_detection_confidence: float = Field(default=0.35, ge=0.05, le=0.95)
    restock_cooldown_minutes: int = Field(default=60, ge=1, le=1440)
    max_audits_per_minute: int = Field(default=12, ge=1, le=120)
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    api_key: str = ""
    mlflow_tracking_uri: str = ""

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
