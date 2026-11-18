from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.recommender import BoardGame, ContentBasedRecommender, load_games
from app.schemas import ContextPreferenceRequest, TastePreferenceRequest, UserGameRating


DATASET_DIR = Path(__file__).parents[1] / "data"


@pytest.fixture(scope="module")
def model() -> ContentBasedRecommender:
    return ContentBasedRecommender(
        load_games(DATASET_DIR / "games.csv"),
        DATASET_DIR / "models" / "item_neighbors.json",
    )


def test_context_recommendations_respect_hard_player_and_time_filters(model) -> None:
    preference = ContextPreferenceRequest.model_validate(
        {
            "recommendationMode": "context",
            "playerCount": 2,
            "maxPlayTime": 30,
            "difficulty": 2,
            "themes": ["strategy"],
            "playStyles": ["puzzle"],
        }
    )

    recommendations = model.recommend(preference, limit=20)

    assert recommendations
    assert all(item.min_players <= 2 <= item.max_players for item in recommendations)
    assert all(item.max_play_time <= 30 for item in recommendations)


TASTE = TastePreferenceRequest.model_validate({"recommendationMode": "taste"})


def make_games(count: int, bayes: dict[int, float] | None = None) -> list[BoardGame]:
    bayes = bayes or {}
    return [
        BoardGame(
            item_id=item_id,
            bgg_id=1000 + item_id,
            name=f"Game {item_id}",
            min_players=1,
            max_players=4,
            max_playtime=60,
            average_rating=7.0,
            bayes_rating=bayes.get(item_id, 7.0),
            complexity=2.5,
            users_rated=100,
            categories=("Strategy",),
            mechanics=("Deck Building",),
            themes=(),
            play_styles=(),
        )
        for item_id in range(count)
    ]


def ratings_of(*pairs: tuple[int, float]) -> list[UserGameRating]:
    return [UserGameRating(datasetItemId=item_id, rating=value) for item_id, value in pairs]


def test_taste_uses_popular_games_when_ratings_are_missing(model) -> None:
    result = model.recommend(TASTE, limit=20)

    bayes = [model.by_id[item.game_id].bayes_rating for item in result]
    assert len(result) == 20
    assert bayes == sorted(bayes, reverse=True)


def test_taste_uses_popular_games_below_three_ratings(model) -> None:
    ratings = ratings_of((0, 9), (1, 9))

    result = model.recommend(TASTE, limit=20, ratings=ratings)

    assert not ({item.game_id for item in result} & {0, 1})
    assert model.known_rating_count(ratings) == 2


def test_taste_excludes_rated_games_and_is_deterministic(model) -> None:
    ratings = ratings_of((0, 9), (1, 8), (2, 7), (3, 3))

    first = model.recommend(TASTE, limit=20, ratings=ratings)
    second = model.recommend(TASTE, limit=20, ratings=ratings)

    assert len(first) == 20
    assert [item.game_id for item in first] == [item.game_id for item in second]
    assert not ({item.game_id for item in first} & {0, 1, 2, 3})
    assert all(0 <= item.score <= 100 for item in first)


def test_high_and_low_ratings_move_neighbors_in_opposite_directions() -> None:
    local = ContentBasedRecommender(make_games(8))
    local.neighbors = {0: {4: 0.9}}
    others = [(1, 5.5), (2, 5.5)]

    liked = local.recommend(TASTE, ratings=ratings_of((0, 10), *others))
    disliked = local.recommend(TASTE, ratings=ratings_of((0, 1), *others))

    assert liked[0].game_id == 4
    assert disliked[-1].game_id == 4


def test_more_ratings_make_the_neighbor_signal_stronger() -> None:
    local = ContentBasedRecommender(make_games(30, bayes={4: 5.5}))
    local.neighbors = {0: {4: 0.9}}
    few = ratings_of((0, 10), (1, 5.5), (2, 5.5))
    many = few + ratings_of(*[(i, 5.5) for i in range(5, 25)])

    score_few = next(i.score for i in local.recommend(TASTE, limit=30, ratings=few) if i.game_id == 4)
    score_many = next(i.score for i in local.recommend(TASTE, limit=30, ratings=many) if i.game_id == 4)

    assert score_many > score_few


def test_context_rating_adjusts_ranking_and_excludes_rated_game() -> None:
    local = ContentBasedRecommender(make_games(6))
    local.neighbors = {0: {4: 0.9}}
    preference = ContextPreferenceRequest.model_validate(
        {"recommendationMode": "context", "playerCount": 2, "maxPlayTime": 60, "difficulty": 2}
    )

    positive = local.recommend(preference, ratings=ratings_of((0, 10)))
    negative = local.recommend(preference, ratings=ratings_of((0, 1)))

    assert positive[0].game_id == 4
    assert negative[0].game_id != 4
    assert all(item.game_id != 0 for item in positive + negative)


def test_recommendation_api_accepts_frontend_contract() -> None:
    response = TestClient(app).post(
        "/api/v1/recommendations/games?limit=5",
        json={
            "recommendationMode": "context",
            "playerCount": 4,
            "maxPlayTime": 60,
            "difficulty": 2,
            "themes": ["strategy"],
            "playStyles": ["engine"],
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["strategy"] == "content-based"
    assert len(payload["items"]) == 5


def test_taste_api_returns_popular_games_without_login() -> None:
    response = TestClient(app).post(
        "/api/v1/recommendations/games?limit=20", json={"recommendationMode": "taste"}
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["strategy"] == "popularity"
    assert result["personalized"] is False
    assert result["ratingCount"] == 0
    assert result["minRatingsRequired"] == 3
    assert len(result["items"]) == 20


def test_taste_api_personalizes_with_three_or_more_ratings() -> None:
    class FakeRatingStore:
        async def get_ratings(self, session_id: str):
            assert session_id == "a" * 43
            return ratings_of((3, 9), (5, 8), (7, 2))

    with TestClient(app) as client:
        app.state.rating_store = FakeRatingStore()
        client.cookies.set("BGSESSION", "a" * 43)
        response = client.post(
            "/api/v1/recommendations/games?limit=20", json={"recommendationMode": "taste"}
        )

    result = response.json()["result"]
    assert response.status_code == 200
    assert result["strategy"] == "rating-profile-hybrid"
    assert result["personalized"] is True
    assert result["ratingCount"] == 3
    assert not ({item["gameId"] for item in result["items"]} & {3, 5, 7})


def test_recommendation_api_returns_common_validation_error() -> None:
    response = TestClient(app).post(
        "/api/v1/recommendations/games",
        json={
            "recommendationMode": "context",
            "playerCount": 0,
            "maxPlayTime": 5,
            "difficulty": 4,
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["code"] == "COMMON-422"
    assert "context.playerCount" in payload["result"]["errors"]
