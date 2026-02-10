"""Feature engineering for player game logs.

Builds leakage-safe rolling statistics, rest metrics, and context
features from validated game-log DataFrames.  Every rolling window
uses ``.shift(1)`` so the current game's stats are never included
in the feature value for that game.
"""

import pandas as pd

# ---------------------------------------------------------------------------
# Rolling helpers (private)
# ---------------------------------------------------------------------------

def _rolling_mean_series(s: pd.Series, window: int, min_periods: int = 1) -> pd.Series:
    """Rolling mean shifted by 1 to exclude the current row."""
    return s.rolling(window=window, min_periods=min_periods).mean().shift(1)


def _rolling_std_series(s: pd.Series, window: int, min_periods: int = 1) -> pd.Series:
    """Rolling std shifted by 1 to exclude the current row."""
    return s.rolling(window=window, min_periods=min_periods).std().shift(1)


# ---------------------------------------------------------------------------
# Rolling helpers (public wrappers)
# ---------------------------------------------------------------------------

def rolling_mean_excl_current(
    group: pd.DataFrame, col: str, window: int, min_periods: int = 1
) -> pd.Series:
    """Rolling mean of *col* within *group*, excluding the current game."""
    return _rolling_mean_series(group[col], window, min_periods)


def rolling_std_excl_current(
    group: pd.DataFrame, col: str, window: int, min_periods: int = 1
) -> pd.Series:
    """Rolling std of *col* within *group*, excluding the current game."""
    return _rolling_std_series(group[col], window, min_periods)


# ---------------------------------------------------------------------------
# Data-driven feature definitions
# ---------------------------------------------------------------------------

# (output_col, source_col, window, optional?)
ROLLING_FEATURES = [
    ("ppg_last_5",   "points",  5,  False),
    ("ppg_last_10",  "points",  10, False),
    ("min_last_5",   "minutes", 5,  False),
    ("shots_last_5", "fga",     5,  False),
    ("usage_last_5", "usage",   5,  True),
    ("ts_last_5",    "ts",      5,  True),
]

STD_FEATURES = [
    ("points_std_last_10", "points", 10, False),
]

CONTEXT_COLUMNS = ["home_flag", "team_pace", "opp_pace", "opp_def_rating"]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_player_features(df_games: pd.DataFrame, min_periods: int = 1) -> pd.DataFrame:
    """Build player-level features from game logs.

    Parameters
    ----------
    df_games : DataFrame
        Validated game-log DataFrame (output of ``validate_game_logs``).
    min_periods : int, optional
        Minimum observations in a rolling window to produce a value
        (default 1).

    Returns
    -------
    DataFrame
        A copy of the input with new feature columns appended.
    """
    df = df_games.copy()

    # Ensure game_date is datetime and sort
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.sort_values(by=["player_id", "game_date"]).reset_index(drop=True)

    # --- Rolling mean features ---
    for out_col, src_col, window, optional in ROLLING_FEATURES:
        if optional and src_col not in df.columns:
            continue
        df[out_col] = df.groupby("player_id")[src_col].transform(
            lambda s: _rolling_mean_series(s, window, min_periods)
        )

    # --- Rolling std features ---
    for out_col, src_col, window, optional in STD_FEATURES:
        if optional and src_col not in df.columns:
            continue
        df[out_col] = df.groupby("player_id")[src_col].transform(
            lambda s: _rolling_std_series(s, window, min_periods)
        )

    # --- Rest metrics ---
    df["prev_game_date"] = df.groupby("player_id")["game_date"].shift(1)
    df["days_rest"] = (
        (df["game_date"] - df["prev_game_date"]).dt.days.fillna(7).clip(lower=0, upper=10)
    )
    df["b2b_flag"] = (df["days_rest"] == 1).astype(int)
    df.drop(columns=["prev_game_date"], inplace=True)

    # --- Context columns (ensure they exist) ---
    for col in CONTEXT_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    return df
