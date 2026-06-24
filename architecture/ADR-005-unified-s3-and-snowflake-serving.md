# ADR-005 — Unified S3 canonical storage + Snowflake Cortex serving veneer

- **Status:** Accepted (owner override; ratified-with-conditions by @data-architect) ·
  **SUPERSEDED 2026-06-24 by [ADR-008]** — storage moves S3 → OneLake, serving moves Snowflake
  Cortex/DuckDB VSS → Power BI Direct Lake + Fabric Copilot. Kept verbatim as the historical
  record of the S3+Snowflake decision; does not govern this repo's storage/serving choice
  anymore. (The sibling repo `creative_intelligence_lab` is unaffected.)
- **Date:** 2026-06-22
- **Deciders:** owner (override), @data-architect (ultimate veto — conditional approve),
  @finops-agent (co-sign on teardown), @scope-guardian (boundary-override recorded),
  @senior-data-engineer (buildability)
- **Amends:** ADR-001 (storage + serving axis only — DuckDB stays the transform engine),
  `STACK_AND_FLOW.md` §1 (serving row + "rejected at this scale" list), `CLAUDE.md` stack boundary.
- **Does NOT touch:** ADR-002 (graph over star), ADR-003 (chunking in Silver), ADR-004
  (perf-veto) — the data model is unchanged (two facts, the bridges, SCD all intact).

## Context
Owner directive (2026-06-22): make **S3 the single unified storage substrate** for the whole
pipeline (landing → bronze → silver → gold), and serve via **Snowflake Cortex**. Cost is covered
by a Snowflake 30-day / $400 trial and low-cost AWS S3. The earlier cabinet "local-first /
MinIO-for-dev" recommendation and the ADR-001/`STACK_AND_FLOW` "no always-on Snowflake" line are
overridden by the owner. Two technical facts from the convene shaped the final form:
1. Snowflake external tables **cannot read MinIO** — so a unified surface must be real S3, not MinIO.
2. v1 Gold is still stubs — serving is **sequenced after** Gold emits real rows; no provisioning yet.

## Decision

### A — Unified S3 storage (no MinIO)
- **All layers persist to S3.** `landing/`, `bronze/`, `silver/`, `gold/` are S3 prefixes.
  Silver/Gold dbt models materialize as **`external` parquet** on S3, read via DuckDB `httpfs`.
- **MinIO is dropped entirely.** Its only benefit was free offline dev; credits cover real S3,
  and it cannot back Snowflake. Dev, staging, and (future) troubleshooting drills all use **real
  S3 buckets** — a separate staging/throwaway bucket for any drill/overwrite work, never the
  canonical bucket.
- **DuckDB = compute only.** The DuckDB catalog is ephemeral (in-process); it is never the truth.

### B — Snowflake Cortex serving (read-only veneer over Gold S3)
- Snowflake **external tables** over `gold/` S3 (read-only) + **Cortex Search** for semantic/
  vector search + **Power BI** for BI. This is the showcased serving demo.
- **Embeddings = bring-your-own (Gemini), generated in the ELT and persisted in Gold S3** —
  NOT Cortex `EMBED_TEXT`. Reason: keep the one content-hash skip-existing idempotency gate the
  pipeline already has; never create a second metered embedding surface (FinOps + senior-DE).
- **DuckDB VSS over the same Gold S3 is retained as the $0 fallback / default serving path.**
  DuckDB reads S3 via httpfs, so the fallback needs no MinIO. This is what a fresh clone (or the
  post-trial demo) runs.

## THE SOURCE-OF-TRUTH BOUNDARY (the spine — do not overwrite)
**Gold S3 parquet is the sole source of truth. Snowflake is a read-only projection.**
- No Gold fact may exist only in Snowflake. The whole veneer must be reconstructible from
  S3 Bronze→Silver→Gold.
- A **reconciliation test** gates the serving layer: Snowflake external-table row counts + key
  sets must exact-match the DuckDB-over-S3 read of the same Gold parquet.
- 🛑 @data-architect veto re-fires if Snowflake becomes a second source of truth (a Snowflake-only
  fact, a CTAS-internal copy that diverges, or a KPI persisted in Snowflake not reproducible from S3).

## Cost discipline (FinOps co-sign — hard preconditions before any Snowflake provisioning)
1. `COST_LOG.md` records the trial start date + a **day-25 teardown reminder** (not day-30).
2. The **$0 fallback demo is built and proven BEFORE the trial clock starts** — DuckDB VSS path
   (or a recorded screen-capture), so the portfolio never depends on a live trial.
3. Embeddings single-sourced (BYO Gemini, content-hash-gated) — no re-embed on unchanged chunks.
4. Cortex Search is **suspended/dropped when idle**; it bills wall-clock, not per-query.
- Killing Snowflake at trial-end = **$0 loss** (truth is on S3). Re-provision later = re-run the
  capture-as-code provisioning script against the same S3 prefix, not a backfill.

## Consequences
- **Positive:** one storage surface (simpler than dual local/MinIO); real Snowflake + Cortex +
  Power BI portfolio story; truth stays cheap + permanent on S3; veneer is disposable.
- **Negative / accepted (owner-accepted):** the project is **no longer fully standalone / offline-$0**
  while built against real S3 — a fresh clone needs AWS credentials to run the ELT, and needs a
  funded Snowflake account to run the *Snowflake* serving demo (the DuckDB-VSS fallback keeps the
  core feature store runnable at $0 given S3 read access). The CLAUDE.md "no Snowflake in v1"
  hard-limit line is amended by this ADR, not silently breached.
- **Provisioning stays owner-gated:** any `aws s3 mb` / Snowflake `CREATE` is confirmed by the
  owner before execution.
- **Sequencing:** serving is built **after** v1 Gold emits real rows. Building Cortex Search over
  empty stub Gold is out of order; the 30-day clock does not justify it.
