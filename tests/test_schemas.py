import pytest
from pydantic import ValidationError

from app.schemas import ContextPreferenceRequest, TastePreferenceRequest


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


def test_taste_preference_requires_three_known_game_ids() -> None:
    preference = TastePreferenceRequest.model_validate(
        {"recommendationMode": "taste", "likedGameIds": [0, 1, 2]}
    )
    assert preference.liked_game_ids == [0, 1, 2]

    with pytest.raises(ValidationError):
        TastePreferenceRequest.model_validate(
            {"recommendationMode": "taste", "likedGameIds": [0, 1]}
        )


def test_taste_preference_rejects_duplicate_game_ids() -> None:
    with pytest.raises(ValidationError):
        TastePreferenceRequest.model_validate(
            {"recommendationMode": "taste", "likedGameIds": [0, 0, 1]}
        )
