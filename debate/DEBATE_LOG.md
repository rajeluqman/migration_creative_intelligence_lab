# DEBATE LOG — Creative Intelligence Pipeline Cabinet Convene

**Date:** 2026-06-20
**Facilitator:** @data-architect (ULTIMATE VETO on data model + architecture)
**Format:** 9 borrowed cabinet personas argued their lane on the agenda
(`00_AGENDA.md`); @data-architect ruled on each question and ratified an
Architecture of Record (AoR).
**Note:** Borrowed-agents convene only. No gym ADRs, sign-off logs, or pharma
artifacts were touched. This project is independent.

---

## Panel positions (condensed, as argued)

### @business-analyst — Q3 (lineage & performance)
- `fact_ad_performance` = **v1 STUB, not build**. Owner stated this is a searchable
  feature store, NOT a ROAS/media-buying tool; perf data is "often absent".
- Proxy attribution (raw inherits edited child's conversions) = **manufactured
  causality** — a marketer screenshotting "this raw clip drove $40K" from an inherited
  number is a credibility incident, not a feature. 🛑 not testable as stated.
- Keep `parent_asset_id` for **discovery lineage only** ("find more clips like this"),
  never performance inheritance.
- Real day-one questions are all search / mix-match (theme, hook, sentiment,
  standalone_score) — none are ROAS.

### @senior-data-engineer — Q1/Q4/Q5/Q7
- **Not a Kimball star** — it's an **asset-lineage graph + feature store**. A star needs
  additive facts at a stable grain over conformed dims; here "facts" are LLM opinions and
  the query pattern is graph traversal. Forcing a 4th conformed dim to "look Kimball" is
  dishonest engineering an interviewer will smell.
- Build: `dim_asset` (node + `parent_asset_id`), `fact_chunk` (feature row keyed by
  `chunk_id`), `bridge_chunk_compatibility` (edge). Vector index sits **beside**, not inside.
- **Grain = semantic chunk. Chunking lives in SILVER.** Bronze = verbatim immutable Gemini
  JSON + `model_version` (chunking in Bronze loses replay-without-repay; Gold is too late).
- Boundaries: Bronze `bronze_asset_raw`; Silver `silver_chunk` (+GE gate); Gold `dim_asset`,
  `fact_chunk`, `bridge_asset_lineage`, `bridge_chunk_compatibility`.
- **Spark/Databricks = over-engineering** (KB-MB scale; the slow step is the API call,
  which Spark does nothing for). DuckDB + dbt is honest. Faux big-data is a resume tell.

### @analytics-engineer — Q1/Q4 (dbt materialization)
- dbt path: `stg_gemini_raw` (flatten, grain `asset_id+chunk_sequence`) → `int_chunk_cleaned`
  → marts.
- **ARRAY columns (`next_compatible_themes`, `keywords`) are a query-hostile smell** →
  explode into bridge tables (one row per chunk per theme/keyword); `dbt_expectations`
  range gate on `standalone_score`.
- Instinct to default to a star — **overruled by DA** (marts are feature/graph, not star);
  the dbt layering + array-explosion are adopted in full.

### @data-platform-engineer — Q5/Q7/Q8
- **Video bytes do NOT live in the analytical lake.** `landing/video/<asset_id>.<ext>`
  write-once is the sole full-binary location; lake holds metadata + transcripts +
  pointers (`s3_uri` + `start_ts`/`end_ts` for playback seek).
- DuckDB + dbt-duckdb compute. No Spark cluster for this volume.
- **Orchestration:** Airflow but **not synchronous PythonOperator per-video polling**
  (pins worker slots, exhausts pool >40 videos). Use **deferrable operators + triggerer**,
  a `gemini_api` **Pool** sized to QPM, **backoff + jitter on 429**, **dynamic task mapping
  `expand()`** one task per `asset_id`, **skip-existing** short-circuit. **Local Airflow,
  not MWAA.**

### @data-quality-steward — Q2/Q6
- **SHA-256 = CRITICAL identity** (blocks Bronze write on mismatch). Near-dups (2–3s diff)
  are a different question — get a **MEDIUM `dq_flag=likely_near_dup`** via cheap heuristic
  (filename stem + duration ±5s + folder), **not** perceptual hashing, **not** auto-merge.
  Perceptual dedup = v2.
- Unique risk: **Silver is "unreliable narration"** — schema-valid rows can be semantically
  wrong; schema gates are blind to it.
- **4 gates:** (1) JSON-schema → quarantine; (2) constraint `1<=standalone_score<=5` →
  quarantine row, don't retry; (3) golden-dataset ≥80% human-agreement → **only gate
  allowed to fail a deploy**; (4) idempotency drift = signal, not block. Silver
  constraint-pass **≥95% before Gold**.

### @qa-engineer — Q6 (execution)
- Deterministic gates (no flake): JSON-schema unit test, mock-data mix-match logic test
  (`standalone_score>=4` filter + `next_compatible_themes` chaining), idempotency test.
- Non-determinism: golden 5-video regression measuring **semantic overlap (Jaccard) ≥80%**,
  not byte-match; on fail → alert + human review, don't assume flake.
- Mock tests every PR (~2 min, ~$0); golden nightly/on-demand.

### @finops-agent — Q8/Q7
- **Cost cliff = API tokens**, not storage/compute (video ~258–300 tok/sec). 40 vids ≈
  $1–5; 500 ≈ $20–150; 5000 ≈ $200–1500+. **Model choice (Flash vs Pro, 10–15×) = first
  lever.**
- **"Keep raw Gemini JSON in Bronze forever" = the single most important cost control**
  (re-parse without re-pay) + idempotent skip-existing on hash.
- 🛑 Budget alert on any **always-on warehouse/cluster** for <10K videos — DuckDB + S3 +
  dbt + pay-per-call Gemini, zero idle compute.

### @scope-guardian — Q9 (VETO holder)
- 🛑 **VETOED** ad-performance ingestion (Fivetran/Airbyte/Meta API) + parent-child
  attribution fact table → BACKLOG.
- OUT of v1: all 4 downstream apps, vector DB, RAG generator, ops dashboard, auto-archiver,
  ad-perf ingestion, perceptual dedup, `fact_ad_performance`.
- Smallest impressive cut: Drive→S3→Bronze(hash-deduped)→Silver(chunks)→Gold(feature store
  + asset dim + lineage)→one SQL/text search demo.

### @product-owner — Q9/Q10
- **North-star story:** *"As a marketer, I paste a client's Google Drive folder link and
  search every video by spoken line / theme / sentiment, getting back timestamped clips
  with a `standalone_score` — so I know what's safe to reuse without re-watching 40 raw
  videos."*
- Done = that query returns sane results on 5–10 videos.
- Tension raised: would accept a **flat Gold table** if the graph delays the first demo.
- Roster: **6 agents** (max 7). Cut PM, BA, platform-eng, and all gym apparatus.

---

## @data-architect rulings (binding)

| Q | Ruling | Decision |
|---|--------|----------|
| Q1 Paradigm | **AMENDED** | Graph + feature store is AoR. Kimball star REJECTED as primary. Analytics-eng's star instinct overruled; its dbt layering adopted. |
| Q2 Identity | **APPROVED** | SHA-256 blocking identity; near-dup = MEDIUM flag, no auto-merge; perceptual dedup = v2. |
| Q3 Lineage/perf | **🛑 VETOED** | `fact_ad_performance` + proxy attribution = manufactured causality → BACKLOG. `parent_asset_id` kept for **discovery lineage only**. |
| Q4 Grain/chunking | **APPROVED** | Grain = chunk. Chunking in **Silver**. Arrays explode to bridges (no array columns in Gold). |
| Q5 Layer boundaries | **APPROVED** | Bronze verbatim/immutable; Silver chunks+gates; Gold graph tables. **Video bytes never enter the lake** — landing-only, pointers downstream. |
| Q6 LLM testing | **APPROVED** | 4 gates; golden ≥80% Jaccard = only deploy-blocker; Silver ≥95% before Gold. |
| Q7 Stack | **APPROVED** | DuckDB + dbt-duckdb + S3 + Gemini (Flash-first) + local Airflow (deferrable). Spark/Databricks/MWAA REJECTED at this scale. |
| Q8 Cost | **APPROVED** | Token cost is the cliff; Bronze-raw-forever + idempotent skip = controls. |
| Q9 Scope | **APPROVED** | v1 = ingest→Bronze→Silver→Gold→one search demo. All else BACKLOG. |
| Q10 Roster | **APPROVED+amended** | 6 core + qa-engineer on golden-dataset activation. |

### VETOES OF RECORD
1. **`fact_ad_performance` + proxy attribution → VETOED** (Q3). Reason: model must not
   encode an inference as if it were a fact. `parent_asset_id` survives as a *navigation*
   relationship only. Performance, if it ever lands, attaches to the EDITED asset that ran,
   behind a provenance/confidence qualifier — v2.
2. **Flat Gold fallback → REJECTED** (resolving the PO tension). A flat table is a
   *different model* that throws away `bridge_chunk_compatibility` — the entire
   anti-Frankenstein (P3) value and the literal mechanism of the north-star query. The
   graph is NOT what delays the demo (Gemini API throughput is); over 5–10 videos the graph
   is trivially small. **Graph-from-start. No flat-then-upgrade debt.** PO's done-definition
   adopted; PO's fallback overruled.

### Convergence ratified as Architecture of Record
senior-DE + platform-eng converged on **graph + feature store + DuckDB + Silver-chunking +
deferrable Airflow + binary-store-separate-from-lake** — ratified verbatim. See
`../architecture/DATA_MODEL.md`.
