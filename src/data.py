"""Data loading and validation for the Prop-Porter experiment."""

from __future__ import annotations

import logging
import os
import warnings
from datetime import date

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "game_id",
    "game_date",
    "player_id",
    "player_name",
    "team_id",
    "opponent_team_id",
    "home_flag",
    "points",
    "minutes",
    "fga",
]

OPTIONAL_COLUMNS = ["usage", "ts", "team_pace", "opp_pace", "opp_def_rating"]
OPTIONAL_COLUMNS += [
    "team_fga",
    "team_oreb",
    "team_tov",
    "team_fta",
    "points_allowed",
    "opponent_fga",
    "opponent_oreb",
    "opponent_tov",
    "opponent_fta",
]

GAME_LOGS_SQL = """
    WITH game_opponents AS (
        SELECT
            g1.game_id,
            g1.team_id,
            g2.team_id AS opponent_team_id,
            g2.points AS opponent_points,
            g2.fga AS opponent_fga,
            g2.oreb AS opponent_oreb,
            g2.tov AS opponent_tov,
            g2.fta AS opponent_fta
        FROM games g1
        JOIN games g2 ON g1.game_id = g2.game_id AND g1.team_id != g2.team_id
    )
    SELECT pgs.game_id, g.game_date, pgs.player_id, p.full_name AS player_name,
           pgs.team_id, go.opponent_team_id, g.is_home AS home_flag,
           pgs.points, pgs.minutes, pgs.fga,
           g.fga AS team_fga,
           g.oreb AS team_oreb,
           g.tov AS team_tov,
           g.fta AS team_fta,
           go.opponent_points AS points_allowed,
           go.opponent_fga,
           go.opponent_oreb,
           go.opponent_tov,
           go.opponent_fta,
           pgs.fgm, pgs.fg3m, pgs.fg3a, pgs.ftm, pgs.fta,
           pgs.oreb, pgs.dreb, pgs.rebounds, pgs.assists,
           pgs.steals, pgs.blocks, pgs.turnovers, pgs.starter,
           g.season_id
    FROM player_game_stats pgs
    JOIN games g ON pgs.game_id = g.game_id AND pgs.team_id = g.team_id
    JOIN players p ON pgs.player_id = p.id
    JOIN game_opponents go ON pgs.game_id = go.game_id AND pgs.team_id = go.team_id
    WHERE pgs.minutes > 0
      AND g.game_date >= %(start_date)s AND g.game_date <= %(end_date)s
    ORDER BY pgs.player_id, g.game_date
"""


def _season_str_to_id(season_str: str) -> int:
    """Convert '2023-24' to numeric season_id 22023 used by the NBA API."""
    return 20000 + int(season_str.strip()[:4])


