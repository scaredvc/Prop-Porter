# Hybrid NBA Player Points Prediction

This project predicts NBA player points for upcoming games using a hybrid pipeline:

- Tabular ML (Random Forest baseline).
- Grok predictions from structured feature prompts.
- Sportsbook points lines as a primary anchor signal.
- A learned ensemble that combines ML + LLM outputs.

---

## Current Project Context (Confirmed)

- Historical player stats currently live in an AWS-hosted SQL database.
- Current historical data is considered noisy/outdated for direct use without stronger recency handling.
- Existing backend is hosted on AWS.
- Possible infrastructure migration path: AWS DB/backend to Supabase.
- Storage for the pivot can be CSV-first or Postgres-first.
- Daily inference scope: run predictions for players scheduled in that day's games.

---

## Pivot Strategy

Do not restart the repo from scratch. Pivot in-place:

- Reuse reliable ingestion, schema, and feature-engineering foundations.
- Replace the legacy single-model prediction path with the new PRD workflow.
- Build the Grok + sportsbook + ensemble system as new modules under `src/` and `scripts/`.

---

## Reuse from Existing Repo

- Data ingestion reliability patterns (retry/rate limit): `scripts/init_data_load.py`.
- Core relational schema for teams/players/games/player game stats: `backend/schema.sql`.
- Time-aware feature engineering baseline: `backend/ml/train_model.py`.
- Existing endpoint and frontend structure as scaffolding for a future hybrid prediction API/UI.

---

## Refactor or Replace

- Legacy `/predict` implementation in `backend/api/routes.py` should be replaced by the hybrid pipeline API.
- Model artifact contract must be unified (loader/predictor currently inconsistent).
- Add explicit Grok clients/prompts, line-fetch scripts, and JSON parsing guards.
- Add a robust feature-line join layer (player/date reconciliation and missing-line fallback).
- Add ensemble training and inference paths.

---

## High-Level Architecture (Target)

1. Historical data prep and validation.
2. Leakage-safe rolling feature engineering.
3. Sportsbook points line fetch via Grok (strict JSON).
4. ML model training using engineered features plus sportsbook line.
5. Grok feature-based expected points for validation/inference rows.
6. Ensemble training with `ml_pred_points` + `llm_pred_points`.
7. Daily inference for players on today's slate.

---

## Modeling Note

Recommended experiment:

- Train on residual target: `residual_points = points - sportsbook_line`.
- At inference: `predicted_points = sportsbook_line + predicted_residual`.

This usually stabilizes drift when player roles change and treats the market line as a strong prior.

---

## Next Build Order

1. Implement `src/data_loading.py` and `src/features.py`.
2. Implement Grok line fetcher and parser (`src/grok_client.py`, `scripts/fetch_lines_for_date.py`).
3. Implement dataset builder and RF trainer.
4. Implement validation-set Grok scoring and ensemble trainer.
5. Implement daily prediction pipeline for scheduled players.
