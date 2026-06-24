# Creative Intelligence Pipeline — AI Context (Microsoft Fabric build)

> Auto-loaded by Claude Code every session. Standalone project (no parent gym dependency).
> This repo (`migration_creative_intelligence_lab`) is the **Microsoft Fabric migration** of
> the sibling repo `creative_intelligence_lab` (ADR-008, 2026-06-24). Every apparatus —
> agents, ADRs, governance contracts, cheatsheets, the cikgu curriculum — keeps the exact same
> structure as the sibling repo. **Only the ecosystem/tools stack migrated**: OneLake replaces
> S3, PySpark notebooks + Fabric Warehouse T-SQL replace dbt-duckdb, Fabric Data Factory
> replaces Airflow, Power BI Direct Lake + Fabric Copilot replace Snowflake Cortex. See
> `architecture/ADR-008-migrate-to-microsoft-fabric.md` for the full decision record.

## 🛑 STOP-GATE — read before ANY data/model/lineage work
This project is governed. Before you edit a model, seed, schema, storage path, or ingest
script — or before you "proceed" past a lineage/identity question — you MUST:
1. **Open the ADR/spec that governs it first.** Lineage & identity → ADR-006 + ADR-008 (path
   grammar) + `architecture/LINEAGE_CONTRACT.md`. Grain/graph/star → ADR-002 + DATA_MODEL.md.
   Stack boundary (rejected tech) → ADR-001/004/005 (historical) + ADR-008 (governing) +
   `architecture/BOUNDARY_CONTRACT.md`.
   Scope → CLAUDE.md "v1 Scope (LOCKED)" + `architecture/BOUNDARY_CONTRACT.md` + @scope-guardian.
2. **Validate lineage & fidelity BEFORE building downstream.** Every asset must trace to a
   **real registered client** (`dim_client.csv`) and a content hash, with a storage path
   that proves it:
   `abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/Files/landing/<client_id>/video/<asset_id>.<ext>`
   where `asset_id == sha256("{client_id}:{content_sha256}")` (ADR-006; path grammar ADR-008).
   Run `python tests/lineage_contract.py` and `python tests/boundary_contract.py` — these are
   the binding checks, not your judgement.
3. **If a rule and the request conflict, STOP and surface it** — do not silently proceed.
   Mixed-domain dimension, placeholder client_id, path/column drift, banned tech
   (Databricks/Glue/boto3-S3-SDK/vector-DB/RAG/dashboard — **PySpark itself is allowed**, ADR-008),
   scope creep → name it, cite the doc, and ask @data-architect / @scope-guardian before writing
   code.

This gate is enforced three ways so it cannot be skipped: this prompt (soft), the
`.claude/hooks/governance_guard.py` pre/post-edit hook (blocks edits to governed files), and
CI `tests/lineage_contract.py` + `tests/boundary_contract.py` (blocks the PR). Governance is
code, not vigilance.

## Project Overview
**Domain**: Advertising / creative-ops intelligence
**Problem**: Turn messy raw ad video (a client's Google Drive folder of near-duplicate
compilation footage) into a **structured, queryable creative feature store** — every line
of dialogue, hook, theme, sentiment, and a `standalone_score` (can this clip be reused
alone?) — so a marketing team can search past footage and assemble new ad scripts.
**Modelling**: Hybrid — asset-graph + star marts (see ADR-002).
**Purpose**: Data Engineering portfolio project (single-dev).

## v1 Scope (LOCKED — see @scope-guardian)
v1 = the **queryable creative feature store** only. Explicitly OUT (v2 BACKLOG):
1. AI creative search engine  2. RAG script generator  3. creative-ops dashboard
4. automated tagging/archiving. Also OUT: ROAS / ad-performance ingestion, vector DB.

