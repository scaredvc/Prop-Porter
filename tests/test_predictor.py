from pathlib import Path

import joblib
import pytest

from src.predictor import (
    PredictionInputError,
    find_latest_player_row,
    load_artifact,
    normalize_player_name,
    predict_for_player,
)


def test_normalize_player_name_is_case_and_space_insensitive():
    assert normalize_player_name("  STEPHEN   curry ") == "stephen curry"


def test_normalize_player_name_rejects_empty():
    with pytest.raises(PredictionInputError, match="cannot be empty"):
        normalize_player_name("   ")


def test_find_latest_player_row_matches_case_insensitively(valid_game_logs_df):
    from src.features import build_features

    featured = build_features(valid_game_logs_df)
    row = find_latest_player_row(featured, "alice")
    assert row["player_name"] == "Alice"
    assert int(row["points"]) == 30


def test_find_latest_player_row_suggests_close_match(valid_game_logs_df):
    from src.features import build_features

    featured = build_features(valid_game_logs_df)
    with pytest.raises(PredictionInputError, match="Did you mean"):
        find_latest_player_row(featured, "Alic")


def test_load_artifact_rejects_missing_file(tmp_path):
    missing_path = tmp_path / "missing.pkl"
    with pytest.raises(PredictionInputError, match="Model file not found"):
        load_artifact(missing_path)


def test_load_artifact_rejects_invalid_payload(tmp_path):
    bad_path = tmp_path / "bad.pkl"
    joblib.dump({"model": "x"}, bad_path)
    with pytest.raises(PredictionInputError, match="missing model or features"):
        load_artifact(bad_path)


def test_predict_for_player_returns_prediction():
    result = predict_for_player("stephen curry")
    assert result.player_name == "Stephen Curry"
    assert isinstance(result.predicted_points, float)
    assert result.game_date == "2024-01-19"
