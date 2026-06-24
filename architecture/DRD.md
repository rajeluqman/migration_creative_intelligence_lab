# DRD — Data Requirements Document
## Creative Intelligence Pipeline

**Owner:** @senior-data-engineer (draft from existing architecture docs by cabinet doc-gap convene)
**Status:** DRAFT — pending review
**Date:** 2026-06-22

> Per @data-architect's gate ruling on this doc: this DRD **describes** known data issues
> and points to the model's existing, already-ratified answer for each. It does not
> propose new resolution strategies — that would be a model change, routed through
> @data-architect, not documentation.

---

## 1. Source Overview

| Path | Source | Form | Source ref |
|------|--------|------|------------|
| **A — Video** | Client's Google Drive folder | Raw video files (RAW and, sometimes, already-EDITED winning ads), mixed together, near-duplicate compilation footage | `architecture/STACK_AND_FLOW.md` §1–2 |
| **B — Performance (v1.5 only)** | Client-provided Meta/TikTok export | Manual CSV export, 3–15 winning ads | `architecture/DATA_MODEL_v1.5_PERFORMANCE.md` §3, §7 |

No connector (Fivetran/Airbyte/Meta API) at this volume — manual CSV until ~50+ ads/week
and a @data-architect TCO sign-off (`architecture/ADR-004-performance-veto-converted.md`,
"Rejected / still-vetoed" table).

## 2. Ingestion Frequency

**Path A (video):** ad-hoc, client-delivered — the client drops a new Drive folder when
they have footage; there is no fixed daily/hourly cadence to land. The Drive→OneLake ingest
script pulls per drop; a Fabric Data Factory pipeline orchestrates per-asset processing once
landed (retry/backoff activities, rate-limit-aware looping, a `ForEach` activity per `asset_id`
— `architecture/STACK_AND_FLOW.md` §1, §"Orchestration", ADR-008). There is no committed SLA on
how fast a drop must land (see `architecture/BRD.md` §7).

**Path B (performance):** ad-hoc, at 3–15 winning ads per batch — not streaming, not a
scheduled pull (`architecture/DATA_MODEL_v1.5_PERFORMANCE.md` §7).

## 3. Schema — Path A: Gemini extraction JSON (Bronze)

Bronze (`bronze_asset_raw`) stores this **verbatim** — no transform, no business logic
(`architecture/ADR-003-chunking-in-silver.md`; `architecture/DATA_MODEL.md` §3). The schema
is the Gemini `responseSchema` structured-output contract:

| Field | Type | Notes |
|-------|------|-------|
| `chunk_theme` | string | Hook / Problem / Solution / Social Proof / CTA … |
| `sentiment` | string (enum) | |
| `standalone_score` | int 1–5 | safe-to-reuse-alone score |
| `next_compatible_themes[]` | array of string | exploded into `bridge_chunk_compatibility` at Gold, not before |
| `start_ts` / `end_ts` | time | Gemini-set semantic chunk boundaries, not hardcoded |
| `transcript_segment` | text | raw dialogue, cleaned downstream in Silver |
| `model_version` / `prompt_version` | string | reproducibility — re-run from Bronze, diffed, no new API spend |

Plus Bronze metadata: `content_sha256`, `load_ts` (`architecture/DATA_MODEL.md` §3).

## 4. Schema — Path B: performance CSV (Bronze)

`bronze_ad_performance_raw` — verbatim CSV/API capture, append-only, immutable, +
`load_ts`, `source_file`, `content_hash` (`architecture/DATA_MODEL_v1.5_PERFORMANCE.md` §3).
Raw counts only — `impressions`, `plays_3s/25/50/75/100`, `sum_watch_time_sec`,
`play_count`, `link_clicks`, `results`, `spend`. Ratios are **never** stored here; they are
derived downstream in `fct_ad_kpi` (view).

## 5. Known Data Issues

1. **Near-duplicate identity collision.** The client's footage is explicitly "near-duplicate
   compilation footage" — two assets can be substantially the same content. **Existing
   model answer (do not re-derive):** identity = content hash (`asset_id` = SHA-256 of
   video bytes); near-duplicates get a `dq_flag = likely_near_dup` (MEDIUM signal) with
   **no auto-merge** (`architecture/DATA_MODEL.md` §4). Perceptual/fuzzy dedup is v2-vetoed
   (`architecture/DATA_MODEL.md` §10).

2. **LLM output non-determinism.** Gemini's chunking/scoring is not guaranteed stable across
   re-runs of the same asset. **Existing model answer:** the idempotency gate treats
   reprocessing drift as a signal, not a block; the golden-dataset gate (≥80% Jaccard
   agreement, ±1 on score) is the only gate allowed to fail a deploy, and only at the
   pipeline level (`architecture/DATA_MODEL.md` §7, gates 3–4).

3. **Schema-valid-but-empty response.** A Gemini response can pass JSON-schema validation
   while containing zero chunks (`{"chunks": []}`) — none of the four existing gates catch
   this. **Status: OPEN, not yet implemented** — tracked as the "5th LLM-output gate" (same
   open item as `creative_intelligence_lab/PROJECT_STATUS.md` finding #2,
   `great_expectations/README.md` line 3 — pipeline logic, not stack-specific, carries over
   unresolved). This DRD records it as a known issue; it does not resolve it here.

4. **`ad_id` → `asset_id` join is manual.** Path B's join key is a hand-maintained mapping
   (`map_ad_asset.csv`), enforced by a GE referential check, not a guaranteed key (no dbt —
   dbt is dropped, ADR-008; `architecture/STACK_AND_FLOW.md` §3). Manual-mapping errors are a
   plausible failure mode at this volume — row-count reconciliation EDL→`bridge_ad_chunk` is
   also still **OPEN** (same open item as `creative_intelligence_lab/PROJECT_STATUS.md`
   finding #3).

## 6. Sign-off Gate

| Agent | Status | Reason | Date |
|-------|--------|--------|------|
| @data-architect | ✅ APPROVED (doc-gap convene) | Pure upstream documentation; reinforces content-hash identity + golden-dataset gate, no new resolution strategy proposed | 2026-06-22 |
| @scope-guardian | ✅ APPROVED (doc-gap convene) | Documents existing Bronze landing layer per the locked stack table, no new ingestion behavior | 2026-06-22 |
