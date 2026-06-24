# DQD — Data Quality Document
## Creative Intelligence Pipeline

**Owner:** @data-quality-steward
**Status:** DRAFT — pending review
**Date:** 2026-06-22

> This is the narrative *why* behind the suites. `great_expectations/README.md` is the
> terse build manifest (what to bootstrap); this doc is the design reasoning + honest
> status of each gate. Per @scope-guardian's gate ruling: writing this narrative does
> **not** implement any TODO gate — open items are flagged OPEN below, not papered over.

---

## 1. The novel risk

**Silver is "unreliable narration"** — a row can be schema-valid yet semantically wrong,
because the upstream transform is a non-deterministic LLM, not a deterministic parser.
Four gates, cheapest-first (`architecture/DATA_MODEL.md` §7):

| # | Gate | Severity | Boundary | Action on failure |
|---|------|----------|----------|--------------------|
| 1 | JSON-schema gate | CRITICAL | Bronze→Silver | quarantine, never blocks batch |
| 2 | Business-constraint gate (`1<=standalone_score<=5`, enum `sentiment`, non-empty `chunk_theme`) | CRITICAL | Silver | quarantine the row, **do not retry** — retrying non-deterministic input just burns API spend |
| 3 | Golden-dataset gate (~30–50 hand-labeled videos, pilot: 5; ≥80% Jaccard ±1 on score) | HIGH | pipeline-level | **the only gate allowed to fail a deploy** — human review, not auto-retry |
| 4 | Idempotency gate (same `asset_id` reprocessed) | MEDIUM | Silver | drift beyond tolerance is a **signal, not a block** — LLM variance is expected |

**Promotion rule:** Silver constraint-pass ≥95% before Gold build (`architecture/DATA_MODEL.md` §7).

## 2. Suites per layer

Source: `great_expectations/README.md`.

| Suite | Layer | Checks |
|-------|-------|--------|
| `bronze_asset_raw` | Bronze | Valid JSON; **chunks length ≥ 1** (catches schema-valid-but-empty LLM output — *specified, not yet built; see §3*) |
| `silver_chunk` | Silver | `standalone_score ∈ [1,5]`; `sentiment` enum; non-empty `chunk_theme` |
| `fact_ad_performance` | Gold (v1.5) | counts/spend ≥ 0; `platform` enum; FK constrained to `EDITED`; every `ad_id` resolves to ≥1 chunk |
| `mart_chunk_perf_correlation` | Gold (v1.5) | `n_ads < 5` ⇒ BLOCK (not surfaced); `honesty_note` not null |

Full v1.5 gate list: `architecture/SPEC_v1.5_performance_marts.md` §7.

## 3. ⚠️ Known gaps — OPEN, not implemented

Honesty per Clean-ERD Doctrine rule 6 (name what is deliberately/currently out): a DQD
that claims completeness it doesn't have is worse than no DQD.

1. **5th LLM-output gate (non-triviality / completeness-floor) — OPEN.** All four gates in
   §1 pass a schema-valid-but-empty `{"chunks": []}` Gemini response. Needed: a GE
   expectation `chunks length >= 1` at the Bronze→Silver boundary, quarantining empties.
   Owner: @data-quality-steward. (Originally surfaced during the sibling repo's first real
   Drive run — see `creative_intelligence_lab/PROJECT_STATUS.md` finding #2 — the
   `bronze_asset_raw` suite line above already lists this check; not yet *built* in either repo.)
2. **Row-count reconciliation, EDL → `bridge_ad_chunk` — OPEN.** An inner join can silently
   drop EDL rows whose `chunk_id` is absent from `fact_chunk`. HIGH severity. (Same open item
   as `creative_intelligence_lab/PROJECT_STATUS.md` finding #3 — pipeline logic, not
   stack-specific, so it carries over unresolved.)
3. **`bridge_ad_chunk` grain guard — REQUIRED AT F2, not yet built here.** In the sibling repo
   this was DONE as a dbt schema test (`unique_combination_of_columns [ad_id, chunk_id,
   position_in_ad]` + not-nulls + position-range, in `_performance.yml` —
   `creative_intelligence_lab/PROJECT_STATUS.md` finding #1). This repo has no dbt and no
   `_performance.yml` (ADR-008) — the equivalent GE expectation on the Gold Warehouse view
   needs authoring when F2 builds it. Not done by inheritance; tracked here so it isn't missed.

## 4. Reconciliation gate (serving-layer truth boundary)

**Fabric build (ADR-008, supersedes ADR-005):** Power BI Direct Lake reads the Gold Warehouse
T-SQL `VIEW`s, which in turn read the Silver Delta tables via a OneLake shortcut — no import,
no duplication, by construction (Direct Lake mode has no separate copy to drift). The
reconciliation risk that remains is at the **view** layer, not the BI layer: this is enforced
by a **reconciliation test** — a Warehouse view's row counts + key sets must exact-match a
direct read of the same Lakehouse Delta table it shortcuts to. This is not a nicety — it is the
mechanism that keeps "the OneLake Delta tables = sole source of truth" true in practice, not
just on paper. @data-architect's veto re-fires if the serving layer ever diverges (a
Power-BI-only measure backed by nothing in the Warehouse, a Copilot-cached copy, a KPI
persisted only in a Power BI dataset instead of a Gold view).

## 5. Honesty gates (v1.5 — distinct from data-quality gates above)

These guard *interpretation*, not row validity — release blockers owned by
@data-quality-steward (`architecture/ADR-004-performance-veto-converted.md`):

- **G1 within-winners:** only "AMONG ads that already succeeded…" framing is honest output;
  causal/lift language is forbidden.
- **G2 within-platform:** no pooling Meta + TikTok; cross-platform = rank-direction
  agreement only.
- **G3 sample ladder:** n<5 BLOCK · 5–11 DIRECTIONAL · ≥12 (≥5/group) SUGGESTIVE.
- **G4 double-count guard:** 1 ad → N chunks; aggregate at theme/sentiment/role grain, never
  sum ad metrics across the bridge's N chunks.

## 6. Action on failure — summary

Quarantine-not-retry is the default for any row-level failure (gates 1–2, §1): retrying a
non-deterministic LLM call on the same input burns API spend for no reliability gain. The
only path that can fail a **deploy** (not a row) is the golden-dataset gate, and that
routes to human review, never auto-retry.

---

## Sign-off Gate

| Agent | Status | Reason | Date |
|-------|--------|--------|------|
| @data-architect | ✅ APPROVED (doc-gap convene) | Narrative consolidation, no new gate logic invented; open items flagged honestly | 2026-06-22 |
| @scope-guardian | ✅ APPROVED (doc-gap convene) | Documents existing/already-planned gates only; does not implement TODOs #2/#3 | 2026-06-22 |
| @data-quality-steward | ⬜ PENDING | Drafted by doc-gap convene; awaiting direct review by the suite owner | — |
