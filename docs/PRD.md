# PRD: Prop-Porter Pivot v1 - Hybrid NBA Player Points Prediction

## Document Control
- Version: 1.0
- Status: Execution draft
- Date: 2026-02-06
- Product owner: Prop-Porter maintainer
- Engineering owner: Backend and ML leads
- Scope horizon: v1 pivot (6 weeks)

## 1. Executive Summary
Prop-Porter currently serves a legacy single-model prediction path that is too brittle for daily NBA points forecasting. This pivot replaces the legacy path with a hybrid system that combines:
- Sportsbook points line as prior signal.
- Tabular ML residual model.
- Grok-based structured feature scoring.
- Ensemble combiner.

Primary v1 output is daily pregame points predictions for players scheduled on that date. Custom single-player prediction will remain internal-only during v1.

This PRD includes implementation-level TODO checklists, acceptance gates, and concrete file-level deliverables.

## 2. Problem Statement
Current issues:
- Legacy prediction endpoint is limited to two handcrafted features and does not match current modeling goals.
- Model artifact contract is inconsistent between training and inference.
- Frontend and backend route contracts are misaligned.
- Data ingestion and reliability patterns exist but need cleanup before reuse.

Business need:
- Deliver a reliable daily slate pipeline with stronger predictive accuracy and clear operational controls.

## 3. Product Goals
1. Accuracy:
   - Ensemble RMSE beats line-only baseline by >= 5 percent.
   - Ensemble RMSE beats ML-only baseline by >= 2 percent.
2. Coverage:
   - Generate predictions for >= 90 percent of scheduled players each run.
3. Runtime:
   - Daily pipeline completes in under 20 minutes.
4. Reliability:
   - End-to-end run success >= 99 percent over rolling 30 days.
5. Operational control:
   - LLM usage is measurable, capped, and degradable without full pipeline failure.

## 4. Non-Goals (v1)
- Predicting rebounds, assists, or fantasy composite stats.
- Real-time in-game updates.
- Supabase migration during initial v1 delivery.
- Public custom player prediction flow.

## 5. Locked Decisions
1. In-place pivot in this repo, no full restart.
2. Postgres-first data path for v1.
3. AWS-first infrastructure for v1; Supabase explicitly deferred.
4. Grok is primary LLM provider for lines and feature-based scoring.
5. Daily slate timezone is America/New_York (ET).
6. Custom prediction endpoint is internal-only in v1.
7. Modeling target uses residual approach:
   - `residual_points = points - sportsbook_line`
   - `predicted_points = sportsbook_line + predicted_residual`
8. Fallback chain for inference:
   - Ensemble -> ML plus line -> ML-only -> no prediction (flagged).

## 6. Initial Cost and Runtime Policy
Runtime:
- Hard target: complete by 20 minutes per daily run.

LLM spending controls (initial defaults):
- Soft cap: USD 20 per day.
- Hard cap: USD 500 per month.
- On cap breach: automatically disable LLM scoring and continue with fallback chain.

Caching policy:
- Cache key: `(player_id, game_date, feature_hash, prompt_version)`.
- Reuse cache for retries and reruns on same slate.

## 7. Users and Use Cases
Primary user:
- Internal analyst/developer validating and operating daily model output.

Primary use case:
- Run daily pregame pipeline and retrieve player points predictions for that slate.

Secondary use case:
- Internal diagnostics for one-off player request and model breakdown.

## 8. Functional Requirements
### FR-001: Daily schedule scope
- System must identify players expected to participate in games scheduled for ET date D.
- Output must be restricted to scheduled-player rows only.

### FR-002: Historical data load and validation
- System must pull required historical rows from Postgres.
- Must fail fast on missing required columns or invalid types.
- Must run duplicate/null key validation.

### FR-003: Leakage-safe feature engineering
- Rolling features must exclude current game row (`shift(1)` behavior).
- Days-rest and b2b features must be computed per player timeline.
- Missing optional context features must be handled with explicit fallback values.

### FR-004: Sportsbook line retrieval
- System must fetch daily player points lines via Grok prompt.
- Parser must enforce strict JSON shape and reject malformed rows.
- Line source and retrieval timestamp must be persisted.

### FR-005: Player identity reconciliation
- Sportsbook player naming must map to canonical `player_id`.
- Mapping pipeline must support alias table and deterministic normalization.
- Unmapped players must be logged with reason code.

### FR-006: ML model training
- System must train residual RandomForest model with configured feature set.
- Must persist artifact with explicit metadata and feature contract.

### FR-007: LLM feature scoring
- For each needed player-game row, system must request expected points from Grok.
- Response must parse into numeric `llm_pred_points` or return structured failure.

### FR-008: Ensemble training and inference
- System must train linear combiner over ML and LLM outputs.
- Inference must apply fallback logic when LLM score missing.

### FR-009: Daily output persistence
- System must write one daily prediction artifact with run metadata.
- Must include confidence/fallback reason fields per row.

