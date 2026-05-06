"""Model training and evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

from src.features import FEATURE_COLUMNS, TARGET_COLUMN


@dataclass
class ExperimentResult:
    model: RandomForestRegressor
    predictions: pd.DataFrame
    mae: float
    r2: float


def train_and_evaluate(train_df: pd.DataFrame, test_df: pd.DataFrame) -> ExperimentResult:
    """Train a baseline random forest and evaluate on a held-out time split."""
    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        min_samples_leaf=2,
        n_jobs=1,
    )
    model.fit(train_df[FEATURE_COLUMNS], train_df[TARGET_COLUMN])

    preds = model.predict(test_df[FEATURE_COLUMNS])
    prediction_frame = test_df[["game_date", "player_name", "points"]].copy()
    prediction_frame["predicted_points"] = preds

    return ExperimentResult(
        model=model,
        predictions=prediction_frame,
        mae=mean_absolute_error(test_df[TARGET_COLUMN], preds),
        r2=r2_score(test_df[TARGET_COLUMN], preds),
    )
