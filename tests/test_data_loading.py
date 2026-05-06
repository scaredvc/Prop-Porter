import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data_loading import (
    REQUIRED_COLUMNS,
    load_game_logs,
    load_game_logs_from_csv,
    validate_columns,
    validate_game_logs,
    validate_no_duplicates,
    validate_no_nulls,
)


# ── Column validation ──────────────────────────────────────────────────────


def test_validate_columns_all_present(valid_game_logs_df):
    result = validate_columns(valid_game_logs_df)
    assert list(result.columns) is not None  # no error raised


def test_validate_columns_missing_required(valid_game_logs_df):
    df = valid_game_logs_df.drop(columns=["points"])
    with pytest.raises(ValueError, match="points"):
        validate_columns(df)


def test_validate_columns_adds_optional_as_nan(valid_game_logs_df):
    result = validate_columns(valid_game_logs_df)
    assert "usage" in result.columns
    assert result["usage"].isna().all()


def test_validate_columns_coerces_game_date_string():
    df = pd.DataFrame(
        {
            "game_id": ["G001"],
            "game_date": ["2024-01-10"],  # string, not datetime
            "player_id": [101],
            "player_name": ["Alice"],
            "team_id": [1],
            "opponent_team_id": [2],
            "home_flag": [True],
            "points": [25],
            "minutes": [34.5],
            "fga": [20],
        }
    )
    result = validate_columns(df)
    assert pd.api.types.is_datetime64_any_dtype(result["game_date"])


def test_validate_columns_coerces_home_flag_int():
    df = pd.DataFrame(
        {
            "game_id": ["G001", "G002"],
            "game_date": ["2024-01-10", "2024-01-12"],
            "player_id": [101, 102],
            "player_name": ["Alice", "Bob"],
            "team_id": [1, 2],
            "opponent_team_id": [2, 1],
            "home_flag": [1, 0],  # ints, should become bools
            "points": [25, 18],
            "minutes": [34.5, 28.0],
            "fga": [20, 15],
        }
    )
    result = validate_columns(df)
    assert result["home_flag"].dtype == bool
    assert result["home_flag"].iloc[0] == True
    assert result["home_flag"].iloc[1] == False


# ── Duplicate validation ──────────────────────────────────────────────────


def test_validate_no_duplicates_clean(valid_game_logs_df):
    validate_no_duplicates(valid_game_logs_df)  # no error


def test_validate_no_duplicates_raises():
    df = pd.DataFrame(
        {
            "player_id": [101, 101],
            "game_id": ["G001", "G001"],
        }
    )
    with pytest.raises(ValueError, match="duplicate"):
        validate_no_duplicates(df)


# ── Null validation ───────────────────────────────────────────────────────


def test_validate_no_nulls_clean(valid_game_logs_df):
    validate_no_nulls(valid_game_logs_df)  # no error


def test_validate_no_nulls_player_id():
    df = pd.DataFrame(
        {
            "player_id": [None, 102],
            "game_date": pd.to_datetime(["2024-01-10", "2024-01-12"]),
        }
    )
    with pytest.raises(ValueError, match="player_id"):
        validate_no_nulls(df)


def test_validate_no_nulls_game_date():
    df = pd.DataFrame(
        {
            "player_id": [101, 102],
            "game_date": pd.to_datetime(["2024-01-10", None]),
        }
    )
    with pytest.raises(ValueError, match="game_date"):
        validate_no_nulls(df)


def test_validate_no_nulls_optional_columns_ok(valid_game_logs_df):
    valid_game_logs_df["usage"] = pd.NA
    validate_no_nulls(valid_game_logs_df)  # no error


# ── CSV loading ───────────────────────────────────────────────────────────


def test_load_csv_valid(tmp_path, valid_game_logs_df):
    csv_path = tmp_path / "game_logs.csv"
    valid_game_logs_df.to_csv(csv_path, index=False)
    result = load_game_logs_from_csv(str(csv_path))
    df = validate_game_logs(result)
    assert len(df) == 4


def test_load_csv_missing_file():
    with pytest.raises(FileNotFoundError):
        load_game_logs_from_csv("/nonexistent/path/game_logs.csv")


def test_load_csv_missing_required_column(tmp_path, valid_game_logs_df):
    df = valid_game_logs_df.drop(columns=["points"])
    csv_path = tmp_path / "bad.csv"
    df.to_csv(csv_path, index=False)
    loaded = load_game_logs_from_csv(str(csv_path))
    with pytest.raises(ValueError, match="points"):
        validate_game_logs(loaded)


# ── DB loading (mocked) ──────────────────────────────────────────────────


@patch("src.data_loading.pd.read_sql_query")
@patch("src.data_loading.get_db_connection")
def test_load_db_sql_contains_expected_joins(mock_conn, mock_read_sql, valid_game_logs_df):
    mock_read_sql.return_value = valid_game_logs_df
    mock_connection = MagicMock()
    mock_conn.return_value = mock_connection

    from src.data_loading import load_game_logs_from_db

    load_game_logs_from_db(start_date="2024-01-01", end_date="2024-12-31")

    sql_arg = mock_read_sql.call_args[0][0]
    assert "game_opponents" in sql_arg
    assert "JOIN players p" in sql_arg
    assert "JOIN game_opponents go" in sql_arg


@patch("src.data_loading.get_db_connection")
def test_auto_mode_falls_back_to_csv(mock_conn, tmp_path, valid_game_logs_df):
    mock_conn.side_effect = Exception("connection refused")

    csv_path = tmp_path / "game_logs.csv"
    valid_game_logs_df.to_csv(csv_path, index=False)

    with pytest.warns(match="DB connection failed"):
        result = load_game_logs(source="auto", csv_path=str(csv_path))
    assert len(result) == 4
