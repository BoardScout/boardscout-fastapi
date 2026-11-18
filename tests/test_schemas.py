import pytest
from pydantic import ValidationError

from app.schemas import ContextPreferenceRequest, TastePreferenceRequest, UserGameRating


def test_context_preference_accepts_bgg_feature_contract() -> None:
    preference = ContextPreferenceRequest.model_validate(
        {
            "recommendationMode": "context",
            "playerCount": 4,
            "maxPlayTime": 90,
            "difficulty": 2,
            "themes": ["strategy", "building"],
            "playStyles": ["engine", "puzzle"],
        }
    )

    assert preference.player_count == 4
    assert preference.model_dump(by_alias=True)["playStyles"] == ["engine", "puzzle"]


def test_context_preference_rejects_unknown_dataset_mapping() -> None:
    with pytest.raises(ValidationError):
        ContextPreferenceRequest.model_validate(
            {
                "playerCount": 0,
                "maxPlayTime": 5,
                "difficulty": 4,
                "themes": ["romance"],
                "playStyles": ["unknown"],
            }
        )


def test_taste_preference_needs_only_the_mode() -> None:
    preference = TastePreferenceRequest.model_validate({"recommendationMode": "taste"})
    assert preference.recommendation_mode == "taste"


def test_taste_preference_rejects_liked_game_ids() -> None:
    # 취향 추천은 별점으로만 계산하므로 게임 ID 목록은 받지 않는다.
    with pytest.raises(ValidationError):
        TastePreferenceRequest.model_validate(
            {"recommendationMode": "taste", "likedGameIds": [0, 1, 2]}
        )


def test_user_rating_uses_bgg_ten_point_scale() -> None:
    assert UserGameRating.model_validate({"datasetItemId": 7, "rating": 1}).rating == 1
    assert UserGameRating.model_validate({"datasetItemId": 7, "rating": 10}).rating == 10

    for rating in (0, 10.1):
        with pytest.raises(ValidationError):
            UserGameRating.model_validate({"datasetItemId": 7, "rating": rating})
