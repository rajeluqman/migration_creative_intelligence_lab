# DATA MODEL & ARCHITECTURE OF RECORD — Creative Intelligence Pipeline

**Owner:** @data-architect · **Status:** Ratified 2026-06-20 (cabinet convene)
**Source of truth for rulings:** `../debate/DEBATE_LOG.md`

> **Paradigm (locked):** Asset-lineage **graph + chunk feature store**
> (+ vector index *beside* the relational model, v2). **NOT** a Kimball star.
> Governing principle: *model the domain you actually have, not the one your resume wants.*

---

## 1. Conceptual model

Two first-class entities and two graph-natured relationships:

```
        ┌────────────────────┐        parent_asset_id (self-edge)
        │      ASSET         │◄──────────────────────────────┐
        │ (raw OR edited     │   RAW ──"cut into"──► EDITED   │
        │  creative video)   │───────────────────────────────┘
        └─────────┬──────────┘
                  │ 1 asset → N chunks  (fan-out in Silver)
                  ▼
        ┌────────────────────┐    compatible_with (chunk↔chunk edge)
        │       CHUNK        │◄──────────────────────────────┐
        │ (one standalone    │   "what theme can follow this" │
        │  marketing beat)   │───────────────────────────────┘
        └────────────────────┘
```

- **ASSET** — a creative video, raw or edited. `parent_asset_id` is a **discovery
  lineage** edge (RAW→EDITED), used to "find more clips like this winning edit." It is
  **NOT** a performance-attribution edge (see §6 / Veto 1).
- **CHUNK** — the unit of value: a semantically complete marketing beat (Hook, Problem,
  Solution, Social Proof, CTA…) that can stand on its own. **Grain of the whole model.**
- **chunk↔chunk compatibility** — the adjacency that powers safe mix-and-match and
  prevents "Frankenstein content" (problem P3).

Every asset belongs to exactly one **CLIENT** (`dim_client`, ADR-006) — the tenancy
boundary. Asset identity is scoped to the client (`(client_id, content_sha256)`), so two
clients delivering byte-identical footage do not collapse into one asset.

## 2. Grain

**One row = one semantic chunk** (`chunk_id`). Not one row per video, not per timestamp
slice. Chunks are emitted by Gemini as meaning-bounded segments (not fixed 10s cuts),
each carrying `chunk_theme`, `sentiment`, `standalone_score` (1–5), `next_compatible_themes[]`.

## 3. Medallion layers & the immutability contract

| Layer | Object | Content | Rule |
|-------|--------|---------|------|
| **Landing** | `landing/<client_id>/video/<asset_id>.<ext>` | original video **bytes** | write-once; **the only place full binary lives**; content-hash named; **client-partitioned (ADR-006)**; **TTL-purged at `dim_client.landing_ttl_days`, default 30d (ADR-007)** |
| **Bronze** | `bronze/<client_id>/asset_raw/<asset_id>.parquet` | verbatim Gemini JSON | append-only, **immutable, forever**; + `model_version`, `content_sha256`, `load_ts`; **no business logic** |
| **Silver** | `silver_chunk` | flattened, conformed chunk rows | **chunking happens here**; filler removed, timestamps normalized; GE schema + range gates |
| **Gold** | `dim_client`, `dim_asset`, `fact_chunk`, `bridge_asset_lineage`, `bridge_chunk_compatibility`, `dim_keyword_bridge`/`dim_theme_bridge` | query-shaped feature/graph tables | arrays exploded → **no array columns in Gold** |

**Why chunking lives in Silver, not Bronze:** Bronze must stay the verbatim, immutable
Gemini response so any downstream re-model is a **re-parse, never a re-pay** (cost firewall,
§9). Chunking is a transformation → Silver. Gold would be too late (it already models
relationships *between* chunks). **Why video bytes never enter the lake:** binary store and
analytical store are separated; the lake holds metadata + transcripts + **pointers**
(`s3_uri` + `start_ts` + `end_ts`) so apps can seek into the original for playback without
the warehouse ever storing frames.

