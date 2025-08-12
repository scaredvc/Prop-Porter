import os
from typing import Tuple, List

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
import joblib

load_dotenv()

def get_db_connection():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    return conn

def create_training_dataframe() -> pd.DataFrame:

    print("Connecting to the database...")
    conn = get_db_connection()

    sql_query = """
        WITH game_opponents AS (
            SELECT
                g1.game_id,
                g1.team_id,
                g2.team_id AS opponent_team_id,
                g2.points AS opponent_points,
                -- Opponent box score for pace estimation
                g2.fga  AS opponent_fga,
                g2.oreb AS opponent_oreb,
                g2.tov  AS opponent_tov,
                g2.fta  AS opponent_fta
            FROM games g1
            JOIN games g2 ON g1.game_id = g2.game_id AND g1.team_id != g2.team_id
        )
        SELECT 
            pgs.player_id,
            pgs.game_id,
            pgs.team_id,
            pgs.minutes,
            pgs.points AS player_points,
            g.game_date,
            -- Player team box score for pace estimation
            g.fga  AS team_fga,
            g.oreb AS team_oreb,
            g.tov  AS team_tov,
            g.fta  AS team_fta,
            go.opponent_team_id,
            go.opponent_points AS points_allowed,
            go.opponent_fga,
            go.opponent_oreb,
            go.opponent_tov,
            go.opponent_fta
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id = g.game_id AND pgs.team_id = g.team_id
        JOIN game_opponents go ON pgs.game_id = go.game_id AND pgs.team_id = go.team_id
        WHERE pgs.minutes > 0
        ORDER BY pgs.player_id, g.game_date
    """

    training_df = pd.read_sql_query(sql_query, conn)

    print(f"Successfully created DataFrame with {len(training_df)} rows.")
    print("Here are the first 5 rows:")
    print(training_df.head())

    conn.close()

    # Ensure types
    training_df["game_date"] = pd.to_datetime(training_df["game_date"])  # safe if already datetime
    # Guard against missing minutes
    if "minutes" not in training_df.columns:
        training_df["minutes"] = np.nan

    return training_df

