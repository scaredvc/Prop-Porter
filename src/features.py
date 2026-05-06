"""Feature engineering for NBA player points prediction."""

from __future__ import annotations

import pandas as pd


FEATURE_COLUMNS = [
    "player_points_last_5",
    "player_points_last_10",
    "player_points_ewm_span_5",
    "player_points_ewm_span_10",
    "ppm_last_5",
    "ppm_last_10",
    "ppm_ewm_span_5",
    "ppm_ewm_span_10",
    "days_rest",
    "opponent_avg_points_allowed_last_10",
    "opponent_possessions_last_10",
    "opponent_def_rating_last_10",
    "is_home",
]

TARGET_COLUMN = "points"


def _possessions_proxy(
    fga: pd.Series, oreb: pd.Series, tov: pd.Series, fta: pd.Series
) -> pd.Series:
    return (
        fga.astype(float)
        - oreb.astype(float)
        + tov.astype(float)
        + 0.44 * fta.astype(float)
    )


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create a leakage-safe feature set from historical game logs."""
    frame = df.copy()
    frame["game_date"] = pd.to_datetime(frame["game_date"])
    frame = frame.sort_values(["player_id", "game_date"]).reset_index(drop=True)

    grouped = frame.groupby("player_id", group_keys=False)

    frame["player_points_last_5"] = grouped["points"].transform(
        lambda s: s.rolling(5, min_periods=1).mean().shift(1)
    )
    frame["player_points_last_10"] = grouped["points"].transform(
        lambda s: s.rolling(10, min_periods=1).mean().shift(1)
    )
    frame["player_points_ewm_span_5"] = grouped["points"].transform(
        lambda s: s.ewm(span=5, adjust=False).mean().shift(1)
    )
    frame["player_points_ewm_span_10"] = grouped["points"].transform(
        lambda s: s.ewm(span=10, adjust=False).mean().shift(1)
    )

    def _ppm_series(group: pd.DataFrame) -> pd.Series:
        values = group["points"].astype(float) / group["minutes"].replace({0: pd.NA}).astype(
            "float64"
        )
        values = values.replace([float("inf"), float("-inf")], pd.NA)
        return values

    frame["ppm_last_5"] = grouped.apply(
        lambda g: _ppm_series(g).rolling(5, min_periods=1).mean().shift(1)
    ).reset_index(level=0, drop=True)
    frame["ppm_last_10"] = grouped.apply(
        lambda g: _ppm_series(g).rolling(10, min_periods=1).mean().shift(1)
    ).reset_index(level=0, drop=True)
    frame["ppm_ewm_span_5"] = grouped.apply(
        lambda g: _ppm_series(g).ewm(span=5, adjust=False).mean().shift(1)
    ).reset_index(level=0, drop=True)
    frame["ppm_ewm_span_10"] = grouped.apply(
        lambda g: _ppm_series(g).ewm(span=10, adjust=False).mean().shift(1)
    ).reset_index(level=0, drop=True)

    previous_game_date = grouped["game_date"].shift(1)
    frame["days_rest"] = (
        (frame["game_date"] - previous_game_date).dt.days.fillna(7).clip(0, 10)
    )
    frame["is_home"] = frame["home_flag"].astype(int)

    team_context_columns = [
        "points_allowed",
        "team_fga",
        "team_oreb",
        "team_tov",
        "team_fta",
        "opponent_fga",
        "opponent_oreb",
        "opponent_tov",
        "opponent_fta",
    ]
    has_team_context = all(
        column in frame.columns and frame[column].notna().any() for column in team_context_columns
    )

    if has_team_context:
        team_level = (
            frame[
                [
                    "team_id",
                    "game_id",
                    "game_date",
                    "points_allowed",
                    "team_fga",
                    "team_oreb",
                    "team_tov",
                    "team_fta",
                ]
            ]
            .drop_duplicates(subset=["team_id", "game_id"])
            .sort_values(["team_id", "game_date"])
            .copy()
        )
        team_level["team_possessions"] = _possessions_proxy(
            team_level["team_fga"],
            team_level["team_oreb"],
            team_level["team_tov"],
            team_level["team_fta"],
        )
        team_level["team_points_allowed_rm10"] = team_level.groupby("team_id")[
            "points_allowed"
        ].transform(lambda s: s.rolling(10, min_periods=1).mean().shift(1))
        team_level["team_possessions_rm10"] = team_level.groupby("team_id")[
            "team_possessions"
        ].transform(lambda s: s.rolling(10, min_periods=1).mean().shift(1))

        opp_features = team_level[
            [
                "team_id",
                "game_id",
                "team_points_allowed_rm10",
                "team_possessions_rm10",
            ]
        ].rename(
            columns={
                "team_id": "opponent_team_id",
                "team_points_allowed_rm10": "opponent_avg_points_allowed_last_10",
                "team_possessions_rm10": "opponent_possessions_last_10",
            }
        )

        frame = frame.merge(opp_features, on=["opponent_team_id", "game_id"], how="left")

        per_opponent_mean = frame.groupby("opponent_team_id")["points_allowed"].transform("mean")
        global_points_allowed_mean = frame["points_allowed"].mean()
        frame["opponent_avg_points_allowed_last_10"] = (
            frame["opponent_avg_points_allowed_last_10"]
            .fillna(per_opponent_mean)
            .fillna(global_points_allowed_mean)
        )

        fallback_possessions = _possessions_proxy(
            frame["opponent_fga"],
            frame["opponent_oreb"],
            frame["opponent_tov"],
            frame["opponent_fta"],
        ).mean()
        if frame["opponent_possessions_last_10"].isna().all():
            frame["opponent_possessions_last_10"] = fallback_possessions
        else:
            frame["opponent_possessions_last_10"] = frame[
                "opponent_possessions_last_10"
            ].fillna(fallback_possessions)
    else:
        frame["opponent_avg_points_allowed_last_10"] = 115.0
        frame["opponent_possessions_last_10"] = 100.0

    frame["opponent_def_rating_last_10"] = 100.0 * (
        frame["opponent_avg_points_allowed_last_10"] / frame["opponent_possessions_last_10"]
    )
    frame["opponent_def_rating_last_10"] = (
        frame["opponent_def_rating_last_10"]
        .replace([float("inf"), float("-inf")], pd.NA)
        .fillna(frame["opponent_def_rating_last_10"].mean())
        .fillna(115.0)
    )

    for column in FEATURE_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA

    return frame.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN]).reset_index(drop=True)


def time_split(
    df: pd.DataFrame, test_ratio: float = 0.3
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split chronologically to mimic forward prediction."""
    ordered = df.sort_values("game_date").reset_index(drop=True)
    cutoff = max(1, int(len(ordered) * (1 - test_ratio)))
    return ordered.iloc[:cutoff].copy(), ordered.iloc[cutoff:].copy()
