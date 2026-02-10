# TODO — Hybrid Player Points Prediction System

This file breaks the project into small, actionable steps.

---

## Phase 0 — Pivot Decisions & Legacy Audit

- [x] Keep this repo and pivot in-place (no full restart).
- [x] Scope daily inference to players scheduled for today's games.
- [x] Record current infrastructure context:
  - [x] Historical stats previously lived in AWS-hosted SQL.
  - [x] AWS DB was decommissioned for cost control.
  - [x] Supabase-hosted Postgres is selected for v1.
- [x] Choose primary storage path for v1:
  - [ ] CSV-first pipeline.
  - [x] Postgres-first pipeline. *(Locked decision — see `docs/ADR.md` ADR-002)*
- [x] Decide near-term infra approach:
  - [ ] Stay on AWS for v1.
  - [x] Move DB to Supabase during pivot. *(Locked decision — see `docs/ADR.md` ADR-003)*
- [x] Complete legacy code audit and tag modules: *(See `docs/LEGACY_AUDIT.md`)*
  - [x] Reuse ingestion/retry utilities.
  - [x] Reuse schema foundation.
  - [x] Reuse feature-engineering patterns.
  - [x] Replace legacy `/predict` endpoint and model loading contract.

---

## Phase 1 — Repo & Environment Setup

- [x] Create directory structure:
  - [x] `/data/raw`
  - [x] `/data/processed`
  - [x] `/data/lines`
  - [x] `/data/llm`
  - [x] `/models`
  - [x] `/src`
  - [x] `/notebooks`
  - [x] `/grok_prompts`
  - [x] `/scripts`
  - [x] `/docs`
- [x] Initialize git repo.
- [x] Create `requirements.txt` with at least:
  - [x] `pandas`
  - [x] `numpy`
  - [x] `scikit-learn`
  - [x] `joblib`
  - [x] `python-dotenv`
  - [x] `requests` (or Grok SDK)
- [x] Create and activate virtual environment.
- [x] Install dependencies from `requirements.txt`.

---

## Phase 2 — Historical Data Preparation

- [x] Export/ingest historical game logs from Supabase Postgres into `data/raw/game_logs.csv` (or equivalent table/view).
- [x] Add data freshness policy for training set:
  - [x] Define date window/seasons to include. *(See `docs/ADR.md` ADR-009)*
  - [x] Optionally apply recency weighting or filtering. *(No explicit weighting in v1; rolling features handle recency)*
- [x] Create `src/data_loading.py`:
  - [x] Function to load game logs from DB into a DataFrame.
  - [x] Ensure `game_date` is parsed as datetime.
  - [x] Ensure required columns exist and are correctly typed.
- [x] Add basic data validation checks:
  - [x] No duplicate `(player_id, game_id)` rows.
  - [x] No null `player_id` or `game_date`.

---

## Phase 3 — Feature Engineering

- [x] Create `src/features.py`.
- [x] Implement helper functions:
  - [x] `rolling_mean_excl_current(group, col, window, min_periods)`
  - [x] `rolling_std_excl_current(group, col, window, min_periods)`
- [x] Implement main function: `build_player_features(df_games)`:
  - [x] Convert `game_date` to datetime.
  - [x] Sort by `player_id`, `game_date`.
  - [x] Group by `player_id`.
  - [x] Compute:
    - [x] `ppg_last_5`
    - [x] `ppg_last_10`
    - [x] `min_last_5`
    - [x] `usage_last_5` (if `usage` column present)
    - [x] `ts_last_5` (if `ts` column present)
    - [x] `shots_last_5` (if `fga` column present)
    - [x] `points_std_last_10`
  - [x] Compute rest metrics:
    - [x] `days_rest` (difference in `game_date` per player)
    - [x] Fill missing `days_rest` (e.g., 7).
    - [x] `b2b_flag` where `days_rest == 1`.
  - [x] Ensure context columns exist (`home_flag`, `team_pace`, `opp_pace`, `opp_def_rating`), fill with NaN if missing.
- [x] Script to:
  - [x] Load `data/raw/game_logs.csv`.
  - [x] Apply `build_player_features`.
  - [x] Save to `data/processed/features.csv`.

---

## Phase 4 — Grok: Sportsbook Line Fetcher

- [ ] Create `grok_prompts/fetch_lines.txt` with JSON-only prompt template.
- [ ] Create `.env` file for Grok API key.
- [ ] Create `src/grok_client.py`:
  - [ ] Function to read prompt template.
  - [ ] Function to call Grok API with a date.
  - [ ] Function to parse the JSON response.
- [ ] Create `scripts/fetch_lines_for_date.py`:
  - [ ] Accept date as argument.
  - [ ] Call Grok client.
  - [ ] Parse JSON into DataFrame.
  - [ ] Save to `data/lines/{date}.csv`.

