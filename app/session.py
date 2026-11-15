"""Spring Boot와 공유하는 Redis 로그인 세션을 읽습니다."""

import json
import re
from typing import Annotated, Protocol, cast

from fastapi import Cookie, Depends, Request
from pydantic import BaseModel, ConfigDict, ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.errors import ApiError
from app.schemas import UserSessionResponse


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class StoredSession(BaseModel):
    """Redis JSON 계약을 검증하는 내부 모델입니다."""

    model_config = ConfigDict(extra="forbid")

    userId: int
    email: str
    nickname: str
    role: str
    createdAt: str


class SessionStore(Protocol):
    async def ping(self) -> bool: ...

    async def find_and_refresh(self, session_id: str) -> UserSessionResponse | None: ...


class RedisSessionStore:
    """Redis 조회와 슬라이딩 TTL 갱신을 담당합니다."""

    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def find_and_refresh(self, session_id: str) -> UserSessionResponse | None:
        # 1단계: Spring과 같은 규칙으로 쿠키를 검증해 임의 키 조회를 막습니다.
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            return None

        key = f"session:{session_id}"
        # 2단계: GETEX로 세션 조회와 만료 시간 갱신을 원자적으로 처리합니다.
        raw_value = await self.client.getex(key, ex=self.ttl_seconds)
        if raw_value is None:
            return None

        # 3단계: 손상되었거나 계약이 다른 세션은 인증하지 않고 제거합니다.
        try:
            stored = StoredSession.model_validate(json.loads(raw_value))
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, TypeError):
            await self.client.delete(key)
            return None

        # 4단계: 응답에서 생성 시각과 세션 ID 같은 내부 정보는 제외합니다.
        return UserSessionResponse(
            userId=stored.userId,
            email=stored.email,
            nickname=stored.nickname,
            role=stored.role,
        )


def get_session_store(request: Request) -> SessionStore:
    """애플리케이션 시작 때 만든 공유 저장소를 요청에 주입합니다."""

    return cast(SessionStore, request.app.state.session_store)


async def get_current_user(
    store: Annotated[SessionStore, Depends(get_session_store)],
    session_id: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> UserSessionResponse:
    """쿠키로 사용자를 인증하고 Redis 장애와 인증 실패를 구분합니다."""

    if session_id is None:
        raise ApiError(401, "AUTH-401-001", "로그인이 필요합니다.")
    try:
        user = await store.find_and_refresh(session_id)
    except RedisError as error:
        raise ApiError(
            503, "COMMON-503", "세션 저장소에 연결할 수 없습니다."
        ) from error
    if user is None:
        raise ApiError(401, "AUTH-401-001", "유효하지 않거나 만료된 세션입니다.")
    return user
