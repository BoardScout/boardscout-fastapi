"""Spring core 서비스에서 현재 사용자의 영속 데이터를 읽습니다."""

from __future__ import annotations

from typing import Protocol

import httpx
from pydantic import ValidationError

from app.schemas import UserGameRating
from app.session import SESSION_ID_PATTERN


class RatingStore(Protocol):
    async def get_ratings(self, session_id: str) -> list[UserGameRating]: ...


class SpringRatingStore:
    """브라우저의 로그인 쿠키를 Spring에 전달해 내 별점을 조회합니다."""

    def __init__(self, client: httpx.AsyncClient, cookie_name: str) -> None:
        self.client = client
        self.cookie_name = cookie_name

    async def get_ratings(self, session_id: str) -> list[UserGameRating]:
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            return []
        response = await self.client.get(
            "/api/v1/users/me/ratings",
            headers={"Cookie": f"{self.cookie_name}={session_id}"},
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result", [])
        try:
            return [UserGameRating.model_validate(item) for item in result]
        except (AttributeError, TypeError, ValidationError) as error:
            raise ValueError("잘못된 사용자 별점 응답입니다.") from error
