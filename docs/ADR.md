# Architecture Decision Records — Prop-Porter v1 Pivot

## ADR-001: In-place pivot, no full restart

**Status:** Accepted
**Date:** 2026-02-06
**Context:** The existing repo has working ingestion pipelines, schema definitions, and feature-engineering patterns. Starting from scratch would discard tested infrastructure.
**Decision:** Pivot in-place in this repo. Reuse reliable modules, replace the legacy prediction path.
**Consequences:** Must audit legacy code and tag reuse vs replace boundaries cleanly.

---

## ADR-002: Postgres-first data path for v1

**Status:** Accepted
**Date:** 2026-02-09
**Context:** The AWS DB was decommissioned. A CSV-first pipeline would add unnecessary file I/O and synchronization overhead.
**Decision:** Use Postgres as the primary data path for training extraction, feature computation inputs, and daily inference, with Supabase Postgres as the managed DB target.
**Consequences:** Pipeline scripts must connect to Supabase Postgres. CSV/Parquet exports are secondary artifacts for portability and debugging.

---

## ADR-003: Supabase Postgres data infrastructure for v1

**Status:** Accepted
**Date:** 2026-02-09
**Context:** The prior AWS DB is no longer available. v1 still needs managed Postgres for historical storage, daily reads, and training extraction.
**Decision:** Move the DB layer to Supabase during the pivot and keep the app runtime deploy target flexible (local/Docker) for v1.
**Consequences:** DB connection setup and runbooks must target Supabase credentials/SSL. App hosting can be migrated independently after data layer stabilization.

---

## ADR-004: Grok as primary LLM provider

**Status:** Accepted
**Date:** 2026-02-06
**Context:** The hybrid pipeline requires an LLM for sportsbook line retrieval and feature-based scoring. Grok is the selected provider.
**Decision:** Use Grok for both line fetching (structured JSON prompts) and player points scoring.
**Consequences:** Must implement Grok client with strict JSON parsing, caching, and budget controls. Fallback chain degrades gracefully when LLM is unavailable.

---

## ADR-005: Daily slate timezone is America/New_York (ET)

**Status:** Accepted
**Date:** 2026-02-06
**Context:** NBA schedules are published in Eastern Time. Using a consistent timezone avoids date boundary ambiguity.
**Decision:** All daily slate operations use ET as the reference timezone.
**Consequences:** Schedule fetch, line retrieval, and output file naming all key on ET date.

---

## ADR-006: Custom prediction endpoint is internal-only in v1

**Status:** Accepted
**Date:** 2026-02-06
**Context:** The daily slate pipeline is the primary v1 deliverable. Custom single-player prediction is useful for debugging but not ready for public use.
**Decision:** Keep custom prediction as an internal-only endpoint. Public frontend only surfaces daily slate predictions.
**Consequences:** Frontend custom prediction UI is hidden in v1. Internal endpoint available for diagnostics.

---

## ADR-007: Residual modeling target

**Status:** Accepted
**Date:** 2026-02-06
**Context:** Sportsbook lines are a strong prior for player points. Training directly on raw points ignores this signal.
**Decision:** ML model trains on residual target: `residual = points - sportsbook_line`. At inference: `predicted_points = sportsbook_line + predicted_residual`.
**Consequences:** Model focuses on deviations from market consensus. Sportsbook line is always required at inference (handled by fallback chain).

---

## ADR-008: Fallback chain for inference

**Status:** Accepted
**Date:** 2026-02-06
**Context:** LLM scoring may fail due to budget caps, parse errors, or timeouts. The pipeline must not fail entirely when LLM is unavailable.
**Decision:** Row-level fallback chain: Ensemble -> ML + line -> ML-only -> no prediction (flagged).
**Consequences:** Every prediction row carries a `prediction_mode` and optional `reason_code`. Coverage metrics track fallback usage per run.

---

## ADR-009: Data freshness policy for training set

**Status:** Accepted
**Date:** 2026-02-09
**Context:** The ML model needs a defined training window of historical data. Too little data reduces accuracy; too much includes stale roster/playstyle patterns.
**Decision:**
- Default training window: 3 NBA seasons, controlled by the `API_SEASONS` env var.
- Current default seasons: `2021-22, 2022-23, 2023-24`.
- No explicit recency weighting in v1. Rolling feature windows (last 5/10 games) inherently emphasize recent performance.
- Re-extract data before each model retraining cycle using `scripts/extract_game_logs.py`.
- Extraction metadata (run_id, row count, date range) is tracked in `data_extraction_runs` table.
**Consequences:** Adding a new season requires updating `API_SEASONS` and re-running ingestion + extraction. No automated schedule in v1 — retraining is manual.
