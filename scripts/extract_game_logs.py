#!/usr/bin/env python
"""CLI tool to extract game logs from the database and save to CSV and Parquet.

Usage:
    python scripts/extract_game_logs.py --start-date 2022-10-01 --end-date 2025-04-15
    python scripts/extract_game_logs.py --seasons 2023-24,2024-25
    python scripts/extract_game_logs.py  # uses env-var / default date range
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

# Ensure project root is on sys.path when run as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data_loading import load_game_logs_from_db, validate_game_logs


def main():
    parser = argparse.ArgumentParser(
        description="Extract player game logs from the database."
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Earliest game date (YYYY-MM-DD). Defaults to DATA_START_DATE env var.",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Latest game date (YYYY-MM-DD). Defaults to DATA_END_DATE env var.",
    )
    parser.add_argument(
        "--seasons",
        default=None,
        help="Comma-separated season IDs, e.g. '2023-24,2024-25'. Overrides date range.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("data", "raw", "game_logs.csv"),
        help="Output CSV path (default: data/raw/game_logs.csv).",
    )
    parser.add_argument(
        "--parquet-output",
        default=os.path.join("data", "processed", "training_source.parquet"),
        help="Output Parquet path (default: data/processed/training_source.parquet).",
    )
    args = parser.parse_args()

    print("Extracting game logs from database...")
    df = load_game_logs_from_db(
        start_date=args.start_date,
        end_date=args.end_date,
        seasons=args.seasons,
    )

    print("Validating...")
    df = validate_game_logs(df)

    # Save CSV
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Saved {len(df)} rows to {args.output}")

    # Save Parquet
    os.makedirs(os.path.dirname(args.parquet_output), exist_ok=True)
    df.to_parquet(args.parquet_output, index=False, engine="pyarrow")
    print(f"Saved {len(df)} rows to {args.parquet_output}")

    # Run metadata
    run_id = uuid.uuid4()
    extracted_at = datetime.now(timezone.utc)
    row_count = len(df)
    date_min = df["game_date"].min().date() if row_count else None
    date_max = df["game_date"].max().date() if row_count else None
    unique_players = df["player_id"].nunique() if row_count else 0
    unique_games = df["game_id"].nunique() if row_count else 0

    # Print metadata summary
    print("\n--- Run Metadata ---")
    print(f"  Run ID:         {run_id}")
    print(f"  Extracted at:   {extracted_at.isoformat()}")
    print(f"  Rows:           {row_count}")
    print(f"  Date range:     {date_min} to {date_max}")
    print(f"  Unique players: {unique_players}")
    print(f"  Unique games:   {unique_games}")

    # Optionally persist metadata to data_extraction_runs table
    try:
        from src.data_loading import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO data_extraction_runs
                (run_id, extracted_at, row_count, date_min, date_max, unique_players, unique_games, params)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id) DO NOTHING
            """,
            (
                str(run_id),
                extracted_at,
                row_count,
                date_min,
                date_max,
                unique_players,
                unique_games,
                '{"source": "extract_game_logs.py"}',
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        print("  Metadata saved to data_extraction_runs table.")
    except Exception as e:
        print(f"  (Could not save metadata to DB: {e})")


if __name__ == "__main__":
    main()
