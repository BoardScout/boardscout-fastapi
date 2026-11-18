"""BoardGameGeek 메타데이터와 평점을 결합한 추천 모델입니다."""

from __future__ import annotations

import ast
import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.schemas import (
    ContextPreferenceRequest,
    PlayStyle,
    RecommendationItem,
    Theme,
    TastePreferenceRequest,
    UserGameRating,
)


THEME_KEYWORDS: dict[Theme, tuple[str, ...]] = {
    Theme.STRATEGY: ("economic", "civilization", "strategy", "political", "wargame"),
    Theme.PARTY: ("party game", "humor", "word game", "bluffing"),
    Theme.ADVENTURE: ("adventure", "fantasy", "exploration", "fighting", "mythology"),
    Theme.MYSTERY: ("deduction", "murder", "horror", "mystery", "spies"),
    Theme.SCIFI: ("science fiction", "space exploration", "futuristic"),
    Theme.FAMILY: ("children's game", "animals", "family", "educational"),
    Theme.HISTORY: ("medieval", "ancient", "world war", "history", "renaissance"),
    Theme.BUILDING: ("city building", "territory building", "industry", "transportation"),
}

STYLE_KEYWORDS: dict[PlayStyle, tuple[str, ...]] = {
    PlayStyle.COOP: ("cooperative game", "team-based game"),
    PlayStyle.SOCIAL: ("negotiation", "trading", "communication", "voting", "bluffing"),
    PlayStyle.ENGINE: ("deck, bag, and pool building", "income", "tableau building", "tech trees"),
    PlayStyle.LUCK: ("dice rolling", "push your luck", "random production"),
    PlayStyle.PUZZLE: ("tile placement", "pattern building", "set collection", "map addition"),
    PlayStyle.SOLO: ("solo / solitaire game",),
}

DIFFICULTY_CENTERS = {1: 1.5, 2: 2.5, 3: 3.7}

# 별점이 3개 미만이면 취향을 알 수 없어서 인기 게임을 보여줍니다.
MIN_TASTE_RATINGS = 3
# 별점 n개일 때 개인화 비중은 n / (n + 5). 5개면 절반, 20개면 80%입니다.
CONFIDENCE_K = 5


@dataclass(frozen=True)
class BoardGame:
    item_id: int
    bgg_id: int
    name: str
    min_players: int
    max_players: int
    max_playtime: int
    average_rating: float
    bayes_rating: float
    complexity: float
    users_rated: int
    categories: tuple[str, ...]
    mechanics: tuple[str, ...]
    themes: tuple[Theme, ...]
    play_styles: tuple[PlayStyle, ...]

    @property
    def tokens(self) -> tuple[str, ...]:
        """분류와 메커니즘을 'category:', 'mechanic:' 접두어가 붙은 소문자 토큰으로 반환합니다."""

        return tuple(f"category:{value.lower()}" for value in self.categories) + tuple(
            f"mechanic:{value.lower()}" for value in self.mechanics
        )


def _parse_list(raw: str) -> tuple[str, ...]:
    """CSV에 문자열로 저장된 목록을 안전하게 변환합니다."""

    value = ast.literal_eval(raw) if raw else []
    if not isinstance(value, list):
        raise ValueError(f"목록 형태의 메타데이터가 필요합니다: {type(value).__name__}")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _map_labels(values: Iterable[str], mapping):
    """BGG 영문 분류를 화면에서 사용하는 테마와 플레이 방식으로 묶습니다."""

    normalized = " | ".join(values).lower()
    return tuple(label for label, keywords in mapping.items() if any(word in normalized for word in keywords))