**Landing TTL exception + the frozen-asset consequence (ADR-007).** Landing is write-once
but **not retained forever**: aged non-golden landing videos are **hard-deleted at
`landing_ttl_days`** by a guarded-delete process (golden-prefix-exempt; deletes only after
the asset's Bronze JSON is confirmed present). **Consequence (named, accepted):** once an
asset's landing bytes are deleted it is **FROZEN at its last extraction** — re-EXTRACTION
(re-pay Gemini on a new prompt/model) is permanently impossible for it; only **re-parse from
the immutable Bronze JSON** survives. This does **not** breach the §9 firewall: Bronze is
forever and re-parse is always free — what is surrendered is the separate *re-extract
optionality*, consciously given up everywhere except the permanently-exempt **golden set**.

## 4. Logical schema (Gold)

### `dim_client` (tenancy dimension — ADR-006)
| column | type | notes |
|--------|------|-------|
| `client_id` (PK) | VARCHAR | short stable slug; also the S3 partition token |
| `client_name` | VARCHAR | display name |
| `account_support_owner` | VARCHAR | internal relationship owner |
| `drive_folder_id` | VARCHAR | the client's source Google Drive folder |
| `landing_ttl_days` | INT | per-client landing retention (feeds ADR-007 guarded delete) |
| `status` | VARCHAR | `active` \| `paused` \| `offboarded` |

Grain = **one client account.** SCD0 reference (immutable `client_id`; descriptive columns
hand-curated via seed). One domain = one dimension — client attributes never overload
`dim_asset` (Clean-ERD axis 2). Sourced from `seeds/dim_client.csv`, not the manifest.

### `dim_asset` (node)
| column | type | notes |
|--------|------|-------|
| `asset_id` (PK) | VARCHAR | **`SHA-256(client_id ':' content_sha256)`** — tenant-scoped content identity (ADR-006) |
| `client_id` (FK→dim_client) | VARCHAR | tenancy boundary; **NOT NULL** |
| `content_sha256` | VARCHAR | raw SHA-256 of video **bytes**, kept as a **separate non-key** column for **intra-client** near-dup detection |
| `parent_asset_id` (FK→self) | VARCHAR | RAW→EDITED **discovery lineage only**; NULL for raw |
| `asset_name` | VARCHAR | original filename |
| `asset_type` | VARCHAR | `RAW` \| `EDITED` |
| `duration_sec` | INT | |
| `source_uri` | VARCHAR | pointer to `landing/<client_id>/video/...` |
| `dq_flag` | VARCHAR | e.g. `likely_near_dup` (MEDIUM signal, no auto-merge) — derived from `content_sha256` collisions **within a client** |
| `ingested_at` | TIMESTAMP | **provenance** — when the bytes landed in S3 from Drive; immutable, write-once at landing, never recomputed on re-parse (ADR-006 impl, @data-architect 2026-06-22) |
| `load_ts` | TIMESTAMP | **audit** — when this dimension row was last (re)built by dbt; volatile, distinct from `ingested_at` |

> **Identity (ADR-006):** `asset_id = SHA-256(client_id || ':' || content_sha256)`. Still
> deterministic and content-addressed (same client + same bytes → same id), so the Bronze
> path, `stg_gemini_raw`, and every `asset_id` FK keep working unchanged — but two **different**
> clients' identical bytes now resolve to two **different** assets. `content_sha256` survives
> as its own column so within-client de-dup is unaffected.

### `fact_chunk` (feature row — grain = one chunk)
| column | type | notes |
|--------|------|-------|
| `chunk_id` (PK) | VARCHAR | |
| `asset_id` (FK→dim_asset) | VARCHAR | client reached by join `→ dim_asset.client_id` — **not stored here** (axis 4) |
| `chunk_sequence` | INT | order within asset |
| `start_ts` / `end_ts` | TIME | Gemini-set semantic boundaries (not hardcoded) |
| `transcript_segment` | TEXT | cleaned dialogue |
| `chunk_theme` | VARCHAR | Hook / Problem / Solution / Social Proof / CTA … |
| `sentiment` | VARCHAR | enum-bounded |
| `standalone_score` | INT | **1–5, GE range-gated** — safe-to-reuse-alone score |

> **`client_id` is NOT a stored column on `fact_chunk`** (Clean-ERD axis 4). It is reached by
> join (`asset_id → dim_asset.client_id`); if a serving surface needs it pre-joined for filter
> performance, expose it on a **VIEW**, never as a stored fact column.

### `bridge_chunk_compatibility` (chunk↔chunk edge — explodes `next_compatible_themes[]`)
| column | type | notes |
|--------|------|-------|
| `chunk_id` (FK) | VARCHAR | |
| `compatible_theme` | VARCHAR | one row per chunk per compatible theme |
| `theme_match_score` | DECIMAL | optional ranking |

### `bridge_asset_lineage` (asset↔asset edge)
| column | type | notes |
|--------|------|-------|
| `parent_asset_id` (FK) | VARCHAR | RAW |
| `child_asset_id` (FK) | VARCHAR | EDITED |

### `dim_keyword_bridge` / `dim_theme_bridge`
One row per chunk per keyword/theme — arrays exploded for queryability (no `ARRAY` columns
survive into Gold).

> **`fact_ad_performance` is NOT in v1** — it is a **v1.5 object** (ADR-004 converted the
> round-1 veto, see §6). Grain: 1 edited ad × 1 platform × 1 day; attaches to the EDITED
> asset that actually ran. Full schema: `DATA_MODEL_v1.5_PERFORMANCE.md` + `ERD_consolidated.md`.

## 5. dbt materialization path

```
seeds: dim_client (tenancy reference, SCD0)
sources: bronze_asset_raw (raw Gemini JSON)
  → stg_gemini_raw        -- flatten JSON; grain = asset_id + chunk_sequence
  → int_chunk_cleaned     -- filler removal, timestamp normalize, score passthrough
  → marts (Gold):
        dim_client                       (from seed)
        dim_asset                        (client_id FK → dim_client)
        fact_chunk                       (+ dbt_expectations range gate 1..5)
        bridge_chunk_compatibility       (explode next_compatible_themes[])
        bridge_asset_lineage
        dim_keyword_bridge / dim_theme_bridge
```
Tests: `unique`+`not_null` on `chunk_id`; `unique` on (`asset_id`,`chunk_sequence`);
`relationships` FK integrity (`fact_chunk.asset_id`→`dim_asset`, `dim_asset.client_id`→`dim_client`);
`dbt_expectations` range on `standalone_score`.

## 6. Vetoes embedded in the model

1. **Backward performance-propagation onto RAW via `parent_asset_id` → PERMANENTLY VETOED.**
   Raw clip A did not convert; edited clip B (possibly 10% A's footage + 9 other sources)
   did. Attributing B's conversions back to A manufactures causality. `parent_asset_id` is
   retained as a **navigation** relationship only. *Principle: a model must not encode an
   inference as if it were a fact — provenance before propagation.* — **Note:**
   `fact_ad_performance` itself is **not** vetoed: ADR-004 converted (not reversed) the
   round-1 veto into a v1.5 object attached to the EDITED ad that actually ran, never
   propagated backward. See `DATA_MODEL_v1.5_PERFORMANCE.md`.
2. **Flat Gold table → REJECTED.** A flat table discards `bridge_chunk_compatibility` — the
   entire anti-Frankenstein value and the literal mechanism of the north-star query.
   **Graph-from-start**, even on 5–10 videos (the graph is trivially small; the demo is
   gated by Gemini API throughput, not by the join).
3. **Asset removal / re-curation → deliberately OUT for v1 (ADR-006).** When support staff
   remove a video from a client's curated Drive folder, the asset leaves the client's
   *current curated set* — but Landing/Bronze stay append-only and immutable: **removal never
   deletes Bronze.** The v1.5 home for this is `bridge_client_asset_curation` (SCD2 membership
   of an asset in a client's current curated set). Named here so it is a deliberate deferral,
   not an accidental gap.
4. **`client_id` as a stored column on `fact_chunk` → REJECTED (ADR-006).** Reached by join
   (`asset_id → dim_asset.client_id`); promoted to a serving VIEW only on query proof, never
   stored on the fact (Clean-ERD axis 4).

## 7. Quality gates (LLM non-determinism)

The novel risk: **Silver is "unreliable narration"** — a row can be schema-valid yet
semantically wrong. Four gates, cheapest-first:

1. **CRITICAL — JSON-schema gate** (Bronze→Silver): malformed/truncated → **quarantine**, never blocks batch.
2. **CRITICAL — business-constraint gate**: `1<=standalone_score<=5`, enum `sentiment`, non-empty `chunk_theme` → **quarantine the row, do not retry** (retrying non-deterministic input just burns API spend).
3. **HIGH — golden-dataset gate**: ~30–50 (pilot: 5) hand-labeled videos, re-run on every prompt/model change, require **≥80% semantic agreement (Jaccard, ±1 on score)** — **the only gate allowed to fail a deploy**, and only at the *pipeline* level, never per-row. On fail → human review, not auto-retry. **Golden videos are TTL-exempt (ADR-007 Condition 1)** so this gate stays permanently re-runnable.
4. **MEDIUM — idempotency gate**: same `asset_id` reprocessed → drift beyond tolerance is a **signal, not a block** (LLM variance is expected).

Promotion rule: **Silver constraint-pass ≥95% before Gold build.**

## 8. Stack (locked at this scale)

| Concern | Choice | Why |
|---------|--------|-----|
| Landing transport | Python (Drive API → S3) | content-hash naming, write-once, client-partitioned |
| Transcription/extraction | **Gemini API (Flash-first)** | per-second video billing; Flash 10–15× cheaper than Pro |
| Storage | **S3** (video bytes) + S3 (Bronze/Silver/Gold parquet) | pay-per-GB, zero idle |
| Compute / transforms | **DuckDB + dbt-duckdb** | KB–MB structured scale; bottleneck is the API call, not CPU |
| Orchestration | **local Airflow** — deferrable operators + triggerer, `gemini_api` Pool sized to QPM, backoff+jitter on 429, dynamic task mapping `expand()` per `asset_id`, skip-existing short-circuit on hash, **+ scheduled landing-TTL guarded-delete task (ADR-007)** | async/rate-limit-bound; synchronous PythonOperator polling would pin worker slots |
| Quality | **Great Expectations** + dbt tests | per-layer gates above |
| Demo serving | **Snowflake Cortex** veneer over Gold S3 (Cortex Search + Power BI); **DuckDB VSS = $0 fallback** | satisfies north-star (ADR-005) |

**REJECTED at this scale:** Spark / Databricks / MWAA — over-engineering and idle-cost
anti-pattern for <10K videos. *(Revisit only if @data-architect justifies long-term TCO at
materially higher volume.)*
**ADMITTED by ADR-005 (owner override 2026-06-22):** Snowflake Cortex as a **read-only serving
veneer** over Gold S3 (disposable trial + day-25 teardown; Gold S3 stays sole source of truth).
Storage is now unified S3 (no MinIO).

## 9. Cost firewall

- Spend cliff = **Gemini API tokens** (video ~258–300 tok/sec): 40 vids ≈ $1–5,
  500 ≈ $20–150, 5000 ≈ $200–1500+. Storage/compute are noise by comparison.
- **Controls:** (a) Bronze keeps raw Gemini JSON **forever** → every re-model is re-parse,
  never re-pay; (b) idempotent **client-scoped skip-existing on `(client_id, content_sha256)`**;
  (c) **Flash-first** model choice.
- **Firewall vs. landing TTL (ADR-007):** the TTL hard-deletes only *landing video bytes*,
  never Bronze JSON — so "re-parse, never re-pay" is **fully preserved**. What the TTL
  surrenders is the *separate* re-EXTRACT (deliberately re-pay on a new prompt/model)
  optionality, given up for all but the golden set.

## 10. v1 scope line (agreed)

**IN:** Drive → S3 landing (client-partitioned) → Bronze (tenant-scoped-content-deduped raw
Gemini JSON) → Silver (gated semantic chunks) → Gold (`dim_client` + chunk feature store +
`dim_asset` + lineage & compatibility bridges) → **one SQL/text search demo** returning sane,
timestamped, standalone-scored clips over 5–10 videos. Multi-client tenancy (`dim_client`,
tenant-scoped `asset_id`) is IN (ADR-006); landing TTL guarded-delete is IN (ADR-007).

**OUT (BACKLOG):** all 4 downstream apps (search-engine UI, RAG generator, ops dashboard,
auto-archiver), vector DB, ad-performance ingestion, perceptual/fuzzy dedup,
`fact_ad_performance`, **asset removal / re-curation tracking (`bridge_client_asset_curation`,
v1.5 — ADR-006 §F)**.
