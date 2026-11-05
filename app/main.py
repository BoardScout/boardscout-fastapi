"""FastAPI 추천 서비스 진입점입니다."""

from datetime import UTC, datetime

from fastapi import FastAPI

from app.config import settings
from app.schemas import HealthResponse


app = FastAPI(
    title="Boardgame Recommendation API",
    version="0.1.0",
    description="사용자 취향과 학습 모델을 이용해 보드게임을 추천합니다.",
)


@app.get(
    "/api/recommend/health",
    response_model=HealthResponse,
    tags=["health"],
)
async def health() -> HealthResponse:
    """컨테이너와 gateway가 서비스의 생존 여부를 확인합니다."""

    return HealthResponse(
        service=settings.service_name,
        status="UP",
        timestamp=datetime.now(UTC),
    )

