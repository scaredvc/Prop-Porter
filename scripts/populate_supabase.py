#!/usr/bin/env python
"""Populate Supabase with player game stats from NBA API (LeagueGameLog bulk endpoint)."""

import os
import sys
import time
import random

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from nba_api.stats.endpoints import leaguegamelog

# DB config
DB_CONFIG = {
    "dbname": os.environ["DB_NAME"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "host": os.environ["DB_HOST"],
    "port": os.environ.get("DB_PORT", "5432"),
}

SEASONS = ["2022-23", "2023-24", "2024-25"]
SEASON_TYPES = ["Regular Season", "Playoffs"]

INSERT_SQL = """
    INSERT INTO player_game_stats (
        player_id, game_id, team_id, minutes, points,
        rebounds, oreb, dreb, assists, steals, blocks, turnovers,
        fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
        ftm, fta, ft_pct, starter
    ) VALUES %s
    ON CONFLICT (player_id, game_id) DO NOTHING
"""

INSERT_PLAYER_SQL = """
    INSERT INTO players(id, full_name, first_name, last_name, is_active)
    VALUES %s
    ON CONFLICT (id) DO NOTHING
"""


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def convert_min(time_str):
    if not time_str or pd.isna(time_str):
        return 0.0
    try:
        parts = str(time_str).split(":")
        if len(parts) == 2:
            return float(parts[0]) + float(parts[1]) / 60
        return float(time_str)
    except Exception:
        return 0.0


def safe_int(val, default=0):
    if pd.isna(val):
        return default
    return int(val)


def safe_float(val):
    if pd.isna(val):
        return None
    return float(val)


def fetch_known_player_ids():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM players")
    ids = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return ids


def fetch_league_game_log(season, season_type, max_retries=3):
    for attempt in range(max_retries):
        try:
            time.sleep(random.uniform(3, 5))
            result = leaguegamelog.LeagueGameLog(
                season=season,
                player_or_team_abbreviation="P",
                season_type_all_star=season_type,
                timeout=60,
            )
            df = result.get_data_frames()[0]
            return df
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
    return pd.DataFrame()


def row_to_tuple(row):
    return (
        int(row["PLAYER_ID"]),
        row["GAME_ID"],
        int(row["TEAM_ID"]),
        convert_min(row["MIN"]),
        safe_int(row["PTS"]),
        safe_int(row["REB"]),
        safe_int(row.get("OREB")),
        safe_int(row.get("DREB")),
        safe_int(row["AST"]),
        safe_int(row["STL"]),
        safe_int(row["BLK"]),
        safe_int(row["TOV"]),
        safe_int(row["FGM"]),
        safe_int(row["FGA"]),
        safe_float(row["FG_PCT"]),
        safe_int(row["FG3M"]),
        safe_int(row["FG3A"]),
        safe_float(row["FG3_PCT"]),
        safe_int(row["FTM"]),
        safe_int(row["FTA"]),
        safe_float(row["FT_PCT"]),
        False,  # starter — not available from LeagueGameLog
    )


def insert_batch(tuples, batch_size=500):
    """Insert tuples in batches with fresh connections."""
    for i in range(0, len(tuples), batch_size):
        batch = tuples[i : i + batch_size]
        conn = get_conn()
        cur = conn.cursor()
        try:
            execute_values(cur, INSERT_SQL, batch)
            conn.commit()
        finally:
            cur.close()
            conn.close()


def insert_players_batch(player_tuples):
    conn = get_conn()
    cur = conn.cursor()
    try:
        execute_values(cur, INSERT_PLAYER_SQL, player_tuples)
        conn.commit()
    finally:
        cur.close()
        conn.close()


def main():
    known_player_ids = fetch_known_player_ids()
    print(f"Known players in DB: {len(known_player_ids)}")

    new_players = {}  # pid -> name
    all_rows_for_new = []  # rows to re-process after adding players

    for season in SEASONS:
        for stype in SEASON_TYPES:
            print(f"\nFetching {stype} {season}...")
            df = fetch_league_game_log(season, stype)
            if df.empty:
                print("  Skipped (no data)")
                continue
            print(f"  Got {len(df)} rows")

            tuples_to_insert = []
            skipped = 0
            for _, row in df.iterrows():
                pid = int(row["PLAYER_ID"])
                if pid not in known_player_ids:
                    new_players[pid] = row["PLAYER_NAME"]
                    all_rows_for_new.append(row)
                    skipped += 1
                    continue
                tuples_to_insert.append(row_to_tuple(row))

            print(f"  Inserting {len(tuples_to_insert)} rows (skipped {skipped} unknown)...")
            insert_batch(tuples_to_insert)
            print(f"  Done.")

    # Add new players and insert their stats
    if new_players:
        print(f"\nAdding {len(new_players)} previously unknown players...")
        player_tuples = []
        for pid, pname in new_players.items():
            parts = pname.split(" ", 1)
            player_tuples.append((pid, pname, parts[0], parts[1] if len(parts) > 1 else "", False))
        insert_players_batch(player_tuples)
        known_player_ids.update(new_players.keys())

        # Insert their stats
        new_tuples = [row_to_tuple(row) for row in all_rows_for_new]
        print(f"  Inserting {len(new_tuples)} stats for new players...")
        insert_batch(new_tuples)
        print("  Done.")

    # Final summary
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM player_game_stats")
    pgs = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM players")
    pl = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT player_id) FROM player_game_stats")
    up = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT game_id) FROM player_game_stats")
    ug = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"\n{'='*40}")
    print(f"FINAL SUMMARY")
    print(f"{'='*40}")
    print(f"Players in DB:            {pl}")
    print(f"Player game stats rows:   {pgs}")
    print(f"Unique players with stats:{up}")
    print(f"Unique games with stats:  {ug}")


if __name__ == "__main__":
    main()