---

## Phase 5 — Merge Features and Lines for Training

- [ ] Create `src/dataset_builder.py`.
- [ ] Implement:
  - [ ] Load `data/processed/features.csv`.
  - [ ] Load all relevant `data/lines/*.csv` and concat into one DataFrame.
  - [ ] Join features and lines on:
    - [ ] `player_name` (or `player_id` if mapped)
    - [ ] `game_date` (ensure alignment)
  - [ ] Keep rows with non-null:
    - [ ] `points` (target)
    - [ ] `sportsbook_line`
  - [ ] Save final training dataset to `data/processed/training_dataset.csv`.

---

## Phase 6 — Train ML Model (Random Forest)

- [ ] Create `notebooks/train_rf_model.ipynb` or `src/train_rf_model.py`.
- [ ] Load `data/processed/training_dataset.csv`.
- [ ] Define feature columns (example):
  - [ ] `sportsbook_line`
  - [ ] `ppg_last_5`
  - [ ] `ppg_last_10`
  - [ ] `min_last_5`
  - [ ] `usage_last_5`
  - [ ] `ts_last_5`
  - [ ] `shots_last_5`
  - [ ] `points_std_last_10`
  - [ ] `home_flag`
  - [ ] `opp_def_rating`
  - [ ] `opp_pace`
  - [ ] `team_pace`
  - [ ] `b2b_flag`
  - [ ] `days_rest`
- [ ] Set target column:
  - [ ] Baseline: `points`.
  - [ ] Recommended experiment: residual target `points - sportsbook_line`.
- [ ] Split into train/validation sets.
- [ ] Train `RandomForestRegressor`.
- [ ] Evaluate RMSE and R² on validation.
- [ ] Save model with `joblib` to `models/rf_model.joblib`.

---

## Phase 7 — LLM Predictions (Grok) for Validation Set

- [ ] Create `grok_prompts/predict_points_from_features.txt` with JSON-only prompt.
- [ ] Add function to `src/grok_client.py`:
  - [ ] Build structured JSON input for a single player-game.
  - [ ] Call Grok with feature prompt.
  - [ ] Parse `expected_points` and `rationale`.
- [ ] Create `scripts/get_llm_preds_for_val.py`:
  - [ ] Identify validation rows from `training_dataset` (or separate file).
  - [ ] For each row:
    - [ ] Build Grok feature prompt.
    - [ ] Call Grok, parse `expected_points`.
  - [ ] Save results to `data/llm/llm_preds_val.csv` with:
    - [ ] `game_id`
    - [ ] `player_id`
    - [ ] `llm_pred_points`
    - [ ] `llm_rationale` (optional)

---

## Phase 8 — Train Ensemble Model

- [ ] Create `src/train_ensemble.py`.
- [ ] Steps:
  - [ ] Load validation subset of `training_dataset`.
  - [ ] Load RF model and generate `ml_pred_points` for validation set.
  - [ ] Load `data/llm/llm_preds_val.csv` and merge on `game_id`, `player_id`.
  - [ ] Drop rows with missing `llm_pred_points`.
  - [ ] Fit a `LinearRegression` on:
    - [ ] Features: `ml_pred_points`, `llm_pred_points`
    - [ ] Target: `points`
  - [ ] Print learned weights.
  - [ ] Save ensemble model to `models/ensemble.joblib`.

---

## Phase 9 — Daily Inference Pipeline

- [ ] Create `scripts/predict_today.py`.
- [ ] Steps:
  - [ ] Load today’s schedule + raw game logs up to yesterday.
  - [ ] Keep only players expected to play in today’s scheduled games.
  - [ ] Run feature engineering for games up to today (no leakage).
  - [ ] Fetch today’s lines via Grok and save to `data/lines/{today}.csv`.
  - [ ] Merge today’s features with today’s lines.
  - [ ] Load RF model and predict `ml_pred_points`.
  - [ ] For each player-game:
    - [ ] Build feature JSON and call Grok with feature prompt.
    - [ ] Store `llm_pred_points`.
  - [ ] Load ensemble model.
  - [ ] Compute `final_pred_points` from `ml_pred_points` + `llm_pred_points`.
  - [ ] Save results to `data/processed/predictions_{today}.csv`.

---

## Phase 10 — Documentation & Cleanup

- [ ] Write/Update `README.md` with:
  - [ ] High-level description.
  - [ ] Setup instructions.
  - [ ] Training instructions.
  - [ ] Daily prediction instructions.
- [ ] Add comments to core code paths.
- [ ] Optionally add basic tests:
  - [ ] Test feature engineering functions.
  - [ ] Test that Grok parsing doesn’t crash on malformed outputs.
