# MIGRATION MAP — sibling repo → Microsoft Fabric

> **Purpose:** the binding, file-by-file port plan from `creative_intelligence_lab` (the real,
> working DuckDB/dbt/S3/Airflow build) to this Fabric repo. Built by reading every source file,
> not from memory — it exists *because* the F0 pass shipped docs only and silently skipped all
> ~1,522 lines of working code (`SESSION_LOG.md` 2026-06-24 "Honest gap audit").
>
> **How to use (port sessions, incl. Sonnet):** this is a CHECKLIST, not a suggestion. For each
> row: (1) open the source file in the sibling repo `../creative_intelligence_lab/<path>` and
> READ IT, (2) apply the treatment + translation notes, (3) write the Fabric target, (4) tick the
> box. Do **not** write a target from this map's summary alone — the map tells you *what* changes,
> the source file is still the source of truth for the logic. Re-run `tests/lineage_contract.py`
> + `tests/boundary_contract.py` after each file.

## Methodology (real migration, not rebuild-from-scratch)

Rebuild-from-scratch is the LAST resort — the sibling repo already paid for bugs (CRLF sniffer,
column-count, stale catalog, chunk-grain Bronze VETO, non-recursive folder walk) and rulings
(winning→EDITED, asset-grain Bronze, double-count guard). Rebuilding re-incurs them. So:

1. **Inventory & assess** — done (this file; 36 source artifacts).
2. **Classify** each artifact by treatment (table below).
3. **Map** each platform construct source→target (construct table below).
4. **Port** preserving business logic; translate only the platform layer.
5. **Parity test** against the sibling repo's real output (the golden baseline: **131 real
   chunks** from 13 assets, `dim_asset` 19 rows 14 EDITED/5 RAW — see the sibling repo's
   `PROJECT_STATUS.md` "First real Drive run"). Same input → same rows, modulo engine rounding.
6. **Cutover** — F4 serving + decommission note.

Treatments: **RETAIN** (copy verbatim, platform-agnostic) · **REPLATFORM** (keep logic, swap
I/O) · **REFACTOR** (structural translation) · **REBUILD** (no source, build fresh) ·
**RETIRE** (no Fabric equivalent, drop on purpose).

## Construct mapping (the translation table — applies everywhere)

| Source construct (DuckDB/dbt/S3/Airflow) | Fabric target | Notes |
|---|---|---|
| `boto3.client("s3")` + `s3.put_object/list/delete` | OneLake `Files/` I/O (`notebookutils`/`mssparkutils.fs`, or Spark write to abfss) | only the I/O call changes; keys/prefixes keep their shape under `Files/` |
| `s3://<bucket>/landing/<client>/video/<id>.<ext>` | `abfss://<ws>@onelake.dfs.fabric.microsoft.com/<lh>.Lakehouse/Files/landing/<client>/video/<id>.<ext>` | ADR-008; identity formula `asset_id = sha256("{client_id}:{content_sha256}")` UNCHANGED |
| `{{ ref('x') }}` | plain Lakehouse/Warehouse object name `x` | no Jinja; T-SQL/Spark resolve by name |
| `{{ source('bronze','bronze_asset_raw') }}` | Lakehouse `Files/bronze/...` read (Spark) | Bronze stays raw files, read in the Silver notebook |
| `{{ config(materialized='view') }}` / dbt table | Warehouse `CREATE VIEW` (Gold) / Delta table (Silver) | Gold = view always (ADR-008 Binding Condition 1) |
| DuckDB `unnest(array_col)` / `unnest(json_extract(...))` | **Silver:** Spark `explode(from_json(...))` | explode arrays in Silver so Gold T-SQL views never see array types over the shortcut |
| DuckDB `x ->> 'k'` / `x -> 'k'` (JSON) | Spark `from_json` + field access (Silver) | the Gemini-JSON explosion belongs in the Silver notebook, not a T-SQL view |
| DuckDB `val::double` / `::integer` | T-SQL `CAST(val AS FLOAT)` / `TRY_CAST(... AS INT)` | |
| DuckDB `median(x)` | T-SQL `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x) OVER (...)` | **no `median()` aggregate in T-SQL** — key change in `mart_chunk_perf_correlation` |
| `least(a,b)` / `greatest(a,b)` | T-SQL `LEAST/GREATEST` (supported) else `CASE` | overlap calc in `int_metric_chunk_alignment` |
| `join ... using (col)` | `join ... ON a.col = b.col` | T-SQL has no USING |
| `current_timestamp` | `SYSUTCDATETIME()` (T-SQL) / `current_timestamp()` (Spark) | |
| Airflow `@task` | Data Factory pipeline **activity** | |
| Airflow `.expand()` (dynamic mapping) | DF **ForEach** activity | one iteration per new asset |
| Airflow `gemini_api` Pool | DF ForEach `batchCount` (concurrency cap) | the rate-limit guard |
| Airflow `retries`/`retry_exponential_backoff` | DF activity **retry policy** | |
| Airflow `TimeDeltaSensorAsync` | DF **Wait** activity | |
| Airflow `BashOperator(dbt build)` | DF **Notebook** activity (run the Silver/Gold notebook) | |
| Airflow `AirflowSkipException` | DF **If Condition** activity (skip when no new assets) | |
| dbt schema test (`unique`/`not_null`/`relationships`/`accepted_values`) | Great Expectations expectation on the Silver Delta table | dbt dropped (ADR-008) |
| `dbt_expectations` range gate | GE `expect_column_values_to_be_between` | |

