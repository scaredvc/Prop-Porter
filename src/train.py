"""Run the Prop-Porter baseline experiment end-to-end."""

from __future__ import annotations

import os
from pathlib import Path

import joblib
import matplotlib

from src.data import load_game_logs, validate_game_logs
from src.features import FEATURE_COLUMNS, build_features, time_split
from src.model import train_and_evaluate

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo"
MODEL_PATH = ROOT / "models" / "baseline_random_forest.joblib"
LEGACY_MODEL_PATH = ROOT / "player_points_predictor.pkl"
PLOT_PATH = DEMO_DIR / "prediction_vs_actual.png"


def save_plot(predictions):
    """Save a simple prediction-vs-actual chart for the README."""
    plot_df = predictions.reset_index(drop=True).copy()
    x = range(len(plot_df))

    plt.figure(figsize=(10, 5))
    plt.plot(x, plot_df["points"], marker="o", linewidth=2, label="Actual")
    plt.plot(
        x,
        plot_df["predicted_points"],
        marker="o",
        linewidth=2,
        linestyle="--",
        label="Predicted",
    )
    plt.xticks(x, plot_df["player_name"], rotation=45, ha="right")
    plt.ylabel("Points")
    plt.xlabel("Held-out player games")
    plt.title("Prop-Porter: Predicted vs Actual Points")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT_PATH, dpi=160)
    plt.close()


def main():
    source = os.getenv("DATA_SOURCE", "auto")
    raw = load_game_logs(source=source)
    validated = validate_game_logs(raw)
    featured = build_features(validated)
    train_df, test_df = time_split(featured, test_ratio=0.3)
    result = train_and_evaluate(train_df, test_df)

    saved_plot = False
    try:
        save_plot(result.predictions)
        saved_plot = True
    except PermissionError:
        saved_plot = False

    saved_model = False
    saved_legacy_model = False
    try:
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(result.model, MODEL_PATH)
        saved_model = True
    except PermissionError:
        saved_model = False

    try:
        joblib.dump(
            {"model": result.model, "features": FEATURE_COLUMNS},
            LEGACY_MODEL_PATH,
        )
        saved_legacy_model = True
    except PermissionError:
        saved_legacy_model = False

    print(f"Rows used: {len(featured)}")
    print(f"Train rows: {len(train_df)}")
    print(f"Test rows: {len(test_df)}")
    print(f"MAE: {result.mae:.2f}")
    print(f"R^2: {result.r2:.2f}")
    if saved_plot:
        print(f"Saved demo plot: {PLOT_PATH}")
    else:
        print("Saved demo plot: skipped (permission denied in demo directory)")
    if saved_model:
        print(f"Saved model: {MODEL_PATH}")
    else:
        print("Saved model: skipped (permission denied in models directory)")
    if saved_legacy_model:
        print(f"Saved legacy model: {LEGACY_MODEL_PATH}")
    else:
        print("Saved legacy model: skipped (permission denied in repo root)")


if __name__ == "__main__":
    main()
