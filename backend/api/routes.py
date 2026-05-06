from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import traceback
from flask import jsonify, request

from . import app
from .utils import get_db_connection

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "player_points_predictor.pkl"

try:
    model_artifact = joblib.load(MODEL_PATH)
    print("Model loaded successfully")
except FileNotFoundError:
    print("Model not found")
    model_artifact = None


def _rolling_mean(values: list[float], window: int) -> float:
    series = pd.Series(values, dtype="float64")
    return float(series.tail(window).mean()) if not series.empty else 0.0


def _ewm_mean(values: list[float], span: int) -> float:
    series = pd.Series(values, dtype="float64")
    return float(series.ewm(span=span, adjust=False).mean().iloc[-1]) if not series.empty else 0.0


def _fetch_recent_player_games(cur, player_id: int, limit: int = 10) -> pd.DataFrame:
    cur.execute(
        """
        SELECT
            g.game_date,
            CASE
                WHEN g.matchup LIKE '%%vs.%%' THEN TRUE
                WHEN g.matchup LIKE '%%@%%' THEN FALSE
                ELSE NULL
            END AS is_home,
            pgs.points,
            pgs.minutes,
            pgs.fga
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id = g.game_id AND pgs.team_id = g.team_id
        WHERE pgs.player_id = %s
          AND pgs.minutes > 0
        ORDER BY g.game_date DESC
        LIMIT %s;
        """,
        (player_id, limit),
    )
    rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=["game_date", "is_home", "points", "minutes", "fga"])
    frame = pd.DataFrame(rows, columns=["game_date", "is_home", "points", "minutes", "fga"])
    return frame.sort_values("game_date").reset_index(drop=True)


def _fetch_recent_opponent_games(cur, opponent_team_id: int, limit: int = 10) -> pd.DataFrame:
    cur.execute(
        """
        WITH game_opponent AS (
            SELECT
                g1.game_id,
                g1.team_id,
                g1.game_date,
                g2.points AS points_allowed,
                g1.fga,
                g1.oreb,
                g1.tov,
                g1.fta
            FROM games g1
            JOIN games g2 ON g1.game_id = g2.game_id AND g1.team_id != g2.team_id
        )
        SELECT game_date, points_allowed, fga, oreb, tov, fta
        FROM game_opponent
        WHERE team_id = %s
        ORDER BY game_date DESC
        LIMIT %s;
        """,
        (opponent_team_id, limit),
    )
    rows = cur.fetchall()
    if not rows:
        return pd.DataFrame(columns=["game_date", "points_allowed", "fga", "oreb", "tov", "fta"])
    frame = pd.DataFrame(
        rows,
        columns=["game_date", "points_allowed", "fga", "oreb", "tov", "fta"],
    )
    return frame.sort_values("game_date").reset_index(drop=True)