def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(by=["player_id", "game_date"]).copy()

    # Rolling windows and exponentially weighted means
    def rolling_mean(group: pd.Series, window: int) -> pd.Series:
        return group.rolling(window=window, min_periods=1).mean().shift(1)

    def ewm_mean(group: pd.Series, span: int) -> pd.Series:
        return group.ewm(span=span, adjust=False).mean().shift(1)

    # Player form features
    for w in (5, 10):
        df[f"player_points_last_{w}"] = df.groupby("player_id")["player_points"].transform(lambda s: rolling_mean(s, w))
    for span in (5, 10):
        df[f"player_points_ewm_span_{span}"] = df.groupby("player_id")["player_points"].transform(lambda s: ewm_mean(s, span))

    # Minutes and efficiency
    if "minutes" in df.columns:
        df["points_per_minute"] = df["player_points"] / df["minutes"].replace({0: np.nan})
        for w in (5, 10):
            df[f"ppm_last_{w}"] = df.groupby("player_id")["points_per_minute"].transform(lambda s: rolling_mean(s, w))
        for span in (5, 10):
            df[f"ppm_ewm_span_{span}"] = df.groupby("player_id")["points_per_minute"].transform(lambda s: ewm_mean(s, span))

    # Days rest
    df["prev_game_date"] = df.groupby("player_id")["game_date"].shift(1)
    df["days_rest"] = (df["game_date"] - df["prev_game_date"]).dt.days.fillna(7).clip(lower=0, upper=10)
    df.drop(columns=["prev_game_date"], inplace=True)

    # Opponent defensive strength
    # Build team-level frame to compute opponent features without leakage
    team_cols = [
        "team_id", "game_id", "game_date", "points_allowed",
        "team_fga", "team_oreb", "team_tov", "team_fta",
    ]
    team_level = (
        df[team_cols]
        .drop_duplicates(subset=["team_id", "game_id"])  # one row per team-game
        .sort_values(["team_id", "game_date"])  # ensure order
        .copy()
    )
    # Possessions proxy for team
    team_level["team_possessions"] = (
        team_level["team_fga"].astype(float)
        - team_level["team_oreb"].astype(float)
        + team_level["team_tov"].astype(float)
        + 0.44 * team_level["team_fta"].astype(float)
    )
    # Rolling defense and pace for each team (shifted to avoid leakage)
    team_level["team_points_allowed_rm10"] = (
        team_level.groupby("team_id")["points_allowed"].transform(lambda s: s.rolling(window=10, min_periods=1).mean().shift(1))
    )
    team_level["team_possessions_rm10"] = (
        team_level.groupby("team_id")["team_possessions"].transform(lambda s: s.rolling(window=10, min_periods=1).mean().shift(1))
    )

    # Opponent features: map opponent_team_id to its rolling series at this game_id
    opp_features = team_level[[
        "team_id", "game_id", "team_points_allowed_rm10", "team_possessions_rm10"
    ]].rename(columns={
        "team_id": "opponent_team_id",
        "team_points_allowed_rm10": "opponent_avg_points_allowed_last_10",
        "team_possessions_rm10": "opponent_possessions_last_10",
    })
    df = df.merge(
        opp_features,
        on=["opponent_team_id", "game_id"],
        how="left",
    )

    # Fallbacks for missing opponent features
    # Per-opponent historical means, then global means
    per_opp_def_mean = df.groupby("opponent_team_id")["points_allowed"].transform("mean")
    global_def_mean = df["points_allowed"].mean()
    df["opponent_avg_points_allowed_last_10"].fillna(per_opp_def_mean, inplace=True)
    df["opponent_avg_points_allowed_last_10"].fillna(global_def_mean, inplace=True)

    # For pace, use opponent's average possessions if available; else fallback to overall mean
    # Compute opponent possessions at the game level from opponent box scores if missing
    if "opponent_possessions_last_10" not in df.columns:
        df["opponent_possessions_last_10"] = np.nan
    global_poss_mean = (
        (df["opponent_fga"].astype(float) - df["opponent_oreb"].astype(float) + df["opponent_tov"].astype(float) + 0.44 * df["opponent_fta"].astype(float))
        .mean()
    ) if {"opponent_fga", "opponent_oreb", "opponent_tov", "opponent_fta"}.issubset(df.columns) else np.nan
    df["opponent_possessions_last_10"].fillna(global_poss_mean, inplace=True)

    df = df.sort_values(by=["player_id", "game_date"]).reset_index(drop=True)
    print("feature engineering complete")
    return df


def time_based_split(df: pd.DataFrame, test_size: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if "game_date" not in df.columns:
        raise ValueError("game_date column is required for time-based split")
    df_sorted = df.sort_values("game_date").reset_index(drop=True)
    cutoff_index = int(len(df_sorted) * (1 - test_size))
    return df_sorted.iloc[:cutoff_index].copy(), df_sorted.iloc[cutoff_index:].copy()

def train_model(df: pd.DataFrame):
    candidate_features: List[str] = [
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
    ]
    target = "player_points"

    # Keep only features that exist
    features = [f for f in candidate_features if f in df.columns]
    if not features:
        raise ValueError("No valid features available for training.")

    # Drop rows with missing in used columns
    df_clean = df.dropna(subset=features + [target]).copy()

    # Time-based split
    train_df, test_df = time_based_split(df_clean, test_size=0.2)
    X_train, y_train = train_df[features], train_df[target]
    X_test, y_test = test_df[features], test_df[target]

    # Prefer LightGBM if available
    model = None
    try:
        from lightgbm import LGBMRegressor  # type: ignore
        model = LGBMRegressor(
            n_estimators=1000,
            learning_rate=0.03,
            max_depth=-1,
            subsample=0.9,
            colsample_bytree=0.9,
            random_state=42,
        )
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)], eval_metric="l1", verbose=False)
    except Exception:
        model = RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    print(f"Features used: {features}")
    print(f"Test MAE: {mae:.2f}")

    model_filename = "player_points_predictor.pkl"
    joblib.dump({"model": model, "features": features}, model_filename)
    print(f"Model saved to {model_filename}")
    return model

if __name__ == '__main__':
    master_df = create_training_dataframe()
    featured_df = feature_engineering(master_df)
    trained_model = train_model(featured_df)