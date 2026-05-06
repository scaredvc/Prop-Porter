"""CLI for predicting a selected player's points safely."""

from __future__ import annotations

import argparse
import os
import sys

from src.predictor import PredictionInputError, predict_for_player


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Predict points for a selected NBA player from the saved Prop-Porter model."
    )
    parser.add_argument(
        "--player",
        required=True,
        help="Player name, case-insensitive. Example: --player \"Stephen Curry\"",
    )
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
        "--model",
        default="player_points_predictor.pkl",
        help="Path to the saved model artifact.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = predict_for_player(
            player_name=args.player,
            source=args.source,
            csv_path=args.csv if args.source in {"auto", "csv"} else None,
            model_path=args.model,
        )
    except PredictionInputError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    print(f"Player: {result.player_name}")
    print(f"Game date: {result.game_date}")
    print(f"Actual points: {result.actual_points:.1f}")
    print(f"Predicted points: {result.predicted_points:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