def load_games(path: Path) -> list[BoardGame]:
    """ML_RecSys에서 생성한 게임 카탈로그 CSV를 읽습니다."""

    games: list[BoardGame] = []
    with path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            categories = _parse_list(row["categories"])
            mechanics = _parse_list(row["mechanics"])
            games.append(
                BoardGame(
                    item_id=int(row["item_id"]),
                    bgg_id=int(row["bgg_id"]),
                    name=row["name"],
                    min_players=int(float(row["min_players"])),
                    max_players=int(float(row["max_players"])),
                    max_playtime=int(float(row["max_playtime"])),
                    average_rating=float(row["average_rating"]),
                    bayes_rating=float(row["bayes_average_rating"]),
                    complexity=float(row["complexity"]),
                    users_rated=int(float(row["users_rated"])),
                    categories=categories,
                    mechanics=mechanics,
                    themes=_map_labels(categories, THEME_KEYWORDS),
                    play_styles=_map_labels(mechanics, STYLE_KEYWORDS),
                )
            )
    if not games:
        raise ValueError(f"게임 데이터가 없습니다: {path}")
    return games


class ContentBasedRecommender:
    """카탈로그 콘텐츠와 미리 학습한 게임 이웃을 결합한 추천기입니다."""

    def __init__(self, games: list[BoardGame], neighbors_path: Path | None = None) -> None:
        """게임 목록으로 TF-IDF 특징 벡터를 만들고, 오프라인에서 계산한 이웃 점수를 불러옵니다."""

        self.games = games
        self.by_id = {game.item_id: game for game in games}
        self.vectors = self._fit_tfidf(games)
        self.neighbors = self._load_neighbors(neighbors_path)

    @staticmethod
    def _load_neighbors(path: Path | None) -> dict[int, dict[int, float]]:
        """오프라인 학습으로 만든 게임별 이웃 점수를 읽습니다."""

        if path is None or not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            int(item_id): {int(other): float(score) for other, score in values}
            for item_id, values in payload["neighbors"].items()
        }

    @staticmethod
    def _fit_tfidf(games: list[BoardGame]) -> dict[int, dict[str, float]]:
        """자주 등장하는 분류의 영향은 낮추고 희소한 특징의 영향은 높입니다."""

        document_frequency = Counter(token for game in games for token in set(game.tokens))
        vectors: dict[int, dict[str, float]] = {}
        for game in games:
            counts = Counter(game.tokens)
            weighted = {
                token: count * (math.log((1 + len(games)) / (1 + document_frequency[token])) + 1)
                for token, count in counts.items()
            }
            norm = math.sqrt(sum(value * value for value in weighted.values())) or 1.0
            vectors[game.item_id] = {token: value / norm for token, value in weighted.items()}
        return vectors

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        """두 게임 특징 벡터의 방향 유사도를 계산합니다."""

        if len(left) > len(right):
            left, right = right, left
        return sum(value * right.get(token, 0.0) for token, value in left.items())

    def _rating_affinity(
        self, ratings: Iterable[UserGameRating]
    ) -> tuple[set[int], dict[int, float]]:
        """이미 평가한 게임 ID와 별점으로 계산한 이웃 게임별 보정 점수를 반환합니다."""

        known = [rating for rating in ratings if rating.dataset_item_id in self.by_id]
        excluded = {rating.dataset_item_id for rating in known}
        weighted = Counter()
        total_weight = 0.0
        for rating in known:
            # 1~10점의 중간값인 5.5점을 기준으로 -1~1 범위의 신호를 만듭니다.
            signal = (rating.rating - 5.5) / 4.5
            if math.isclose(signal, 0.0):
                continue
            total_weight += abs(signal)
            for candidate_id, similarity in self.neighbors.get(rating.dataset_item_id, {}).items():
                weighted[candidate_id] += similarity * signal
        if total_weight == 0:
            return excluded, {}
        # 별점이 많을수록 보정 점수의 범위가 커지지 않도록 전체 신호의 절댓값 합으로 나눕니다.
        return excluded, {
            candidate_id: score / total_weight for candidate_id, score in weighted.items()
        }

    def recommend_context(
        self,
        preference: ContextPreferenceRequest,
        limit: int = 12,
        ratings: Iterable[UserGameRating] = (),
    ) -> list[RecommendationItem]:
        """상황 추천입니다.

        인원과 시간 조건을 통과한 게임을 난이도, 테마, 플레이 방식, 평점으로 점수화해
        상위 limit개를 반환합니다. 별점이 있으면 이웃 게임 점수를 더해 보정합니다.
        """

        # 1단계: 화면의 3단계 난이도를 BGG complexity 점수의 중심값으로 바꿉니다.
        target_complexity = DIFFICULTY_CENTERS[preference.difficulty]
        # 2단계: 인원과 시간은 점수가 아니라 실제 플레이 가능 여부로 먼저 거릅니다.
        rated_ids, affinity = self._rating_affinity(ratings)
        candidates = [
            game
            for game in self.games
            if game.item_id not in rated_ids
            and game.min_players <= preference.player_count <= game.max_players
            and game.max_playtime <= preference.max_play_time
        ]
        scored = []
        for game in candidates:
            # 3단계: 난이도·테마·방식·평점을 0~1 신호로 정규화해 가중 합산합니다.
            theme_overlap = len(set(preference.themes) & set(game.themes))
            style_overlap = len(set(preference.play_styles) & set(game.play_styles))
            complexity_match = max(0.0, 1.0 - abs(game.complexity - target_complexity) / 3.0)
            rating_quality = max(0.0, min(1.0, (game.bayes_rating - 5.5) / 3.5))
            score = 0.35 * complexity_match + 0.30 * min(1.0, theme_overlap / 2) + 0.25 * min(
                1.0, style_overlap / 2
            ) + 0.10 * rating_quality
            score += 0.20 * affinity.get(game.item_id, 0.0)
            scored.append((score, game))
        # 4단계: 동점이면 검증된 평점과 고정 ID를 사용해 결과 순서를 안정적으로 유지합니다.
        scored.sort(key=lambda pair: (-pair[0], -pair[1].bayes_rating, pair[1].item_id))
        return [self._to_item(game, score, preference) for score, game in scored[:limit]]

    def known_rating_count(self, ratings: Iterable[UserGameRating]) -> int:
        """카탈로그에 있는 게임에 남긴 별점 개수를 반환합니다."""

        return len({rating.dataset_item_id for rating in ratings if rating.dataset_item_id in self.by_id})

    def recommend_popular(
        self,
        limit: int = 12,
        ratings: Iterable[UserGameRating] = (),
    ) -> list[RecommendationItem]:
        """베이지안 평점이 높은 순서로 추천합니다. 이미 평가한 게임은 뺍니다."""

        rated_ids = {rating.dataset_item_id for rating in ratings}
        ranked = sorted(
            (game for game in self.games if game.item_id not in rated_ids),
            key=lambda game: (-game.bayes_rating, game.item_id),
        )
        return [
            self._to_item(
                game,
                self._rating_quality(game),
                None,
                reason="BGG 베이지안 평점이 높은 인기 게임",
            )
            for game in ranked[:limit]
        ]

    @staticmethod
    def _rating_quality(game: BoardGame) -> float:
        """BGG 베이지안 평점(5.5~9점)을 0~1 범위 점수로 정규화합니다."""

        return max(0.0, min(1.0, (game.bayes_rating - 5.5) / 3.5))

    def recommend_taste(
        self,
        preference: TastePreferenceRequest,
        limit: int = 12,
        ratings: Iterable[UserGameRating] = (),
    ) -> list[RecommendationItem]:
        """취향 추천입니다.

        별점이 3개 미만이면 인기 게임을 반환하고, 그 이상이면 별점으로 만든 취향 프로필과
        이웃 게임 점수로 점수화합니다. 이미 평가한 게임은 제외합니다.
        """

        # 같은 게임의 별점이 여러 개면 마지막 값만 쓰고, 카탈로그에 없는 게임은 뺍니다.
        rated = {r.dataset_item_id: r for r in ratings if r.dataset_item_id in self.by_id}
        if len(rated) < MIN_TASTE_RATINGS:
            return self.recommend_popular(limit, rated.values())

        # 별점을 -1~1로 바꿉니다. 5.5점보다 낮으면 음수라서 비슷한 게임이 아래로 내려갑니다.
        profile: Counter[str] = Counter()
        item_cf: Counter[int] = Counter()
        for rating in rated.values():
            signal = (rating.rating - 5.5) / 4.5
            for token, value in self.vectors[rating.dataset_item_id].items():
                profile[token] += signal * value
            for other_id, similarity in self.neighbors.get(rating.dataset_item_id, {}).items():
                item_cf[other_id] += signal * similarity
        norm = math.sqrt(sum(v * v for v in profile.values())) or 1.0
        profile = {token: value / norm for token, value in profile.items()}
        cf_scale = max((abs(v) for v in item_cf.values()), default=0.0) or 1.0

        # 별점이 쌓일수록 내 취향 점수를 더 믿고, 적을 땐 인기 점수가 받쳐 줍니다.
        confidence = len(rated) / (len(rated) + CONFIDENCE_K)
        scored = []
        for game in self.games:
            if game.item_id in rated:
                continue
            content = self._cosine(profile, self.vectors[game.item_id])
            taste = 0.7 * item_cf[game.item_id] / cf_scale + 0.3 * content
            score = confidence * taste + (1 - confidence) * self._rating_quality(game)
            scored.append((score, game))
        scored.sort(key=lambda pair: (-pair[0], -pair[1].bayes_rating, pair[1].item_id))
        return [self._to_item(game, score, preference) for score, game in scored[:limit]]

    def recommend(
        self,
        preference,
        limit: int = 12,
        ratings: Iterable[UserGameRating] = (),
    ) -> list[RecommendationItem]:
        """선호 조건의 종류에 따라 상황 추천과 취향 추천 중 알맞은 쪽으로 넘깁니다."""

        if isinstance(preference, ContextPreferenceRequest):
            return self.recommend_context(preference, limit, ratings)
        return self.recommend_taste(preference, limit, ratings)

    @staticmethod
    def _to_item(
        game: BoardGame, raw_score: float, preference, reason: str | None = None
    ) -> RecommendationItem:
        """내부 게임 정보를 프런트가 사용하는 응답 형식으로 변환합니다."""

        matched_themes = set(getattr(preference, "themes", [])) & set(game.themes)
        matched_styles = set(getattr(preference, "play_styles", [])) & set(game.play_styles)
        if reason is not None:
            pass
        elif matched_themes:
            reason = f"선호 테마와 {len(matched_themes)}개 일치하고 인원·시간 조건에 맞는 게임"
        elif matched_styles:
            reason = f"원하는 플레이 방식과 {len(matched_styles)}개 일치하는 게임"
        else:
            reason = f"{game.categories[0] if game.categories else '보드게임'} 특성이 내 별점 취향과 유사한 게임"
        return RecommendationItem(
            gameId=game.item_id,
            bggId=game.bgg_id,
            title=game.name,
            localizedTitle=None,
            category=game.categories[0] if game.categories else "Board Game",
            minPlayers=game.min_players,
            maxPlayers=game.max_players,
            maxPlayTime=game.max_playtime,
            complexity=game.complexity,
            averageRating=game.average_rating,
            themes=list(game.themes),
            playStyles=list(game.play_styles),
            score=round(max(0.0, min(1.0, raw_score)) * 100),
            reason=reason,
        )


DEFAULT_GAMES_PATH = Path(__file__).resolve().parents[1] / "data" / "games.csv"
DEFAULT_NEIGHBORS_PATH = Path(__file__).resolve().parents[1] / "data" / "models" / "item_neighbors.json"
recommender = ContentBasedRecommender(load_games(DEFAULT_GAMES_PATH), DEFAULT_NEIGHBORS_PATH)
