# Legacy Code Audit — Prop-Porter v1 Pivot

**Date:** 2026-02-06
**Scope:** All existing backend, scripts, schema, and ML code.

---

## 1. REUSE: Ingestion & Retry Utilities

**File:** `scripts/init_data_load.py`

### What works well
- `make_api_request()` (line 79): Robust retry logic with configurable max retries, exponential backoff, and transient error handling. Production-ready pattern.
- `rate_limit_sleep()` (line 75): Simple randomized sleep to avoid API rate limits.
- `_get_env_int()`, `_get_env_bool()`, `_get_env_float()` (lines 17-35): Safe env config helpers with defaults.
- `_parse_env_seasons()` (line 46): Season string parser with validation.
- `convert_time_to_minutes()` (line 403): Time string converter with edge case handling.
- All data loaders (`load_teams_data`, `load_players_data`, `load_player_game_stats`) use `ON CONFLICT` upsert patterns and commit-per-batch for resilience.

### Known bugs
- **`load_games_data()` indentation bug (line 323):** The `is_home, opponent_abbr = parse_matchup(row['MATCHUP'])` line and all subsequent row-processing code is outside the `for index, row` loop. Only the last row from the API response gets processed. The for loop body at line 320 only contains the team ID check and `continue`.

### Reuse plan
- Extract `make_api_request`, `rate_limit_sleep`, and env helpers into a shared utility module (`backend/utils/retry.py` or similar).
- Fix the `load_games_data` indentation bug before any further use.

---

## 2. REUSE: Schema Foundation

**File:** `backend/schema.sql`

### What works well
- Core tables (`teams`, `players`, `games`, `player_game_stats`) are properly normalized with foreign keys and unique constraints.
- `games` table includes `opponent_team_id`, `is_home`, `season_type`, and `tipoff_datetime` — all useful for the new pipeline.
- `player_game_stats` has `UNIQUE (player_id, game_id)` constraint preventing duplicates (matches PRD Gate A).
- `game_lines` table already exists for sportsbook line storage (needs adaptation from game-level to player-level lines).
- `injury_reports` table is a useful placeholder for future features.
- Indexes on `(team_id, game_date)` and `(player_id, game_id)` support the query patterns needed.

### Gaps
- `player_game_stats` lacks a direct `game_date` column — requires JOIN with `games` to get dates. Acceptable relationally but adds query complexity.
- No `player_lines` table for per-player sportsbook points lines. The existing `game_lines` stores game-level spreads/totals, not player props.
- No `daily_predictions` or `run_metadata` tables needed by the new pipeline.

### Reuse plan
- Keep all existing tables as-is.
- Add new tables for player lines, prediction output, and run metadata in Phase 2+.

---

## 3. REUSE: Feature Engineering Patterns

**File:** `backend/ml/train_model.py`

### What works well
- `feature_engineering()` (line 87): Solid implementation with `.shift(1)` on all rolling/EWM features to prevent current-row leakage.
- Rolling windows at 5 and 10 games for player points and points-per-minute.
- Days rest computation with `fillna(7)` default and `clip(0, 10)`.
- Opponent defensive features computed at team-level first, then joined to player rows — avoids per-player leakage.
- Defensive rating proxy using possessions estimate.
- Fallback chains for missing opponent features (per-opponent mean -> global mean).
- `time_based_split()` (line 193): Clean chronological split for validation.
- `create_training_dataframe()` (line 25): Well-structured SQL with CTE for opponent data.

### Patterns to carry forward
- Shift-based leakage prevention on all rolling features.
- Team-level feature computation joined to player rows.
- Hierarchical fallback for missing values (group mean -> global mean).
- Time-based validation split (not random).

### What to adapt
- Current target is raw `player_points`. New pipeline uses residual target (`points - sportsbook_line`) per ADR-007.
- Current features don't include `sportsbook_line`, `usage`, or `ts` (true shooting). These will be added in the new feature set.
- Rolling std (volatility) feature `points_std_last_10` is not implemented yet — needed per PRD.

---

## 4. REPLACE: Legacy `/predict` Endpoint

**File:** `backend/api/routes.py`

### Problems
- **Model artifact mismatch (line 13):** `train_model.py` saves `{"model": model, "features": features}` dict via joblib. `routes.py` loads it with `joblib.load("../player_points_predictor.pkl")` and calls `model.predict()` directly. Since the loaded object is a dict, not a model, `.predict()` will raise `AttributeError`.
- **Only 2 features (lines 196-235):** Prediction uses only `player_points_last_10` and `opponent_avg_points_allowed_last_10`, computed via raw SQL at request time. This bypasses the feature engineering pipeline entirely.
- **Fragile model path (line 13):** Relative path `"../player_points_predictor.pkl"` depends on working directory.
- **No validation:** No input sanitization beyond type coercion. Missing parameters return 400 but other edge cases (invalid player ID, no historical data) are not handled.

### Replace plan
- Replace with `GET /api/v2/predictions/daily?date=YYYY-MM-DD` serving precomputed daily predictions.
- Keep `POST /api/v2/internal/predict/player` as internal-only debug endpoint.
- Retire `/api/v1/predict` after v2 is stable.

---

## 5. REPLACE: Model Loading Contract

### Problems
- Training saves: `joblib.dump({"model": model, "features": features}, "player_points_predictor.pkl")`
- Serving loads: `model = joblib.load("../player_points_predictor.pkl")` then `model.predict(feature_df)`
- These are incompatible. The serving code expects a bare model, but gets a dict.

### Replace plan
- New artifact contract: save model + feature list + metadata (version, training date, metrics) as a structured dict.
- Serving code must unpack the dict: `artifact = joblib.load(path); model = artifact["model"]`.
- Model path should be configurable via env var, not hardcoded relative path.

---

## 6. Other Issues

### `backend/data/nba_client.py`
- Standalone NBA API wrapper. Largely redundant with `scripts/init_data_load.py`.
- **Tag:** Low priority. Can be removed or consolidated later.

### `Dockerfile`
- References `src.api:app` but app is at `backend/api/__init__.py`.
- Copies `player_points_predictor.pkl` from root — will need updating for new model path.
- **Tag:** Update after pipeline restructure.

### `tests/test_data_utils.py`
- Only tests `convert_time_to_minutes`. Minimal but functional.
- **Tag:** Expand with feature engineering and data validation tests in Phase 3.

### `backend/api/routes.py` — Other endpoints
- `GET /api/v1/health`: Works fine. Keep as-is, add v2 health endpoint alongside.
- `GET /api/v1/teams`, `GET /api/v1/players`, `GET /api/v1/players/<id>/stats`, `GET /api/v1/teams/<id>/games`: Functional data endpoints. Keep for now, may retire in v2.
- **Note:** `get_player()` and `get_player_stats()` have `return jsonify(...)` inside the `finally` block (lines 93, 136). This works in Python but is unconventional — the return executes regardless of exceptions.

### `test_env/` directory
- Appears to be a committed virtual environment. Added to `.gitignore`.

### `player_points_predictor.pkl` in repo root
- Model artifact committed to repo root. Should be in `models/` directory (already gitignored).
- `.gitignore` now covers `*.pkl` and `*.joblib`.
