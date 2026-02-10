#!/usr/bin/env python
"""CLI tool to build player features from game logs and save to CSV/Parquet.

Usage:
    python scripts/build_features.py
    python scripts/build_features.py --input data/raw/game_logs.csv --min-periods 3
"""

import argparse
import os
import sys

# Ensure project root is on sys.path when run as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.data_loading import load_game_logs_from_csv, validate_game_logs
from src.features import build_player_features


def main():
    parser = argparse.ArgumentParser(
        description="Build player features from game logs."
    )
    parser.add_argument(
        "--input",
        default=os.path.join("data", "raw", "game_logs.csv"),
        help="Input CSV path (default: data/raw/game_logs.csv).",
    )
    parser.add_argument(
        "--output-csv",
        default=os.path.join("data", "processed", "features.csv"),
        help="Output CSV path (default: data/processed/features.csv).",
    )
    parser.add_argument(
        "--output-parquet",
        default=os.path.join("data", "processed", "features.parquet"),
        help="Output Parquet path (default: data/processed/features.parquet).",
    )
    parser.add_argument(
        "--min-periods",
        type=int,
        default=1,
        help="Minimum observations in rolling window (default: 1).",
    )
    args = parser.parse_args()

    print(f"Loading game logs from {args.input}...")
    df = load_game_logs_from_csv(csv_path=args.input)

    print("Validating...")
    df = validate_game_logs(df)

    print(f"Building features (min_periods={args.min_periods})...")
    df_features = build_player_features(df, min_periods=args.min_periods)

    # Save CSV
    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
    df_features.to_csv(args.output_csv, index=False)
    print(f"Saved {len(df_features)} rows to {args.output_csv}")

    # Save Parquet
    os.makedirs(os.path.dirname(args.output_parquet), exist_ok=True)
    df_features.to_parquet(args.output_parquet, index=False, engine="pyarrow")
    print(f"Saved {len(df_features)} rows to {args.output_parquet}")

    # Summary
    feature_cols = [c for c in df_features.columns if c not in df.columns]
    print(f"\nNew feature columns ({len(feature_cols)}): {feature_cols}")
    print(f"Total columns: {len(df_features.columns)}")


if __name__ == "__main__":
    main()