### FR-010: API contract
- External v1 API focuses on daily slate predictions.
- Internal-only endpoint may expose one-player debug payload.

### FR-011: Observability
- Every run must emit metrics for runtime, coverage, parse success, cost, and fallback rates.

## 9. Data Contracts
### 9.1 Historical game log minimum columns
Required:
- `game_id`
- `game_date`
- `player_id`
- `player_name`
- `team_id`
- `opponent_team_id`
- `home_flag`
- `points`
- `minutes`
- `fga`

Optional with fallback handling:
- `usage`
- `ts`
- `team_pace`
- `opp_pace`
- `opp_def_rating`

### 9.2 Engineered feature schema (minimum)
- `ppg_last_5`
- `ppg_last_10`
- `min_last_5`
- `usage_last_5`
- `ts_last_5`
- `shots_last_5`
- `points_std_last_10`
- `days_rest`
- `b2b_flag`
- `home_flag`
- `team_pace`
- `opp_pace`
- `opp_def_rating`
- `sportsbook_line`

### 9.3 Grok lines JSON schema
Each row must include:
- `player_name` (string)
- `team` (string)
- `opponent` (string)
- `game_datetime_local` (ISO string)
- `sportsbook_line` (number)
- `sportsbook_name` (string)

### 9.4 LLM scoring schema
- `player_id` (int)
- `game_id` (string)
- `game_date` (date)
- `llm_pred_points` (float)
- `llm_status` (enum: ok, parse_error, timeout, skipped_budget, unmapped)
- `prompt_version` (string)

### 9.5 Final prediction schema
- `run_id`
- `game_date`
- `game_id`
- `player_id`
- `player_name`
- `sportsbook_line`
- `ml_pred_points`
- `llm_pred_points` (nullable)
- `final_pred_points`
- `prediction_mode` (ensemble, ml_plus_line, ml_only, no_prediction)
- `reason_code` (nullable)
- `created_at`

## 10. API Contract (v1)
### 10.1 External endpoints
1. `GET /api/v2/health`
2. `GET /api/v2/predictions/daily?date=YYYY-MM-DD`

`GET /api/v2/predictions/daily` response shape:
- `date` (ET date)
- `run_status`
- `run_id`
- `coverage`
- `predictions` array of final prediction schema rows

### 10.2 Internal endpoints
1. `POST /api/v2/internal/predict/player`
- Purpose: debug one-player prediction path.
- Not used by public frontend in v1.

## 11. System Architecture (Target)
1. Postgres historical source -> data validation.
2. Leakage-safe feature builder.
3. Grok line fetch and strict parser.
4. Identity mapper to canonical player ids.
5. Residual ML model training and scoring.
6. Grok feature scoring and cache.
7. Ensemble combiner.
8. Daily output persistence and API serving.

## 12. Quality Gates and Acceptance Criteria
### Gate A: Data quality
- No duplicate `(player_id, game_id)` rows in training source.
- No null `player_id` or `game_date` in training source.

### Gate B: Mapping quality
- Player mapping coverage >= 98 percent for last 14 slates.

### Gate C: Parser quality
- Grok line parser success >= 95 percent per run.

### Gate D: Modeling quality
- Ensemble beats line-only baseline RMSE by >= 5 percent.
- Ensemble beats ML-only RMSE by >= 2 percent.

### Gate E: Operational quality
- Daily run under 20 minutes.
- Prediction coverage >= 90 percent of scheduled players.
- Fallback usage and no-prediction rate logged per run.

## 13. Risks and Mitigations
1. Risk: Grok returns malformed JSON.
   - Mitigation: strict parser, retry with backoff, reject partial rows, cache valid results.
2. Risk: Player name mismatch across sources.
   - Mitigation: alias mapping table, normalization rules, unresolved-player queue.
3. Risk: LLM latency or cost spikes.
   - Mitigation: caching, budget caps, automatic degrade mode.
4. Risk: Leakage in model development.
   - Mitigation: shift-based features, rolling date validation, out-of-fold protocol.
5. Risk: Route and artifact contract drift.
   - Mitigation: schema tests and explicit model metadata contract.

## 14. Rollout Strategy
Stage 1: Shadow mode (7 days)
- Run new pipeline daily without replacing served predictions.
- Compare outputs and collect metrics.

Stage 2: Limited serve (internal consumers)
- Expose daily endpoint to internal UI only.

Stage 3: Full v1 serve
- Promote new endpoint and retire legacy public prediction path.

## 15. Detailed TODO Breakdown (Execution Checklist)

### Phase 0 - Repo Hygiene and Decision Freeze
- [ ] Remove docs ignore rule so PRD and TODO docs are tracked.
- [ ] Add ADR file documenting locked decisions from Section 5.
- [ ] Record API contract version and owner.
- [ ] Record model artifact contract version and owner.
- [ ] Create milestone board with phases 0-8.

Definition of done:
- [ ] PRD and TODO are in git tracking.
- [ ] ADR approved.
- [ ] Contract docs signed off.