## Source inventory + treatment (the master checklist)

### A. Scripts (`scripts/*.py` → `notebooks/` and/or `scripts/`)

| # | Source (sibling repo) | Lines | Treatment | Fabric target | Port notes |
|---|---|---|---|---|---|
| ☐ A1 | `scripts/ingest_drive_to_s3.py` | 250 | REPLATFORM | `notebooks/01_ingest_drive_to_onelake.py` | KEEP: Drive API pull, `_list_videos` (recursive — bug fix), `_infer_asset_type` (winning→EDITED ruling), SHA-256 content hash, `asset_id` formula, skip-existing, manifest append, `ingested_at` one-event-per-run. CHANGE: `boto3`+`put_object`→OneLake Files write; `_s3_key`→`_onelake_path`; `_s3_exists`→OneLake exists; `source_uri` built as abfss. RENAME (no longer "to_s3"). |
| ☐ A2 | `scripts/run_gemini_extract.py` | 238 | REPLATFORM | `notebooks/02_extract_gemini.py` | KEEP (verbatim logic): `responseSchema`, `SENTIMENT_ENUM`, `_upload_and_wait_active` poll loop, **asset-grain Bronze** (the @data-architect VETO fix — one row/asset, verbatim `raw_response`), `chunk_count`, model/prompt-version stamping. CHANGE: Bronze write S3-parquet→OneLake `Files/bronze/...`; `_bronze_key`/`_parse_s3_uri`→OneLake. |
| ☐ A3 | `scripts/enforce_landing_ttl.py` | 115 | REPLATFORM | `scripts/enforce_landing_ttl.py` or `notebooks/` | KEEP: ADR-007's 3 binding conditions (golden exemption, Bronze guard, frozen-asset log), `dim_client` TTL lookup, **dry-run default + `--apply`**. CHANGE: boto3 list/delete→OneLake Files list/delete; prefixes keep shape under `Files/`. ADR-007 Status header already anticipates this. |
| ☐ A4 | `scripts/env_guard.py` | 16 | REPLATFORM | `scripts/env_guard.py` | CHANGE: check `FABRIC_WORKSPACE`/`FABRIC_LAKEHOUSE` instead of `S3_BUCKET`. Keep fail-closed pattern. |
| ☐ A5 | `scripts/significance_post_step.py` | 3 | REBUILD | `scripts/significance_post_step.py` | Stub even in sibling repo. Build fresh per `SPEC_v1.5_performance_marts.md` §6: Warehouse query → pandas → scipy Mann-Whitney U + Bonferroni, SUGGESTIVE tier only. No real source to port. |

### B. dbt models — Silver layer (`models/staging/*`, `models/intermediate/*` → PySpark notebook)

Silver = row-level clean/conform → Delta tables, in PySpark notebook(s). NOT T-SQL views.

| # | Source | Lines | Treatment | Fabric target | Port notes |
|---|---|---|---|---|---|
| ☐ B1 | `models/staging/stg_gemini_raw.sql` | 24 | REFACTOR | Silver notebook cell → `silver_chunk` Delta | **Heaviest translation.** DuckDB `unnest(json_extract(raw_response,'$.chunks'))` + `->>`→ Spark `explode(from_json(raw_response schema).chunks)`. KEEP: deterministic `chunk_id = asset_id||'_'||lpad(seq,3)`, the array cols `next_compatible_themes`/`keywords` (keep as Spark arrays into Silver, explode for Gold bridges). |
| ☐ B2 | `models/staging/stg_meta_perf.sql` | 7 | REPLATFORM | Silver notebook cell | Trivial filter+select `where platform_native='meta'`. Spark `.filter().select()`. |
| ☐ B3 | `models/staging/stg_tiktok_perf.sql` | 7 | REPLATFORM | Silver notebook cell | As B2, `'tiktok'`. |
| ☐ B4 | `models/intermediate/int_chunk_cleaned.sql` | 7 | REPLATFORM | Silver notebook cell | Passthrough select (filler-removal logic is a TODO even in source). |
| ☐ B5 | `models/intermediate/int_ad_perf_unioned.sql` | 4 | REPLATFORM | Silver notebook cell | `union all` + platform tag → Spark `unionByName`. |

