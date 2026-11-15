from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.recommender import ContentBasedRecommender, load_games
from app.schemas import ContextPreferenceRequest, TastePreferenceRequest


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


def test_taste_recommendations_exclude_liked_games_and_are_deterministic(model) -> None:
    preference = TastePreferenceRequest.model_validate(
        {"recommendationMode": "taste", "likedGameIds": [0, 1, 2]}
    )

    first = model.recommend(preference, limit=10)
    second = model.recommend(preference, limit=10)

    assert [item.game_id for item in first] == [item.game_id for item in second]
    assert not ({item.game_id for item in first} & {0, 1, 2})
    assert all(0 <= item.score <= 100 for item in first)
    assert model.neighbors


def test_recommendation_api_accepts_frontend_contract() -> None:
    response = TestClient(app).post(
        "/api/recommend/games?limit=5",
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


def test_taste_api_reports_hybrid_strategy() -> None:
    response = TestClient(app).post(
        "/api/recommend/games?limit=5",
        json={"recommendationMode": "taste", "likedGameIds": [0, 1, 2]},
    )

    assert response.status_code == 200
    assert response.json()["result"]["strategy"] == "content-item-hybrid"


def test_recommendation_api_returns_common_validation_error() -> None:
    response = TestClient(app).post(
        "/api/recommend/games",
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