## Stack (locked — Microsoft Fabric, ADR-008)
| Layer | Storage | Compute / engine | Notes |
|-------|---------|------------------|-------|
| Source | client Google Drive folder | `scripts/ingest_drive_to_onelake.py` (Fabric notebook) | near-duplicate videos |
| Landing (Bronze raw) | **OneLake Lakehouse `Files/`**, append-only | `scripts/run_gemini_extract.py` (Fabric notebook) | keep Gemini response **word-for-word**; re-parse without re-paying |
| Identity | — | content hash (MD5/SHA-256) = `asset_id` | skip-existing idempotency |
| Silver | **OneLake (Delta Tables)** | **PySpark notebook** (Fabric Lakehouse) | row-per-semantic-chunk; filler removed, timestamps normalized |
| Gold / marts | **OneLake (Delta, via shortcut)** | **Fabric Warehouse T-SQL `VIEW`s** `warehouse/{core,performance}` | graph edges + star facts + perf marts (SPEC_v1.5) |
| Quality | Great Expectations (run in notebooks) | per-layer suites + golden-dataset | LLM-output gates |
| Orchestration | — | **Fabric Data Factory pipeline** (`pipelines/creative_intel_fabric.json`) | retry/backoff, skip-existing |
| Significance | Python post-step (Fabric notebook) | `scripts/significance_post_step.py` | v1.5 |
| **Serving** | reads Gold OneLake | **Power BI Direct Lake** + **Fabric Copilot / Azure OpenAI** | read-only veneer; Gold OneLake = sole truth (ADR-008) |

⚠️ Stack boundary (ADR-001/004/005 historical + **ADR-008** governing): **storage = unified
OneLake** (no S3/MinIO; no second physical copy for Gold). PySpark notebooks are now the
Bronze/Silver transform engine (ADR-008 supersedes ADR-001's DuckDB-over-Spark on the
transform-engine axis); Gold stays T-SQL **views**, never a duplicated physical table. Power
BI/Copilot admitted ONLY as a read-only serving veneer over Gold OneLake, never as transform
engine or source of truth. Still rejected: Databricks / Glue / dedicated vector DB / dbt.

## Architecture of Record
`architecture/` — DATA_MODEL.md (+ v1.5), ERD_consolidated.md / erd.dbml, STACK_AND_FLOW.md,
DBT_DAG.md (superseded stub, ADR-008), SPEC_v1_search.md, SPEC_v1.5_performance_marts.md; the
doc-gap set added by the 2026-06-22 convene — BRD.md, DRD.md, DATA_DICTIONARY.md, DQD.md,
STTM.md (all @data-architect + @scope-guardian gate-approved as documentation-debt closure,
not scope creep); and:
- ADR-001 — DuckDB over Spark (historical; transform-engine axis superseded by ADR-008)
- ADR-002 — graph over star
- ADR-003 — chunking in Silver
- ADR-004 — performance-veto converted
- ADR-005 — unified S3 + Snowflake serving veneer (historical; storage/serving axis superseded by ADR-008)
- ADR-006 — multi-client tenancy (identity formula — unchanged by ADR-008)
- ADR-007 — landing TTL (policy unchanged; enforcement mechanism amended by ADR-008)
- **ADR-008 — migrate to Microsoft Fabric (governing this repo's physical stack)**

**Governance gate:** @data-architect holds ULTIMATE VETO and enforces the **Clean-ERD
Doctrine** on every model change — 1 table = 1 grain = 1 business entity · no mixed-domain
dimensions · bridge tables (not CTEs) for N:N · serving = view, never a duplicated physical
table · one isolated SCD strategy per table · what's deliberately OUT stays named in ERD §6.
No Gold/marts work proceeds without architecture sign-off. Full doctrine + veto format:
`.claude/agents/data-architect.md`.

## Repo map (beyond architecture/)
- `BACKLOG.md` — v2-deferred items + the gym-apparatus-port ruling (cheatsheets/learning kept
  as templates, gym agents/incubator rejected — see `AGENT_ROSTER_RECOMMENDATION.md`)
- `debate/` — original cabinet convene record (pre-Fabric): `00_AGENDA.md` (contested
  questions) + `DEBATE_LOG.md` / `ROUND_02_PERFORMANCE_DEBATE.md` (rulings). Historical, not a
  build target — never retroactively edited, same as the sibling repo.
- `great_expectations/` — suite README + per-layer expectation JSON (`expectations/`)
- `cheatsheets/{troubleshooting,optimization}/00_INDEX.md` — card-format libraries, English,
  Fabric/PySpark-native; templates only until v1 ships AND ≥1 real incident lands (BACKLOG-gated)
- `learning/CURRICULUM.md` — @cikgu's M0–M11 teaching path (Fabric-flavored where the module
  touches the engine, e.g. M6); `LEARNING_LOG.md` is the score/progress log (run @cikgu as a
  main session, not a subagent, for actual teaching)
