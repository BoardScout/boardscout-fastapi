"""FastAPI 추천 서비스 진입점입니다."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import Field
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.errors import ApiError, install_exception_handlers
from app.recommender import recommender
from app.schemas import (
    ApiResponse,
    ContextPreferenceRequest,
    HealthResponse,
    RecommendationResult,
    TastePreferenceRequest,
    UserSessionResponse,
)
from app.session import RedisSessionStore, SessionStore, get_current_user, get_session_store


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """프로세스 전체에서 Redis 연결 풀을 만들고 종료 때 닫습니다."""

    # 1단계: decode_responses를 켜 Redis의 bytes를 직접 변환하지 않게 합니다.
    redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    app.state.session_store = RedisSessionStore(redis, settings.session_ttl_seconds)
    try:
        yield
    finally:
        # 2단계: 서버 재시작과 컨테이너 종료 때 연결 풀을 정리합니다.
        await redis.aclose()


def create_app() -> FastAPI:
    """테스트와 운영에서 동일한 설정으로 앱을 생성합니다."""

    application = FastAPI(
        title="Boardgame Recommendation API",
        version="1.0.0",
        description=(
            "사용자 취향과 학습 모델을 이용해 보드게임을 추천합니다."
        ),
        lifespan=lifespan,
    )
    install_exception_handlers(application)
    return application


app = create_app()


@app.get(
    "/api/recommend/health",
    response_model=ApiResponse[HealthResponse],
    tags=["health"],
    summary="서비스 생존 상태 확인",
)
async def health() -> ApiResponse[HealthResponse]:
    """컨테이너와 gateway가 프로세스의 생존 여부를 확인합니다."""

    return ApiResponse[HealthResponse].ok(
        HealthResponse(
            service=settings.service_name,
            status="UP",
            timestamp=datetime.now(UTC),
        )
    )


@app.get(
    "/api/recommend/ready",
    response_model=ApiResponse[HealthResponse],
    tags=["health"],
    summary="서비스 준비 상태 확인",
)
async def ready(
    store: Annotated[SessionStore, Depends(get_session_store)],
) -> ApiResponse[HealthResponse]:
    """요청 처리에 필요한 Redis까지 사용할 수 있는지 확인합니다."""

    try:
        is_ready = await store.ping()
    except RedisError as error:
        raise ApiError(
            503, "COMMON-503", "세션 저장소에 연결할 수 없습니다."
        ) from error
    if not is_ready:
        raise ApiError(503, "COMMON-503", "추천 서비스가 아직 준비되지 않았습니다.")
    return ApiResponse[HealthResponse].ok(
        HealthResponse(
            service=settings.service_name,
            status="READY",
            timestamp=datetime.now(UTC),
        )
    )


@app.get(
    "/api/recommend/me",
    response_model=ApiResponse[UserSessionResponse],
    tags=["session"],
    summary="공유 Redis 세션 확인",
)
async def me(
    user: Annotated[UserSessionResponse, Depends(get_current_user)],
) -> ApiResponse[UserSessionResponse]:
    """Spring이 만든 BGSESSION 쿠키로 FastAPI에서도 같은 사용자를 식별합니다."""

    return ApiResponse[UserSessionResponse].ok(user)


PreferenceRequest = Annotated[
    ContextPreferenceRequest | TastePreferenceRequest,
    Field(discriminator="recommendation_mode"),
]


@app.post(
    "/api/recommend/games",
    response_model=ApiResponse[RecommendationResult],
    tags=["recommendation"],
    summary="보드게임 추천",
)
async def recommend_games(
    preference: PreferenceRequest,
    limit: int = Query(12, ge=1, le=50, description="반환할 추천 게임 수"),
) -> ApiResponse[RecommendationResult]:
    """현재 상황 또는 좋아한 게임을 바탕으로 BGG 카탈로그를 추천합니다."""

    try:
        # 추천 계산은 CPU 작업이므로 이벤트 루프 밖의 작업 스레드에서 실행합니다.
        items = await run_in_threadpool(recommender.recommend, preference, limit)
    except ValueError as error:
        raise ApiError(422, "RECOMMEND-422-001", str(error)) from error

    strategy = (
        "content-item-hybrid"
        if isinstance(preference, TastePreferenceRequest)
        else "content-based"
    )
    return ApiResponse[RecommendationResult].ok(
        RecommendationResult(items=items, strategy=strategy)
    )
