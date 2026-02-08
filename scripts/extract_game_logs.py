#!/usr/bin/env python
"""CLI tool to extract game logs from the database and save to CSV.

Usage:
    python scripts/extract_game_logs.py --start-date 2022-10-01 --end-date 2025-04-15
    python scripts/extract_game_logs.py --seasons 2023-24,2024-25
    python scripts/extract_game_logs.py  # uses env-var / default date range
"""

import argparse
import os
import sys

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
    args = parser.parse_args()

    print("Extracting game logs from database...")
    df = load_game_logs_from_db(
        start_date=args.start_date,
        end_date=args.end_date,
        seasons=args.seasons,
    )

    print("Validating...")
    df = validate_game_logs(df)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Saved {len(df)} rows to {args.output}")

    # Summary stats
    print("\n--- Summary ---")
    print(f"  Rows:           {len(df)}")
    print(f"  Date range:     {df['game_date'].min().date()} to {df['game_date'].max().date()}")
    print(f"  Unique players: {df['player_id'].nunique()}")
    print(f"  Unique games:   {df['game_id'].nunique()}")


if __name__ == "__main__":
    main()
