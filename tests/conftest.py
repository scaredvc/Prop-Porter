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
