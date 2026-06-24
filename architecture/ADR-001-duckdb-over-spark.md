# ADR-001 — DuckDB + dbt over (local) PySpark for the transform layer

- **Status:** Accepted · Amended 2026-06-22 by [ADR-005] on the *storage + serving* axis only ·
  **SUPERSEDED 2026-06-24 by [ADR-008]** on the *transform-engine* axis itself — this repo
  (`migration_creative_intelligence_lab`) now runs PySpark/Fabric notebooks, not DuckDB. The
  reasoning below is kept verbatim as the historical record of why DuckDB was chosen at the
  time; it no longer governs this repo's engine choice. (The sibling repo
  `creative_intelligence_lab` is unaffected — DuckDB still stands there.)
- **Date:** 2026-06-20
- **Deciders:** @data-architect (ratified), @senior-data-engineer, @data-platform-engineer, @finops-agent
- **Context refs:** `DATA_MODEL.md` §8 (stack), `STACK_AND_FLOW.md` §1, round-1 debate Q7
- **Scope:** the Bronze → Silver → Gold transform/ELT layer of the Creative Intelligence pipeline.
  Does **not** cover the Gemini extraction step (an external API call, engine-agnostic).

## Context

The Creative Intelligence pipeline turns messy advertising video into a queryable
graph + chunk feature store (+ a v1.5 within-winners performance-correlation layer). The
structured data that the transform layer processes is small:

- Chunk rows: tens of chunks per video × tens-to-thousands of videos = **KB–MB**, thousands
  to low-hundreds-of-thousands of rows.
- Performance rows: 3–15 winning ads × a few platforms × daily snapshots = **trivial**.

The only expensive, slow, unparallelizable step in the whole pipeline is the **Gemini API
call** per video — which no SQL/compute engine accelerates.

The owner's résumé features PySpark prominently, creating a pull toward using Spark here for
portfolio reasons. This ADR records why that pull is resisted for the transform layer, and the
honest path to demonstrate Spark instead.

## Decision

Use **DuckDB + dbt-duckdb** for the Bronze → Silver → Gold transform layer. Do **not** use
PySpark (local or cluster) for this layer.

## Rationale

1. **The data fits in memory many times over.** Spark's core value is distributed shuffle over
   data too large for one machine. At KB–MB scale there is nothing to distribute. DuckDB is an
   in-process, vectorized OLAP engine purpose-built for single-node analytical workloads of
   exactly this size, and is faster here than Spark because it skips JVM startup, task
   scheduling, and serialization overhead.

2. **`local[*]` is the worst of both worlds.** PySpark in local mode runs on a single machine:
   it incurs all of Spark's overhead (JVM, driver/executor memory tuning, serialization) while
   delivering none of Spark's benefit (distribution, which only materializes on a cluster over
   big data). You pay the tax without receiving the service.

3. **The bottleneck is the API call, not compute.** Bronze→Silver→Gold is light transformation
   work. Wrapping it — or the Gemini HTTP round-trip — in a Spark executor adds zero throughput.
   Engine choice for the transform layer is decided by friction, not horsepower, and DuckDB has
   far less.

4. **Operational friction.** DuckDB: `pip install duckdb`, reads S3 parquet directly via the
   `httpfs` extension, embeds in the Python process, first-class mature `dbt-duckdb` adapter,
   instant iteration. Local PySpark: JVM, SparkSession setup, driver/executor memory tuning,
   Hadoop S3A connector configuration, a heavier `dbt-spark` thrift/session setup, and JVM
   warmup on every `dbt run`. For a single-developer build this is days of yak-shaving for no
   payoff.

5. **Cost / footprint.** DuckDB has near-zero idle cost and the smallest viable footprint,
   consistent with the project-wide FinOps stance (no always-on cluster/warehouse for a
   <10K-video workload).

6. **Seniority signal.** Spark-on-small-data is a recognizable over-engineering tell. Choosing
   the right-sized tool *and being able to articulate why* is a stronger portfolio signal than
   reflexively reaching for Spark. The differentiator of this project is LLM extraction + graph
   modelling + non-deterministic-output testing — not faux big-data.

## Rejected alternatives

| Alternative | Why rejected |
|-------------|--------------|
| **Local PySpark (`local[*]`)** | All Spark overhead, none of the distribution benefit, at a data size that fits in RAM. Slower iteration, more config, weaker signal. |
| **Spark on a managed cluster (Databricks/EMR)** | Idle cluster cost dwarfs the actual workload; an always-on anti-pattern at this scale (round-1 §7, FinOps). |
| **Snowflake / always-on warehouse** *(as the TRANSFORM engine — still rejected)* | DuckDB remains the transform engine; this is unchanged. **However, ADR-005 (2026-06-22) admits Snowflake as a read-only SERVING veneer over Gold S3** (Cortex Search + Power BI) — a different axis from this ADR. The idle-cost objection is bounded there by a disposable trial + a day-25 teardown discipline, with Gold S3 remaining the sole source of truth. |
| **Pandas-only (no DuckDB)** | Works at this size, but loses SQL ergonomics, dbt-native modelling, and direct S3/parquet reads; DuckDB is strictly better for an ELT-shaped layer. |

## When Spark WOULD be the right call (revisit triggers)

- A genuine big-data leg is added where the data is actually large and embarrassingly parallel —
  e.g. **perceptual video-frame hashing** or raw-frame processing at GB–TB scale. That is a
  separate component, not the transform layer, and Spark earns its cost there.
- Structured volume grows past single-node comfort (sustained billions of rows / shuffle-bound
  joins) — revisit with @data-architect TCO sign-off.

If Spark is wanted purely for portfolio demonstration, the honest pattern is a **fenced,
clearly-labelled `local[*]` demonstration track** on a leg where the data is real-sized — shown
as "capability demonstration," never presented as the production choice for this transform layer.

## Consequences

- **Positive:** minimal setup, fast iteration, near-zero idle cost, first-class dbt integration,
  a defensible and articulable architecture decision.
- **Negative / accepted:** does not, by itself, exhibit PySpark on the résumé. Accepted — Spark
  is demonstrated honestly via a separate real big-data leg (above), not by over-fitting this
  layer.
- **Locked:** the transform-layer engine is DuckDB + dbt-duckdb. Adding Spark anywhere requires
  a new ADR citing one of the revisit triggers.