def get_db_connection():
    """Return a psycopg2 connection using environment variables."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )


def _default_start_date() -> str:
    env_val = os.getenv("DATA_START_DATE")
    if env_val:
        return env_val
    today = date.today()
    return f"{today.year - 3}-10-01"


def _default_end_date() -> str:
    env_val = os.getenv("DATA_END_DATE")
    if env_val:
        return env_val
    return date.today().isoformat()


def load_game_logs_from_db(
    start_date=None,
    end_date=None,
    seasons=None,
    conn=None,
):
    """Load game logs from Postgres."""
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()

    try:
        seasons = seasons or os.getenv("DATA_SEASONS")
        if seasons:
            season_list = [_season_str_to_id(s) for s in seasons.split(",")]
            season_sql = """
                WITH game_opponents AS (
                    SELECT
                        g1.game_id,
                        g1.team_id,
                        g2.team_id AS opponent_team_id,
                        g2.points AS opponent_points,
                        g2.fga AS opponent_fga,
                        g2.oreb AS opponent_oreb,
                        g2.tov AS opponent_tov,
                        g2.fta AS opponent_fta
                    FROM games g1
                    JOIN games g2 ON g1.game_id = g2.game_id
                                 AND g1.team_id != g2.team_id
                )
                SELECT pgs.game_id, g.game_date, pgs.player_id,
                       p.full_name AS player_name,
                       pgs.team_id, go.opponent_team_id,
                       g.is_home AS home_flag,
                       pgs.points, pgs.minutes, pgs.fga,
                       g.fga AS team_fga,
                       g.oreb AS team_oreb,
                       g.tov AS team_tov,
                       g.fta AS team_fta,
                       go.opponent_points AS points_allowed,
                       go.opponent_fga,
                       go.opponent_oreb,
                       go.opponent_tov,
                       go.opponent_fta,
                       pgs.fgm, pgs.fg3m, pgs.fg3a, pgs.ftm, pgs.fta,
                       pgs.oreb, pgs.dreb, pgs.rebounds, pgs.assists,
                       pgs.steals, pgs.blocks, pgs.turnovers, pgs.starter,
                       g.season_id
                FROM player_game_stats pgs
                JOIN games g ON pgs.game_id = g.game_id
                            AND pgs.team_id = g.team_id
                JOIN players p ON pgs.player_id = p.id
                JOIN game_opponents go ON pgs.game_id = go.game_id
                                      AND pgs.team_id = go.team_id
                WHERE pgs.minutes > 0
                  AND g.season_id = ANY(%(seasons)s)
                ORDER BY pgs.player_id, g.game_date
            """
            df = pd.read_sql_query(season_sql, conn, params={"seasons": season_list})
        else:
            start_date = start_date or _default_start_date()
            end_date = end_date or _default_end_date()
            df = pd.read_sql_query(
                GAME_LOGS_SQL,
                conn,
                params={"start_date": start_date, "end_date": end_date},
            )
    finally:
        if own_conn:
            conn.close()

    logger.info("Loaded %d rows from database", len(df))
    return df


def load_game_logs_from_csv(csv_path=None):
    """Load game logs from a CSV file."""
    if csv_path is None:
        csv_path = os.path.join("data", "raw", "sample_game_logs.csv")

    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows from %s", len(df), csv_path)
    return df


def load_game_logs(source="auto", **kwargs):
    """Unified entry point for loading game logs."""
    csv_path = kwargs.pop("csv_path", None)
    if source == "db":
        return load_game_logs_from_db(**kwargs)
    if source == "csv":
        return load_game_logs_from_csv(csv_path=csv_path)
    if source == "auto":
        try:
            return load_game_logs_from_db(**kwargs)
        except Exception as exc:
            warnings.warn(
                f"DB connection failed ({exc}), falling back to CSV",
                stacklevel=2,
            )
            return load_game_logs_from_csv(csv_path=csv_path)
    raise ValueError(f"Unknown source: {source!r}. Use 'auto', 'db', or 'csv'.")


def validate_columns(df):
    """Check required columns, add missing optional columns, coerce types."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    df["game_date"] = pd.to_datetime(df["game_date"])
    df["home_flag"] = df["home_flag"].astype(bool)
    df["player_id"] = df["player_id"].astype("int64")
    return df


def validate_no_duplicates(df):
    """Assert no duplicate (player_id, game_id) rows."""
    dupes = df.duplicated(subset=["player_id", "game_id"], keep=False)
    if dupes.any():
        sample = df.loc[dupes, ["player_id", "game_id"]].head(10)
        raise ValueError(
            f"Found {dupes.sum()} duplicate (player_id, game_id) rows. "
            f"Sample:\n{sample}"
        )


def validate_no_nulls(df):
    """Assert no null player_id or game_date values."""
    null_player = df["player_id"].isna().sum()
    null_date = df["game_date"].isna().sum()
    if null_player or null_date:
        raise ValueError(
            f"Null values found - player_id: {null_player}, game_date: {null_date}"
        )


def validate_game_logs(df):
    """Run all validations and return the validated DataFrame."""
    df = validate_columns(df)
    validate_no_duplicates(df)
    validate_no_nulls(df)
    return df
