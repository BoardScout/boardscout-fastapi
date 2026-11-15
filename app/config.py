"""환경변수에서 애플리케이션 설정을 읽습니다.

설정값을 한곳에 모으면 라우터나 서비스가 운영 환경을 직접 알 필요가
없습니다.
"""

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True, slots=True)
class Settings:
    service_name: str = "boardgame-recommendation"
    environment: str = getenv("APP_ENV", "local")
    core_service_url: str = getenv("CORE_SERVICE_URL", "http://localhost:8080")
    redis_host: str = getenv("REDIS_HOST", "localhost")
    redis_port: int = int(getenv("REDIS_PORT", "6379"))
    redis_database: int = int(getenv("REDIS_DATABASE", "0"))
    session_cookie_name: str = getenv("SESSION_COOKIE_NAME", "BGSESSION")
    session_ttl_seconds: int = int(getenv("SESSION_TTL_SECONDS", "1800"))
    model_path: str = getenv(
        "MODEL_PATH",
        "/app/models/recommendation-v1.joblib",
    )

    @property
    def redis_url(self) -> str:
        """호스트·포트 설정을 redis-py에서 사용하는 URL로 변환합니다."""

        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_database}"


settings = Settings()

