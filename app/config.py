"""환경변수에서 애플리케이션 설정을 읽습니다."""

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True, slots=True)
class Settings:
    service_name: str = "boardgame-recommendation"
    environment: str = getenv("APP_ENV", "local")
    core_service_url: str = getenv("CORE_SERVICE_URL", "http://localhost:8080")
    redis_host: str = getenv("REDIS_HOST", "localhost")
    redis_port: int = int(getenv("REDIS_PORT", "6379"))
    model_path: str = getenv(
        "MODEL_PATH",
        "/app/models/recommendation-v1.joblib",
    )


settings = Settings()

