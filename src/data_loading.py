"""Data loading and validation for game logs.

Extracts player game logs from Postgres or CSV, validates schema
integrity, and returns a clean DataFrame for downstream feature
engineering and model training.
"""

import logging
import os
import warnings
from datetime import date, datetime

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

GAME_LOGS_SQL = """
    WITH game_opponents AS (
        SELECT g1.game_id, g1.team_id,
               g2.team_id AS opponent_team_id
        FROM games g1
        JOIN games g2 ON g1.game_id = g2.game_id AND g1.team_id != g2.team_id
    )
    SELECT pgs.game_id, g.game_date, pgs.player_id, p.full_name AS player_name,
           pgs.team_id, go.opponent_team_id, g.is_home AS home_flag,
           pgs.points, pgs.minutes, pgs.fga,
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
    """Return DATA_START_DATE env var or ~3 seasons back (Oct 1 of year-3)."""
    env_val = os.getenv("DATA_START_DATE")
    if env_val:
        return env_val
    today = date.today()
    return f"{today.year - 3}-10-01"


def _default_end_date() -> str:
    """Return DATA_END_DATE env var or today."""
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
    """Load game logs from Postgres.

    Parameters
    ----------
    start_date : str, optional
        Earliest game date (YYYY-MM-DD). Falls back to DATA_START_DATE env
        var, then ~3 seasons back.
    end_date : str, optional
        Latest game date (YYYY-MM-DD). Falls back to DATA_END_DATE env var,
        then today.
    seasons : str, optional
        Comma-separated season IDs (e.g. "2023-24,2024-25"). Falls back to
        DATA_SEASONS env var. When provided, overrides date range filtering.
    conn : psycopg2 connection, optional
        Existing connection to reuse. A new one is created if not provided.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()

    try:
        seasons = seasons or os.getenv("DATA_SEASONS")
        if seasons:
            season_list = [s.strip() for s in seasons.split(",")]
            season_sql = """
                WITH game_opponents AS (
                    SELECT g1.game_id, g1.team_id,
                           g2.team_id AS opponent_team_id
                    FROM games g1
                    JOIN games g2 ON g1.game_id = g2.game_id
                                 AND g1.team_id != g2.team_id
                )
                SELECT pgs.game_id, g.game_date, pgs.player_id,
                       p.full_name AS player_name,
                       pgs.team_id, go.opponent_team_id,
                       g.is_home AS home_flag,
                       pgs.points, pgs.minutes, pgs.fga,
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
    """Load game logs from a CSV file.

    Parameters
    ----------
    csv_path : str, optional
        Path to CSV file. Defaults to ``data/raw/game_logs.csv``.
    """
    if csv_path is None:
        csv_path = os.path.join("data", "raw", "game_logs.csv")

    df = pd.read_csv(csv_path)
    logger.info("Loaded %d rows from %s", len(df), csv_path)
    return df


def load_game_logs(source="auto", **kwargs):
    """Unified entry point for loading game logs.

    Parameters
    ----------
    source : str
        One of ``"auto"``, ``"db"``, or ``"csv"``.
        ``"auto"`` tries DB first, falls back to CSV with a warning.
    **kwargs
        Forwarded to the underlying loader (``start_date``, ``end_date``,
        ``seasons``, ``conn``, ``csv_path``).
    """
    if source == "db":
        return load_game_logs_from_db(**kwargs)
    if source == "csv":
        return load_game_logs_from_csv(**kwargs)
    if source == "auto":
        try:
            return load_game_logs_from_db(**kwargs)
        except Exception as exc:
            warnings.warn(
                f"DB connection failed ({exc}), falling back to CSV",
                stacklevel=2,
            )
            return load_game_logs_from_csv(**kwargs)
    raise ValueError(f"Unknown source: {source!r}. Use 'auto', 'db', or 'csv'.")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_columns(df):
    """Check required columns, add missing optional columns, coerce types.

    Returns the validated (and possibly modified) DataFrame.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    # Type coercions
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
            f"Null values found — player_id: {null_player}, game_date: {null_date}"
        )


def validate_game_logs(df):
    """Run all validations and return the validated DataFrame."""
    df = validate_columns(df)
    validate_no_duplicates(df)
    validate_no_nulls(df)
    return df
