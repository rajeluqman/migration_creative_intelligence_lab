# PROJECT STATUS — Creative Intelligence Pipeline (Microsoft Fabric Migration)

> Resume checkpoint. Read this BEFORE reading code (token discipline, CLAUDE.md). Read
> `SESSION_LOG.md` too — it has the owner's verbatim constraints and a dated, honest account of
> this migration's shortcuts; this file is the technical checkpoint, that one is the decision record.
> This repo is the Fabric migration of `creative_intelligence_lab` (sibling repo, DuckDB/dbt/S3
> build). See that repo's `PROJECT_STATUS.md` for the real Drive-run build history — none of it
> is repeated here; this checkpoint only covers what changed in **this** repo.

## Where we are
**Session A (F0 — governance + apparatus migration) is complete, 2026-06-24.** Cloned fresh
from `creative_intelligence_lab`, copied every apparatus verbatim (debate/, learning/, GE,
seeds, the 8-agent roster, logical architecture docs), then wrote `ADR-008` (the migration
decision record) and surgically updated every doc/script/hook/agent that made a now-false
stack claim — never restructured anything, per the owner's explicit instruction. No code has
been *built* yet: `notebooks/`, `warehouse/`, `pipelines/`, `scripts/`, `requirements.txt`, and
`setup.sh` do not exist yet (F1–F3, see below). This checkpoint is a documentation/governance
milestone, not a working pipeline.

## What's done (F0 — this session)
- **ADR-008** (`architecture/ADR-008-migrate-to-microsoft-fabric.md`) — the migration decision:
  layer-by-layer Fabric mapping, 5 binding conditions, rejected alternatives. ADR-001/005/007
  amended with "Status:" supersession headers (bodies kept verbatim — historical record).
- **`architecture/STACK_AND_FLOW.md`** rewritten for the Fabric flow; `DBT_DAG.md` stubbed
  superseded (dbt dropped entirely — no `dbt_project.yml`/`models/`/`profiles.yml` in this repo).
- **Governance contracts updated and kept in sync**, doc + code together:
  - `architecture/LINEAGE_CONTRACT.md` + `tests/lineage_contract.py` — R4 path grammar now
    `abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/Files/landing/
    <client_id>/video/<asset_id>.<ext>` (ADR-008). Identity formula (R3, ADR-006) untouched.
  - `architecture/BOUNDARY_CONTRACT.md` + `tests/boundary_contract.py` — PySpark now **allowed**
    (was banned under ADR-001); Databricks/Glue/boto3-S3-SDK/MinIO/vector-DB/RAG/dashboard/live-
    ad-connector still **banned**. Scans `notebooks/*.py` + `warehouse/**/*.sql` (no `dags/`,
    no `models/`, no dbt profile files — those checks retired, noted in the doc).
  - `.claude/hooks/governance_guard.py` — pre/post-edit hook updated to match both contracts;
    uses a substring match on `notebooks/`/`warehouse/`/`ingest_drive` so it doesn't need to
    guess F1's exact future filenames.
- **`CLAUDE.md`** — STOP-GATE, stack table, ADR list, repo map, build quickstart all rewritten
  for Fabric. **`seeds/asset_manifest.csv`** — `source_uri` rewritten to the abfss/OneLake
  scheme (asset_id/content_sha256 values themselves unchanged — same formula, ADR-006).
- **8 cabinet agents** (`.claude/agents/*.md`) — 7 of 8 got surgical edits for stale stack
  claims (dbt/DuckDB/Airflow/S3 → PySpark notebooks/Fabric Warehouse/Data Factory/OneLake);
  `data-quality-steward.md` needed no changes. Roster/personalities/veto powers unchanged.