### C. dbt models — Gold layer (`models/marts/**` → `warehouse/**/*.sql` T-SQL views)

Gold = T-SQL `VIEW`s in the Warehouse over the OneLake shortcut. Never materialized tables (ADR-008 BC1).

| # | Source | Lines | Treatment | Fabric target | Port notes |
|---|---|---|---|---|---|
| ☐ C1 | `models/marts/core/dim_asset.sql` | 17 | REPLATFORM | `warehouse/core/dim_asset.sql` | From `asset_manifest` (Delta). `cast(null as varchar)`→`CAST(NULL AS VARCHAR)`; `current_timestamp`→`SYSUTCDATETIME()`. |
| ☐ C2 | `models/marts/core/fact_chunk.sql` | 6 | REPLATFORM | `warehouse/core/fact_chunk.sql` | Trivial select from `int_chunk_cleaned`. |
| ☐ C3 | `models/marts/core/bridge_chunk_compatibility.sql` | 6 | REFACTOR | `warehouse/core/bridge_chunk_compatibility.sql` | `unnest(next_compatible_themes)` — best done in Silver (explode), then Gold view is a plain select. Decide explode-location at B1. |
| ☐ C4 | `models/marts/core/dim_keyword_bridge.sql` | 2 | REFACTOR | `warehouse/core/dim_keyword_bridge.sql` | `unnest(keywords)` — same explode-in-Silver decision as C3. |
| ☐ C5 | `models/marts/core/dim_theme_bridge.sql` | 2 | REPLATFORM | `warehouse/core/dim_theme_bridge.sql` | Trivial; no array. |
| ☐ C6 | `models/marts/core/bridge_asset_lineage.sql` | 4 | RETAIN (stub) | `warehouse/core/bridge_asset_lineage.sql` | `where 1=0` stub in source — port as `WHERE 1=0` stub; population mechanism still unspecified (STTM open item). |
| ☐ C7 | `models/marts/core/fact_extraction_run.sql` | 13 | RETAIN (stub) | `warehouse/core/fact_extraction_run.sql` | `where 1=0` stub; telemetry, populated from extract notebook's run log later. |
| ☐ C8 | `models/marts/performance/fact_ad_performance.sql` | 12 | REPLATFORM | `warehouse/performance/fact_ad_performance.sql` | Joins port; `using`→`ON`; `current_timestamp`→`SYSUTCDATETIME()`. |
| ☐ C9 | `models/marts/performance/fct_ad_kpi.sql` | 17 | REFACTOR | `warehouse/performance/fct_ad_kpi.sql` | `::double`→`CAST(... AS FLOAT)`; keep ratio-of-sums (CTE `agg` then divide), `nullif` guard ports as-is. |
| ☐ C10 | `models/intermediate/int_metric_chunk_alignment.sql` | 46 | REFACTOR | `warehouse/performance/int_metric_chunk_alignment.sql` | **Complex, high-value.** KEEP every CTE (`anchors`/`time_aligned`/`role_aligned`), the `row_number()` tie-break, the **double-count guard** (one chunk per ad×platform×metric). CHANGE: `::double`, `using`→`ON`, `least/greatest`, `values(...)` table-constructor → T-SQL `VALUES`/derived table. |
| ☐ C11 | `models/marts/performance/fct_ad_metric_chunk.sql` | 14 | REPLATFORM | `warehouse/performance/fct_ad_metric_chunk.sql` | `using`→`ON`; `case` ports. |
| ☐ C12 | `models/marts/performance/mart_chunk_perf_correlation.sql` | 16 | REFACTOR | `warehouse/performance/mart_chunk_perf_correlation.sql` | **`median()`→`PERCENTILE_CONT(0.5) WITHIN GROUP(...)`** (no T-SQL median). `rank() over`, `count(distinct)` port. KEEP the n<5 BLOCK / 5-11 DIRECTIONAL / ≥12 SUGGESTIVE gate + `honesty_note`. |

