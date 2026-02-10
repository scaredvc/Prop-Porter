import pandas as pd
import pytest


@pytest.fixture
def valid_game_logs_df():
    """Small synthetic DataFrame: 4 rows, 2 games, 3 players."""
    return pd.DataFrame(
        {
            "game_id": ["G001", "G001", "G002", "G002"],
            "game_date": pd.to_datetime(
                ["2024-01-10", "2024-01-10", "2024-01-12", "2024-01-12"]
            ),
            "player_id": [101, 102, 101, 103],
            "player_name": ["Alice", "Bob", "Alice", "Charlie"],
            "team_id": [1, 2, 1, 2],
            "opponent_team_id": [2, 1, 2, 1],
            "home_flag": [True, False, True, False],
            "points": [25, 18, 30, 12],
            "minutes": [34.5, 28.0, 36.0, 22.5],
            "fga": [20, 15, 22, 10],
        }
    )


@pytest.fixture
def feature_game_logs_df():
    """2 players x 12 games each (24 rows) for feature tests.

    Player 101 scores 20, 21, ..., 31 (linearly increasing).
    Player 102 scores 30, 29, ..., 19 (linearly decreasing).
    Games every 2 days starting 2024-01-01.
    """
    n = 12
    dates = pd.date_range("2024-01-01", periods=n, freq="2D")

    rows = []
    for i in range(n):
        rows.append(
            {
                "game_id": f"G{i+1:03d}",
                "game_date": dates[i],
                "player_id": 101,
                "player_name": "Alice",
                "team_id": 1,
                "opponent_team_id": 2,
                "home_flag": i % 2 == 0,
                "points": 20 + i,
                "minutes": 30.0 + i,
                "fga": 15 + i,
            }
        )
        rows.append(
            {
                "game_id": f"G{i+1:03d}",
                "game_date": dates[i],
                "player_id": 102,
                "player_name": "Bob",
                "team_id": 2,
                "opponent_team_id": 1,
                "home_flag": i % 2 != 0,
                "points": 30 - i,
                "minutes": 35.0 - i,
                "fga": 20 - i,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def b2b_game_logs_df():
    """Player 101 with 5 games including back-to-back pairs.

    Jan 1, Jan 2 (b2b), Jan 5, Jan 6 (b2b), Jan 15 (long rest).
    """
    dates = pd.to_datetime(
        ["2024-01-01", "2024-01-02", "2024-01-05", "2024-01-06", "2024-01-15"]
    )
    return pd.DataFrame(
        {
            "game_id": [f"G{i+1:03d}" for i in range(5)],
            "game_date": dates,
            "player_id": [101] * 5,
            "player_name": ["Alice"] * 5,
            "team_id": [1] * 5,
            "opponent_team_id": [2] * 5,
            "home_flag": [True, False, True, False, True],
            "points": [20, 22, 18, 25, 30],
            "minutes": [32.0, 34.0, 28.0, 36.0, 38.0],
            "fga": [15, 18, 12, 20, 22],
        }
    )
