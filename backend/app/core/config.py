"""Application settings, loaded from environment / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    PROJECT_NAME: str = "DriveTime Vehicle Damage Inspection API"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "dev-secret-change-me-before-any-shared-deployment"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Persistence
    DATABASE_URL: str = "sqlite:///./data/app.db"

    # Storage
    STORAGE_DIR: Path = BACKEND_ROOT / "storage"
    MAX_UPLOAD_MB: int = 15
    THUMBNAIL_MAX_EDGE: int = 480

    # Inference
    PREDICTOR_BACKEND: str = "auto"
    # Device for inference: auto | cpu | cuda | mps.
    # "auto" resolves to CUDA when present, otherwise CPU - deliberately NOT
    # Apple's MPS, because the API serves requests from a thread pool and MPS
    # is not reliably thread-safe across torch versions. Set INFERENCE_DEVICE=mps
    # explicitly if you want it (faster, single-user development machines).
    INFERENCE_DEVICE: str = "auto"
    CLASSIFIER_WEIGHTS: Path = BACKEND_ROOT / "models" / "car_damage_classifier.pth"
    DETECTOR_WEIGHTS: Path = BACKEND_ROOT / "models" / "yolov8_damage.pt"

    # CORS. Kept as a string because pydantic-settings JSON-decodes list-typed
    # fields straight from the environment, which a comma-separated value fails.
    CORS_ORIGINS: str = "http://localhost:4200,http://127.0.0.1:4200"

    # Seed admin
    FIRST_ADMIN_EMAIL: str = "admin@drivetime.lk"
    FIRST_ADMIN_PASSWORD: str = "ChangeMe123!"
    SEED_DEMO_DATA: bool = True

    @field_validator("STORAGE_DIR", "CLASSIFIER_WEIGHTS", "DETECTOR_WEIGHTS", mode="after")
    @classmethod
    def _absolutise(cls, value: Path) -> Path:
        return value if value.is_absolute() else (BACKEND_ROOT / value).resolve()

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def sqlalchemy_url(self) -> str:
        """Resolve a relative SQLite path against the backend root."""
        prefix = "sqlite:///"
        if self.DATABASE_URL.startswith(prefix):
            raw = self.DATABASE_URL[len(prefix) :]
            if raw != ":memory:" and not raw.startswith("/"):
                resolved = (BACKEND_ROOT / raw).resolve()
                resolved.parent.mkdir(parents=True, exist_ok=True)
                return f"{prefix}{resolved}"
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