### D. Orchestration (`dags/*.py` → `pipelines/*.json`)

| # | Source | Lines | Treatment | Fabric target | Port notes |
|---|---|---|---|---|---|
| ☐ D1 | `dags/creative_intel_pipeline.py` | 136 | REFACTOR | `pipelines/creative_intel_fabric.json` | Structural translation per the construct table: `sync_drive_to_landing`/`list_new_assets`/`extract_chunks.expand()`/`await`/`dbt_build`/`ge_validate`/`refresh_serving` → DF activities (Notebook + ForEach + Wait + If Condition), retry policy, ForEach batchCount = the Gemini-QPM guard. KEEP the two cost-firewalls (skip-existing on hash; skip when no new assets) and the no-synchronous-polling design. |

### E. Build/config/analyses

| # | Source | Treatment | Fabric target | Port notes |
|---|---|---|---|---|
| ☐ E1 | `setup.sh` (546) | REBUILD | `setup.sh` | Scaffold `notebooks/` + `warehouse/` + `pipelines/` stubs + venv + `requirements.txt`; drop all dbt scaffolding (`models/`, `dbt_project.yml`, `profiles.yml`, `dbt deps/parse`). |
| ☐ E2 | `requirements.txt` | RESHAPE | `requirements.txt` | DROP `dbt-duckdb`, `duckdb`, `boto3`. KEEP `google-genai`, `google-api-python-client`, `google-auth`, `pandas`, `scipy`, `tqdm`, `ruff`, `great-expectations`. ADD OneLake/Fabric access lib if scripts run outside a notebook. |
| ☐ E3 | `.env.example` | RESHAPE | `.env.example` | DROP `S3_*`, `AWS_*`, `SNOWFLAKE_*`, `SERVING_BACKEND`. ADD `FABRIC_WORKSPACE=creative-intel-ws`, `FABRIC_LAKEHOUSE=creative_intel_lh`. KEEP `GEMINI_*`, `GOOGLE_APPLICATION_CREDENTIALS`, `DRIVE_FOLDER_ID`, `CLIENT_ID` (no default — multi-client guard). |
| ☐ E4 | `analyses/demo_queries.sql` (4) | REPLATFORM | `analyses/demo_queries.sql` | Pointer-stub in source; rewrite the 3 demo queries as T-SQL when Gold lands (SPEC_v1_search §2/§3, SPEC_v1.5 §8). |
| ☐ E5 | `dbt_project.yml`, `packages.yml`, `package-lock.yml`, `profiles.yml`, `profiles.yml.example` | **RETIRE** | — | dbt-specific; no Fabric equivalent. Deliberately not ported (their seed `+column_types` info, if still needed, is captured by GE expectations / Delta schema). |
| ☐ E6 | `requirements-airflow.txt` | **RETIRE** | — | Airflow gone (Data Factory replaces it). |
| ☐ E7 | `.user.yml` | **RETIRE** | — | Local user id only (`id: <uuid>`); not project content. |

## Already in this repo (do NOT re-port — F0 + gap-fix passes covered these)
`seeds/*` (5 CSVs, with `source_uri` already abfss-rewritten) · `great_expectations/*` ·
`tests/{lineage,boundary}_contract.py` · `.claude/**` (8 agents + hook + settings) ·
all `architecture/*.md` · `cheatsheets/**` · `learning/**` · `debate/**` · `CLAUDE.md` ·
`README*.md` · `BACKLOG.md` · `AGENT_ROSTER_RECOMMENDATION.md` · `.github/workflows/ci.yml`.

## Parity test (step 5 — the acceptance gate, do this once F1+F2 run on real Fabric)
The sibling repo's `dim_client` (1 row), `dim_asset` (19 rows: 14 EDITED / 5 RAW), and
`fact_chunk` (**131 chunks**, 3–18/video, real Malay automotive ad transcripts) are the golden
baseline. Re-running the ported pipeline on the **same** Drive folder must reproduce the same
asset_ids (identity formula unchanged) and the same chunk grain. Differences beyond
float-rounding/engine-ordering = a port bug, not "expected variance". The `asset_id`s themselves
are deterministic across engines (pure SHA-256), so they are an exact-match check.

## Status
- **Build state:** 0/28 port items done (this map is the plan; no code ported yet).
- **Sequencing:** port begins only after the owner opens a Fabric codespace/workspace (real
  capacity to test parity). Confirmed Sonnet for the port sessions, with this map as the strict
  checklist (`SESSION_LOG.md` 2026-06-24).