def _build_feature_frame(
    cur,
    player_id: int,
    opponent_team_id: int | None,
    is_home: int,
) -> pd.DataFrame:
    player_games = _fetch_recent_player_games(cur, player_id)
    if player_games.empty:
        raise ValueError("No recent games found for that player.")

    opponent_games = pd.DataFrame()
    if opponent_team_id is not None:
        opponent_games = _fetch_recent_opponent_games(cur, opponent_team_id)

    points = player_games["points"].astype(float).tolist()
    minutes = player_games["minutes"].astype(float).replace({0: np.nan}).tolist()
    fga = player_games["fga"].astype(float).tolist()
    ppm = (
        player_games["points"].astype(float)
        / player_games["minutes"].astype(float).replace({0: np.nan})
    ).replace([np.inf, -np.inf], np.nan)

    last_game_date = pd.Timestamp(player_games["game_date"].iloc[-1]).tz_localize(None)
    today = pd.Timestamp.now(tz=None).normalize()
    days_rest = int((today - last_game_date).days)
    days_rest = max(0, min(days_rest, 10))

    opponent_avg_points_allowed_last_10 = 115.0
    opponent_possessions_last_10 = 100.0
    opponent_def_rating_last_10 = 115.0
    if not opponent_games.empty:
        points_allowed = opponent_games["points_allowed"].astype(float)
        possessions = (
            opponent_games["fga"].astype(float)
            - opponent_games["oreb"].astype(float)
            + opponent_games["tov"].astype(float)
            + 0.44 * opponent_games["fta"].astype(float)
        )
        opponent_avg_points_allowed_last_10 = float(points_allowed.mean())
        if possessions.notna().any():
            opponent_possessions_last_10 = float(possessions.mean())
            if opponent_possessions_last_10:
                opponent_def_rating_last_10 = 100.0 * (
                    opponent_avg_points_allowed_last_10 / opponent_possessions_last_10
                )

    return pd.DataFrame(
        {
            "player_points_last_5": [_rolling_mean(points, 5)],
            "player_points_last_10": [_rolling_mean(points, 10)],
            "player_points_ewm_span_5": [_ewm_mean(points, 5)],
            "player_points_ewm_span_10": [_ewm_mean(points, 10)],
            "ppm_last_5": [float(ppm.tail(5).mean()) if ppm.notna().any() else 0.0],
            "ppm_last_10": [float(ppm.tail(10).mean()) if ppm.notna().any() else 0.0],
            "ppm_ewm_span_5": [float(ppm.ewm(span=5, adjust=False).mean().iloc[-1]) if ppm.notna().any() else 0.0],
            "ppm_ewm_span_10": [float(ppm.ewm(span=10, adjust=False).mean().iloc[-1]) if ppm.notna().any() else 0.0],
            "days_rest": [days_rest],
            "opponent_avg_points_allowed_last_10": [opponent_avg_points_allowed_last_10],
            "opponent_possessions_last_10": [opponent_possessions_last_10],
            "opponent_def_rating_last_10": [opponent_def_rating_last_10],
            "is_home": [int(is_home)],
            "points_last_3": [_rolling_mean(points, 3)],
            "points_last_5": [_rolling_mean(points, 5)],
            "minutes_last_3": [_rolling_mean([0.0 if pd.isna(v) else float(v) for v in minutes], 3)],
            "fga_last_3": [_rolling_mean(fga, 3)],
        }
    )


def _fetch_last_matchup_stats(cur, player_id: int, opponent_team_id: int | None) -> dict | None:
    """Return the player's latest recorded game against the selected opponent."""
    if opponent_team_id is None:
        return None

    cur.execute(
        """
        WITH game_opponents AS (
            SELECT
                g1.game_id,
                g1.team_id,
                g2.team_id AS opponent_team_id
            FROM games g1
            JOIN games g2 ON g1.game_id = g2.game_id AND g1.team_id != g2.team_id
        )
        SELECT
            g.game_date,
            pgs.points,
            pgs.minutes,
            pgs.fga
        FROM player_game_stats pgs
        JOIN games g ON pgs.game_id = g.game_id AND pgs.team_id = g.team_id
        JOIN game_opponents go ON pgs.game_id = go.game_id AND pgs.team_id = go.team_id
        WHERE pgs.player_id = %s
          AND go.opponent_team_id = %s
        ORDER BY g.game_date DESC
        LIMIT 1;
        """,
        (player_id, opponent_team_id),
    )
    row = cur.fetchone()
    if row is None:
        return None

    return {
        "game_date": pd.Timestamp(row[0]).date().isoformat(),
        "points": float(row[1]) if row[1] is not None else None,
        "minutes": float(row[2]) if row[2] is not None else None,
        "fga": float(row[3]) if row[3] is not None else None,
    }

