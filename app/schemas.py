"""추천 API에서 사용하는 응답 모델입니다."""

from datetime import datetime
from enum import StrEnum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


ResponseData = TypeVar("ResponseData")


class ApiModel(BaseModel):
    """Python은 snake_case, JSON은 camelCase를 사용하는 공통 모델입니다."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ApiResponse(ApiModel, Generic[ResponseData]):
    """Spring API와 동일한 성공/실패 응답 계약입니다."""

    success: bool
    code: str
    message: str
    result: ResponseData | None = None

    @classmethod
    def ok(
        cls,
        result: ResponseData,
        message: str = "요청에 성공했습니다.",
    ) -> "ApiResponse[ResponseData]":
        return cls(success=True, code="COMMON-200", message=message, result=result)


class Theme(StrEnum):
    STRATEGY = "strategy"
    PARTY = "party"
    ADVENTURE = "adventure"
    MYSTERY = "mystery"
    SCIFI = "scifi"
    FAMILY = "family"
    HISTORY = "history"
    BUILDING = "building"


class PlayStyle(StrEnum):
    COOP = "coop"
    SOCIAL = "social"
    ENGINE = "engine"
    LUCK = "luck"
    PUZZLE = "puzzle"
    SOLO = "solo"


class ContextPreferenceRequest(ApiModel):
    """현재 플레이 조건과 BGG 메타데이터를 연결하는 요청입니다."""

    recommendation_mode: Literal["context"] = Field("context", alias="recommendationMode")
    player_count: int = Field(alias="playerCount", ge=1, le=100)
    max_play_time: int = Field(alias="maxPlayTime", ge=10, le=360)
    difficulty: int = Field(ge=1, le=3)
    themes: list[Theme] = Field(default_factory=list, max_length=8)
    play_styles: list[PlayStyle] = Field(default_factory=list, alias="playStyles", max_length=6)


class TastePreferenceRequest(ApiModel):
    """좋아한 BGG 게임으로 취향 프로필을 만드는 요청입니다."""

    recommendation_mode: Literal["taste"] = Field("taste", alias="recommendationMode")
    liked_game_ids: list[int] = Field(alias="likedGameIds", min_length=3, max_length=20)

    @field_validator("liked_game_ids")
    @classmethod
    def validate_liked_game_ids(cls, value: list[int]) -> list[int]:
        """중복 선택으로 '3개 이상' 조건을 우회하지 못하게 합니다."""

        if any(item_id < 0 for item_id in value):
            raise ValueError("게임 ID는 0 이상이어야 합니다")
        if len(set(value)) != len(value):
            raise ValueError("likedGameIds에는 중복된 게임 ID를 넣을 수 없습니다")
        return value


class RecommendationItem(ApiModel):
    game_id: int = Field(alias="gameId")
    bgg_id: int = Field(alias="bggId")
    title: str
    localized_title: str | None = Field(None, alias="localizedTitle")
    category: str
    min_players: int = Field(alias="minPlayers")
    max_players: int = Field(alias="maxPlayers")
    max_play_time: int = Field(alias="maxPlayTime")
    complexity: float = Field(ge=1, le=5)
    average_rating: float = Field(alias="averageRating", ge=1, le=10)
    themes: list[Theme]
    play_styles: list[PlayStyle] = Field(alias="playStyles")
    score: int = Field(ge=0, le=100)
    reason: str


class RecommendationResult(ApiModel):
    items: list[RecommendationItem]
    strategy: str = "content-based"


class HealthResponse(ApiModel):
    service: str
    status: str
    timestamp: datetime


class UserSessionResponse(ApiModel):
    """Spring이 Redis에 저장한 세션에서 복원한 최소 사용자 정보입니다."""

    user_id: int = Field(alias="userId")
    email: str
    nickname: str
    role: str


class ErrorDetail(ApiModel):
    """클라이언트가 표시할 수 있는 요청 필드별 오류입니다."""

    errors: dict[str, str] = Field(default_factory=dict)