- **Cheatsheets + curriculum** — `cheatsheets/{troubleshooting,optimization}/00_INDEX.md`
  binding-translation sections rewritten (the old "we have no Spark" premise inverted to
  "Spark IS the engine now, but Fabric-managed — translate cluster-ops assumptions, drop dbt
  items"); `learning/CURRICULUM.md` M6/M7/M11 rewritten for Fabric mechanics + Data Factory +
  the boundary-contract DIY; `learning/diy/README.md` DIY targets repointed at Gold Warehouse
  views instead of dbt model paths.
- **`BACKLOG.md`** — Tier-1 cheatsheet clause updated (`zero Spark/MinIO content` → `zero
  Databricks/Glue/boto3-S3-SDK content`, `ADR-005`→`ADR-008`); the vector-DB v2-OUT line
  re-justified (DuckDB VSS no longer exists here — T-SQL Warehouse views + Direct Lake cover
  v1 search; Copilot/Azure OpenAI is a QA veneer, not a vector index).
- **`README.md`** rewritten (Fabric framing, P6 names the deliberate "go all-in on Fabric"
  trade-off); original repo's README preserved verbatim as `README.md.orig`. **`README_BUILD.md`**,
  a slimmed **`.github/workflows/ci.yml`** (no dbt steps — lint/compile/seed-CSV-parse/lineage
  contract/boundary contract/GE-JSON-validity/no-`.env`-guard), and **`.gitignore`** (Fabric-
  appropriate: dropped `*.duckdb`/`dbt_packages/`/`venv_airflow/`, added notebook checkpoint
  dirs) all written fresh for this repo.

## What's NOT done yet — concrete port checklist

> **The authoritative, binding version of this checklist is `MIGRATION_MAP.md`** (28 items,
> per-file treatment + construct translation table + parity-test gate, written 2026-06-24 by
> reading every source file). The summary below is a pointer; work from `MIGRATION_MAP.md`.
> See `SESSION_LOG.md` 2026-06-24 "Honest gap audit" for why this gap existed: the F0 pass
> shipped 100% docs/governance, 0% ported pipeline code. The sibling repo is NOT a template —
> it has a real, working v1 build. This is a per-file PORT list, not a "write from scratch" list.

- **F1 — port `scripts/*.py` → Fabric notebooks/scripts:**
  - `scripts/ingest_drive_to_s3.py` (250 lines, real) → Drive→OneLake notebook/script: swap
    `boto3` S3 writes for OneLake `Files/` writes (abfss path grammar, ADR-008); content-hash +
    `asset_id` formula (ADR-006) is unchanged logic, port as-is.
  - `scripts/run_gemini_extract.py` (238 lines, real) → Gemini call logic ports unchanged
    (model-agnostic to storage); only the Bronze write target changes (S3 → OneLake `Files/`).
  - `scripts/enforce_landing_ttl.py` (115 lines, real) → port the guarded-delete logic; ADR-007's
    Status header already says the mechanism becomes a OneLake-targeting Fabric
    notebook/pipeline, not a bare lifecycle rule.
  - `scripts/env_guard.py` (16 lines) → swap the `S3_BUCKET` check for `FABRIC_WORKSPACE`/
    `FABRIC_LAKEHOUSE`.
  - `scripts/significance_post_step.py` — still a 3-line TODO stub in the sibling repo too;
    nothing to port, build fresh per `SPEC_v1.5_performance_marts.md` §6 when F2 lands.
  - `setup.sh` (546 lines) → needs a Fabric-equivalent scaffold script (notebooks/ + warehouse/
    stubs instead of models/+dbt config); `requirements.txt`, `.env.example` (`FABRIC_WORKSPACE`,
    `FABRIC_LAKEHOUSE`, `GEMINI_API_KEY`, no `S3_BUCKET`/`AWS_*`) port with light edits.
- **F2 — port `models/**/*.sql` (18 files) → `warehouse/**/*.sql` Gold T-SQL views:**
  some are real builds, not stubs (e.g. `models/marts/performance/bridge_ad_chunk.sql` has a
  full EDL join, not `where 1=0`) — read each one before rewriting, don't assume stub status.
  Every `{{ ref(...) }}` becomes a plain object name (no dbt); DuckDB/Postgres-only syntax
  (`unnest()`, `::type` casts seen in the SPEC docs' own snippets) needs real T-SQL translation,
  not just the disclaimer note current SPEC docs carry — **unverified against a real Fabric
  Warehouse**, test this for real once a workspace exists.
  - Also port: `analyses/demo_queries.sql` (has real query content in the sibling repo, not
    empty — read it before writing this repo's version).
- **F3 — port `dags/creative_intel_pipeline.py`** (136 lines, real) → `pipelines/
  creative_intel_fabric.json` (Fabric Data Factory). This is a structural translation (Airflow
  DAG/operator graph → Data Factory pipeline/activity graph), not a line-for-line port — read
  the DAG's actual task dependencies and retry/backoff config before designing the activities.
- **F4 — Serving**: Power BI Direct Lake + Fabric Copilot/Azure OpenAI QA veneer, wired only
  after Gold has real rows (mirrors the sibling repo's ADR-005 sequencing discipline). No
  sibling-repo equivalent to port — this layer is new in the Fabric build.
- **Cross-cutting, do before/during F1-F3:** every Fabric-specific syntax/capability claim in
  `architecture/SPEC_v1_search.md`, `SPEC_v1.5_performance_marts.md`, and `STACK_AND_FLOW.md`
  is unverified against a real Fabric Warehouse/notebook — confirm or correct each one as F1-F3
  actually run, don't assume the docs are right just because they're internally consistent.

## F0 closeout — 2026-06-24
- `python tests/lineage_contract.py` and `python tests/boundary_contract.py` both run clean
  locally (✅ OK on both, including the hand-edited `seeds/asset_manifest.csv` new path scheme).
- @scope-guardian co-signed ADR-008's Binding Condition 5 — **APPROVED, no scope creep**
  (verdict written directly into the ADR's "Sign-off" section; ADR-008 Status line updated to
  "Accepted, fully closed"). v1 Scope LOCKED list and all v2-OUT items confirmed unchanged.

## Gap-recheck pass — 2026-06-24 (post-push)
F0 push landed, then a full-repo grep audit (`dbt|duckdb|s3|snowflake|airflow|minio`) found 14
architecture docs the first F0 pass had missed (it covered CLAUDE.md/STACK_AND_FLOW/contracts/
agents/cheatsheets/curriculum but not the deeper SPEC/DATA_MODEL/DQD/DRD/STTM/BRD/ADR-002/erd.dbml
layer). Fixed, same surgical-edit-not-restructure rule:
- `DATA_MODEL.md` §5/§8 (dbt materialization path + stack table) + 4 stray cell-level S3/dbt notes.
- `SPEC_v1_search.md` — Engine line, all `{{ ref() }}`→plain names, `ilike`→`like`, the DuckDB
  `fts` section replaced, and a **substantive ruling change**: vector/semantic search is now OUT
  full stop (no in-stack vector index at all — ADR-008 Binding Condition 4), not a "v1.5
  fast-follow" the way DuckDB VSS made it in the sibling repo.
- `SPEC_v1.5_performance_marts.md` — Engine line, all 12 `{{ ref() }}`→plain names, dbt
  test/relationship mentions → GE-equivalent, manual-CSV target S3→OneLake.
- `DATA_MODEL_v1.5_PERFORMANCE.md`, `DATA_DICTIONARY.md`, `DRD.md`, `STTM.md`, `BRD.md`,
  `ADR-002/004/006` (passing implementation-detail mentions only — their core rulings untouched),
  `BOUNDARY_CONTRACT.md`, `erd.dbml` (`database_type`, 3 column notes) — same dbt/DuckDB/S3
  pattern fixed throughout.
- `DQD.md` §4 reconciliation gate **rewritten substantively**: the old test compared Snowflake
  external tables vs DuckDB-over-S3; the Fabric equivalent compares a Warehouse view vs a direct
  Lakehouse Delta read (Direct Lake mode has no import/duplication to begin with).
- `DQD.md`/`DRD.md` also had **dangling citations** to `PROJECT_STATUS.md` finding #1/#2/#3 —
  those findings live in the *sibling* repo's checkpoint, not this one. Reframed as "same open
  item as `creative_intelligence_lab/PROJECT_STATUS.md` finding #N" and, for finding #1 (a dbt
  schema test marked DONE there), reframed as **REQUIRED AT F2** here since no dbt/`_performance.yml`
  exists in this repo to have inherited that test from.
- Both contracts re-verified green after every batch of fixes, not just once at the end.

## Push status — 2026-06-24 (IMPORTANT, read before assuming anything is live)
`origin/main` has only the first F0 commit. **Two more commits exist locally and are NOT
pushed**: the gap-recheck patch (15 files) and this round (`SESSION_LOG.md` + this checklist +
the honest-gap audit). The codespace's GitHub token is scoped to the *other* repo
(`creative_intelligence_lab`) and cannot push here; a owner-provided PAT also got blocked by
the harness's own credential-leak guard (embedding any secret in a command is now refused
outright, not just flagged after the fact). **The owner must push these commits themselves**
— from their own machine, or once they open the Fabric codespace on this repo (which will have
correctly-scoped credentials).

## Next step when resuming
1. **Owner pushes the 2 pending local commits** (gap-fix patch + this SESSION_LOG round) —
   agent cannot do this (see "Push status" above).
2. Owner creates the Fabric workspace + codespace themselves, then F1 begins — work the port
   checklist above file-by-file, reading each sibling-repo source file before translating it.

## Standalone status
Self-contained, same as the sibling repo — `CLAUDE.md` + 8 agents present; no parent/gym
dependency. No `venv/` yet (nothing to install — F1 not started). Do NOT commit `.env` (doesn't
exist yet either).
