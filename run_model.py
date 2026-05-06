"""Simple CLI for running the saved Prop-Porter model."""

from __future__ import annotations

import argparse
import os

import joblib

from src.data import load_game_logs, validate_game_logs
from src.features import build_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the saved Prop-Porter model.")
    parser.add_argument(
        "--csv",
        default="data/raw/sample_game_logs.csv",
        help="Fallback CSV path if the database source is unavailable.",
    )
    parser.add_argument(
        "--source",
        default=os.getenv("DATA_SOURCE", "auto"),
        choices=["auto", "db", "csv"],
        help="Data source to score from. Default prefers DB and falls back to CSV.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=5,
        help="Number of scored rows to print.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact = joblib.load("player_points_predictor.pkl")
    model = artifact["model"]
    features = artifact["features"]

    kwargs = {"csv_path": args.csv} if args.source in {"auto", "csv"} and args.csv else {}
    raw = load_game_logs(source=args.source, **kwargs)
    featured = build_features(validate_game_logs(raw))
    scored = featured[["game_date", "player_name", "points"]].copy()
    scored["predicted_points"] = model.predict(featured[features])

    print("Features:", ", ".join(features))
    print()
    print(scored.tail(args.rows).to_string(index=False))


if __name__ == "__main__":
    main()
