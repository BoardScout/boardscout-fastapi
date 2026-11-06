"""추천 API에서 사용하는 응답 모델입니다."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Python에서는 snake_case, JSON에서는 camelCase를 사용하는 공통 모델입니다."""

    model_config = ConfigDict(populate_by_name=True)


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