@app.route('/api/v1/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "API is healthy"}), 200

@app.route('/api/v1/teams', methods=['GET'])
def get_teams():
    team_list = []
    conn = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
                    SELECT id, 
                        full_name, abbreviation, nickname, city, state, year_founded 
                    FROM 
                        teams 
                    ORDER BY
                        full_name;
                    """)
        result = cur.fetchall()

        if result and cur.description:
            columns = [desc[0] for desc in cur.description]
            team_list = [dict(zip(columns, row)) for row in result]

        cur.close()

    except Exception as e:
        print(e)
        team_list = []

    finally:
        if conn is not None:
            conn.close()

    return jsonify(team_list)

@app.route('/api/v1/players', methods= ['GET'])
def get_player():
    player_list = []
    conn = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
                    SELECT 
                        id, full_name, first_name, last_name, is_active
                    FROM 
                        players 
                    ORDER BY 
                        full_name
                    """)
        
        result = cur.fetchall()
        
        if result and cur.description:
            columns = [desc[0] for desc in cur.description]
            player_list = [dict(zip(columns, row)) for row in result]

        cur.close()

    except Exception as e:
        print(e)
        player_list = []

    finally:
        if conn is not None:
            conn.close()
        
        return jsonify(player_list)

@app.route("/api/v1/players/<int:player_id>/stats", methods = ["GET"])
def get_player_stats(player_id):
    
    player_stats = []
    conn = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        sql_query = ( """
            SELECT 
                id, player_id, game_id, team_id, minutes, points, 
                rebounds, assists, steals, blocks, turnovers, fgm, 
                fga, fg_pct, fg3m, fg3a, fg3_pct, ftm, fta, ft_pct
            FROM 
                player_game_stats
            WHERE 
                player_id = %s
            ORDER BY 
                game_date;
            """)
        
        cur.execute(sql_query, (player_id,))
            
        result = cur.fetchall()

        if result and cur.description:
            columns = [desc[0] for desc in cur.description]
            player_stats = [dict(zip(columns,row)) for row in result]

        cur.close()

    except Exception as e:
        print(e)
        player_stats = []

    finally: 
        if conn is not None:
            conn.close()

        return jsonify(player_stats)
    
@app.route("/api/v1/teams/<int:id>/games", methods = ["GET"])
def get_games(id):
    games = []
    conn = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        sql_query = ("""
            SELECT season_id, team_id, team_abbreviation, game_id, game_date,
                     matchup, win_loss, minutes, points, fgm, fga, fg_pct,
                     fg3m, fg3a, fg3_pct, ftm, fta, ft_pct, oreb, dreb, 
                     reb, ast, stl, blk, tov, pf, plus_minus
            FROM 
                games
            WHERE 
                team_id = %s
            ORDER BY 
                game_date;
            """)
        
        cur.execute(sql_query, (id,))
        result = cur.fetchall()

        if result and cur.description:
            columns = [desc[0] for desc in cur.description]
            games = [dict(zip(columns, row)) for row in result]

        cur.close()
        
    except Exception as e:
        print(e)
        games = []

    finally:
        if conn is not None:
            conn.close()

        return jsonify(games)
    

@app.route("/api/v1/predict", methods=['GET'])
def predict_player_points():
    if model_artifact is None:
        return jsonify({"error": "Model not loaded"}), 500
    
    player_id = request.args.get('player_id', type=int)
    opponent_team_id = request.args.get('opponent_team_id', type=int)
    is_home = request.args.get('is_home', default=0, type=int)

    if not player_id:
        return jsonify({"error": "Missing required player_id parameter"}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        feature_df = _build_feature_frame(cur, player_id, opponent_team_id, is_home)
        if isinstance(model_artifact, dict):
            model = model_artifact["model"]
            features = model_artifact["features"]
            missing = [feature for feature in features if feature not in feature_df.columns]
            if missing:
                raise ValueError(f"Prediction features missing: {missing}")
            prediction = model.predict(feature_df[features])
        else:
            prediction = model_artifact.predict(feature_df)
        predicted_points = round(prediction[0], 2)
        last_matchup = _fetch_last_matchup_stats(cur, player_id, opponent_team_id)

        return jsonify ({
            "player_id": player_id,
            "opponent_team_id": opponent_team_id,
            "is_home": int(is_home),
            "predicted_points": predicted_points,
            "last_matchup": last_matchup,
        })

    except Exception as e:
        print("Error during prediction")
        traceback.print_exc()
        return jsonify({"error": "An error occurred during prediction."}), 500
    
    finally:
        if conn:
            conn.close()
