"""FastAPI 추천 서비스 진입점입니다."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import Field

from app.config import settings
from app.recommender import recommender
from app.schemas import (
    ContextPreferenceRequest,
    HealthResponse,
    RecommendationResult,
    TastePreferenceRequest,
)


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


PreferenceRequest = Annotated[
    ContextPreferenceRequest | TastePreferenceRequest,
    Field(discriminator="recommendation_mode"),
]


@app.post(
    "/api/recommend/games",
    response_model=RecommendationResult,
    tags=["recommendation"],
)
async def recommend_games(
    preference: PreferenceRequest,
    limit: int = Query(12, ge=1, le=50),
) -> RecommendationResult:
    """현재 상황 또는 좋아한 게임을 바탕으로 BGG 카탈로그를 추천합니다."""

    try:
        items = recommender.recommend(preference, limit)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    strategy = "content-item-hybrid" if isinstance(preference, TastePreferenceRequest) else "content-based"
    return RecommendationResult(items=items, strategy=strategy)

