"""Utilities for safe, case-insensitive player point predictions."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path

import joblib
import pandas as pd

from src.data import load_game_logs, validate_game_logs
from src.features import build_features


DEFAULT_MODEL_PATH = Path("player_points_predictor.pkl")
DEFAULT_CSV_PATH = Path("data/raw/sample_game_logs.csv")


class PredictionInputError(ValueError):
    """Raised when a prediction request is invalid."""


@dataclass
class PlayerPrediction:
    player_name: str
    game_date: str
    actual_points: float
    predicted_points: float


def normalize_player_name(name: str) -> str:
    """Normalize user input for case-insensitive player matching."""
    if not isinstance(name, str):
        raise PredictionInputError("Player name must be a string.")
    normalized = " ".join(name.strip().split()).casefold()
    if not normalized:
        raise PredictionInputError("Player name cannot be empty.")
    return normalized


def load_artifact(model_path: str | Path = DEFAULT_MODEL_PATH) -> dict:
    """Load and validate the saved model artifact."""
    path = Path(model_path)
    if not path.exists():
        raise PredictionInputError(f"Model file not found: {path}")

    artifact = joblib.load(path)
    if not isinstance(artifact, dict):
        raise PredictionInputError("Model artifact is invalid: expected a dict payload.")
    if "model" not in artifact or "features" not in artifact:
        raise PredictionInputError("Model artifact is invalid: missing model or features.")
    if not isinstance(artifact["features"], list) or not artifact["features"]:
        raise PredictionInputError("Model artifact is invalid: features must be a non-empty list.")
    return artifact


def load_featured_data(
    source: str = "auto",
    csv_path: str | Path = DEFAULT_CSV_PATH,
) -> pd.DataFrame:
    """Load, validate, and feature-engineer the scoring dataset."""
    kwargs: dict[str, str] = {}
    if source in {"auto", "csv"} and csv_path is not None:
        kwargs["csv_path"] = str(csv_path)
    raw = load_game_logs(source=source, **kwargs)
    validated = validate_game_logs(raw)
    featured = build_features(validated)
    if featured.empty:
        raise PredictionInputError("No usable rows were generated from the input CSV.")
    return featured


def find_latest_player_row(featured: pd.DataFrame, player_name: str) -> pd.Series:
    """Return the most recent usable feature row for the selected player."""
    normalized = normalize_player_name(player_name)
    candidates = featured.copy()
    candidates["_normalized_name"] = candidates["player_name"].map(normalize_player_name)

    matched = candidates[candidates["_normalized_name"] == normalized].copy()
    if matched.empty:
        available = sorted(candidates["player_name"].dropna().unique().tolist())
        suggestions = get_close_matches(player_name, available, n=3, cutoff=0.5)
        suggestion_text = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        raise PredictionInputError(f"Player not found: {player_name}.{suggestion_text}")

    latest = matched.sort_values("game_date").iloc[-1].drop(labels="_normalized_name")
    return latest


def predict_for_player(
    player_name: str,
    source: str = "auto",
    csv_path: str | Path = DEFAULT_CSV_PATH,
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> PlayerPrediction:
    """Predict points for the most recent usable row of a selected player."""
    artifact = load_artifact(model_path)
    featured = load_featured_data(source=source, csv_path=csv_path)
    row = find_latest_player_row(featured, player_name)

    features = artifact["features"]
    missing = [feature for feature in features if feature not in row.index]
    if missing:
        raise PredictionInputError(f"Feature row is missing required columns: {missing}")

    prediction = float(artifact["model"].predict(row[features].to_frame().T)[0])
    return PlayerPrediction(
        player_name=str(row["player_name"]),
        game_date=pd.Timestamp(row["game_date"]).date().isoformat(),
        actual_points=float(row["points"]),
        predicted_points=prediction,
    )