### Phase 1 - Legacy Stabilization
- [ ] Fix model artifact load contract mismatch between training and API.
- [ ] Fix ingestion loop indentation and row-insert logic in game loader.
- [ ] Fix any SQL query references to non-existent columns in legacy routes.
- [ ] Add smoke tests for current `/api/v1/health`, `/api/v1/teams`, `/api/v1/players`.
- [ ] Add regression test for model artifact load and predict path.

Definition of done:
- [ ] Legacy app boots without runtime exceptions.
- [ ] Smoke tests pass locally.
- [ ] Data loader inserts expected game row counts.

### Phase 2 - Data Foundation
- [ ] Create canonical training extraction query or materialized view.
- [ ] Add validation script for duplicates and null keys.
- [ ] Define training lookback window and refresh policy.
- [ ] Add run metadata table for data snapshots.
- [ ] Save validated extraction to `data/processed/training_source.parquet`.

Definition of done:
- [ ] Validation reports generated and stored.
- [ ] Training source reproducible from one command.

### Phase 3 - Feature Engineering Layer
- [ ] Implement `backend/pipeline/data_loading.py`.
- [ ] Implement `backend/pipeline/features.py`.
- [ ] Implement rolling mean and std helpers with shift.
- [ ] Implement rest features and context defaults.
- [ ] Add unit tests for no-leakage behavior.
- [ ] Emit `data/processed/features.parquet`.

Definition of done:
- [ ] Feature unit tests pass.
- [ ] Spot checks confirm no current-row leakage.

### Phase 4 - Sportsbook Lines and Identity Mapping
- [ ] Create `grok_prompts/fetch_lines.txt` with strict JSON response contract.
- [ ] Implement `backend/pipeline/grok_client.py` for line fetch.
- [ ] Implement parser with schema validation and reason codes.
- [ ] Create alias mapping table and deterministic normalization rules.
- [ ] Implement `scripts/fetch_lines_for_date.py`.
- [ ] Persist outputs to `data/lines/YYYY-MM-DD.parquet`.

Definition of done:
- [ ] Parse success meets Gate C over sampled historical dates.
- [ ] Mapping coverage meets Gate B.

### Phase 5 - ML Residual Model
- [ ] Implement `backend/pipeline/train_residual_model.py`.
- [ ] Use target `points - sportsbook_line`.
- [ ] Run date-ordered validation split.
- [ ] Compute and log metrics vs line-only baseline.
- [ ] Persist artifact to `models/rf_residual.joblib` with metadata.

Definition of done:
- [ ] Model artifact includes model plus feature list plus version metadata.
- [ ] Validation report committed to `docs/reports/`.

### Phase 6 - LLM Scoring and Ensemble
- [ ] Create `grok_prompts/predict_points_from_features.txt`.
- [ ] Implement `scripts/get_llm_preds_for_val.py` with cache support.
- [ ] Add status codes for timeout, parse error, budget skip.
- [ ] Implement `backend/pipeline/train_ensemble.py`.
- [ ] Train ensemble using OOF-safe prediction set.
- [ ] Persist artifact to `models/ensemble.joblib`.

Definition of done:
- [ ] Ensemble metrics meet Gate D.
- [ ] LLM cache hit behavior verified on rerun.

### Phase 7 - Daily Inference and API v2
- [ ] Implement `scripts/predict_today.py` orchestration.
- [ ] Add budget checks and degrade mode controls.
- [ ] Apply fallback chain at row level.
- [ ] Persist daily output file and DB table records.
- [ ] Implement `GET /api/v2/predictions/daily` and `/api/v2/health`.
- [ ] Keep `/api/v1/predict` internal-only during transition.

Definition of done:
- [ ] Runtime meets Gate E.
- [ ] Coverage meets Gate E.
- [ ] API response schema tests pass.

### Phase 8 - Frontend and Ops Hardening
- [ ] Update frontend to use `/api/v2/predictions/daily`.
- [ ] Hide custom prediction UI in public view.
- [ ] Add run dashboard metrics: runtime, coverage, parse success, fallback usage, estimated cost.
- [ ] Add runbook and failure playbook.
- [ ] Execute 7-day shadow mode and capture report.

Definition of done:
- [ ] Frontend daily view uses v2 endpoint only.
- [ ] Shadow mode report approved.
- [ ] Go-live checklist completed.

## 16. Dependencies
- Grok API key and rate limits.
- Stable AWS Postgres connectivity.
- Schedule source availability before run window.

## 17. Open Items Requiring Confirmation
1. Daily job schedule windows in ET (single run vs two refreshes).
2. Whether to persist `llm_rationale` at all in production logs.
3. Final threshold for minimum expected minutes filter before LLM scoring.

## 18. Out-of-Scope Backlog (Post-v1)
- Injury-aware features and lineup context.
- Additional betting markets.
- Supabase migration.
- Public custom prediction experience.