- `analyses/*.sql` — ad-hoc T-SQL/Spark-SQL analyses (not Warehouse views, not built/tested by
  any framework — there is no dbt-equivalent in this stack)
- `.github/workflows/ci.yml` — static-gates-only CI ($0, no cloud, no secrets): ruff lint,
  py_compile, lineage/boundary contracts, GE JSON validity, no-`.env`-committed guard (no dbt
  steps — dbt is dropped, ADR-008)

## The hard problems (the design drivers)
- **Identity**: near-duplicate videos → content hash, not random key.
- **No performance data**: raw footage has no spend/impressions → feature store, not a
  media-buying dashboard.
- **Frankenstein content**: mixing 10s slices breaks message → model for coherent reuse.
- **Semantic chunking**: cut by *meaning* not *duration*; Gemini emits `chunk_theme`,
  `sentiment`, `standalone_score` (1–5), `next_compatible_themes`.
- **Testing a non-deterministic LLM pipeline**: golden-dataset + value-range/schema gates.

## Cabinet (7 agents) — see `.claude/agents/`
**Veto holders**: @data-architect (Opus, ultimate — the model is the hard part) ·
@scope-guardian (Sonnet, hard veto on scope creep).
**Build**: @senior-data-engineer (Sonnet) · @data-quality-steward (Sonnet) ·
@product-owner (Sonnet) · @finops-agent (Sonnet, part-time — Gemini token cost).
**Conditional**: @qa-engineer (Haiku — activate when golden-dataset testing is its own workstream).
@cikgu (Sonnet) is the optional teaching mentor — NOT a build agent; he teaches, never builds.
Roster rationale: `AGENT_ROSTER_RECOMMENDATION.md`.

## Build quickstart
See `README_BUILD.md`. Short version:
1. `bash setup.sh` → scaffold + venv + deps (no dbt; Fabric notebooks run in-workspace)
2. `cp .env.example .env` → fill `GEMINI_API_KEY`, `FABRIC_WORKSPACE` (`creative-intel-ws`),
   `FABRIC_LAKEHOUSE` (`creative_intel_lh`)
3. Open the Fabric workspace, attach the Lakehouse — no local `profiles.yml` equivalent;
   Bronze/Silver notebooks and Gold Warehouse views run inside the Fabric capacity
4. Implement stubs marked `TODO` from `architecture/SPEC_*` in `notebooks/` (Bronze/Silver,
   F1) and `warehouse/` (Gold T-SQL views, F2)
5. Run notebooks in pipeline order (see `STACK_AND_FLOW.md` §2), then the significance step (v1.5)

## Token Discipline (all agents + main session)
1. Checkpoint first: read `PROJECT_STATUS.md` (and `DEBUG_CHECKPOINT.md` if debugging,
   `learning/LEARNING_LOG.md` if a cikgu session) BEFORE reading code.
2. Scope: read only files in the current module — max ~3 files/turn.
3. Use the Explore subagent to find "where is X" instead of reading many files inline.
4. Update the checkpoint before ending a turn.

## What NOT To Commit
`.env*`, `data/`, `*.parquet`, `*.csv` (except `seeds/`), raw video, `COST_LOG.md`,
`DEBUG_CHECKPOINT.md`, `SIGN_OFF_LOG.md` (ephemeral working logs, created during build —
not yet present; add to `.gitignore` when they first appear).

**Intentionally committed** (unlike the parent gym pattern this project borrowed agents
from): `CLAUDE.md`, `PROJECT_STATUS.md`, `learning/LEARNING_LOG.md` — this is a standalone,
self-contained repo by design; see `PROJECT_STATUS.md` "Standalone status". Fabric-specific
secrets (service principal client secret, Fabric capacity/tenant IDs used for auth) go in
`.env`, same rule as `GEMINI_API_KEY` — never committed.
