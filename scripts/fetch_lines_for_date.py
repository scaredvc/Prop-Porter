#!/usr/bin/env python
"""CLI tool to fetch NBA sportsbook player points lines via Perplexity API.

Usage:
    python scripts/fetch_lines_for_date.py
    python scripts/fetch_lines_for_date.py --date 2025-01-15
"""

import argparse
import os
import sys
from datetime import datetime

import pytz

# Ensure project root is on sys.path when run as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.grok_client import fetch_lines_for_date


def _today_et() -> str:
    """Return today's date in Eastern Time as YYYY-MM-DD string."""
    et = pytz.timezone("America/New_York")
    return datetime.now(et).strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch NBA sportsbook player points lines via Perplexity API."
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Target date in YYYY-MM-DD format (default: today in ET).",
    )
    args = parser.parse_args()

    date_str = args.date or _today_et()

    print(f"Fetching sportsbook lines for {date_str}...")
    df = fetch_lines_for_date(date_str)

    # Save to data/lines/{date}.csv
    output_dir = os.path.join("data", "lines")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{date_str}.csv")
    df.to_csv(output_path, index=False)

    # Summary
    print(f"Saved {len(df)} rows to {output_path}")
    if len(df) > 0:
        unique_teams = df["team"].nunique()
        print(f"  Date: {date_str}")
        print(f"  Unique teams: {unique_teams}")
        print(f"  Players: {df['player_name'].nunique()}")
    else:
        print("  No lines returned.")


if __name__ == "__main__":
    main()
