# PROJECT STATUS — Creative Intelligence Pipeline (Microsoft Fabric Migration)

> Resume checkpoint. Read this BEFORE reading code (token discipline, CLAUDE.md).
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

## What's NOT done yet (deferred, not started this session)
- **F1 — `notebooks/` + `scripts/` + `requirements.txt` + `setup.sh`.** The actual Drive→OneLake
  ingest, Bronze/Silver PySpark notebooks, and the scaffold script that generates them. Both
  `CLAUDE.md` and `README_BUILD.md` already document `bash setup.sh` as step 1 — the script
  itself does not exist yet. `.env.example` also does not exist yet (needs `FABRIC_WORKSPACE`,
  `FABRIC_LAKEHOUSE`, `GEMINI_API_KEY`, no `S3_BUCKET`/`AWS_*`).
- **F2 — `warehouse/` Gold T-SQL views** (`fact_chunk`, `dim_asset`, the bridge tables, the
  performance marts) over a OneLake shortcut.
- **F3 — `pipelines/creative_intel_fabric.json`** (Fabric Data Factory orchestration pipeline).
- **F4 — Serving**: Power BI Direct Lake + Fabric Copilot/Azure OpenAI QA veneer, wired only
  after Gold has real rows (mirrors the sibling repo's ADR-005 sequencing discipline).

## F0 closeout — 2026-06-24
- `python tests/lineage_contract.py` and `python tests/boundary_contract.py` both run clean
  locally (✅ OK on both, including the hand-edited `seeds/asset_manifest.csv` new path scheme).
- @scope-guardian co-signed ADR-008's Binding Condition 5 — **APPROVED, no scope creep**
  (verdict written directly into the ADR's "Sign-off" section; ADR-008 Status line updated to
  "Accepted, fully closed"). v1 Scope LOCKED list and all v2-OUT items confirmed unchanged.

## Next step when resuming
1. Commit + push F0 to `https://github.com/rajeluqman/migration_creative_intelligence_lab`
   (owner explicitly wants this pushed BEFORE provisioning any codespace/workspace on the new
   repo — do not create one).
2. Only after push: owner creates the Fabric workspace + codespace themselves, then F1 begins
   (notebooks/scripts/setup.sh/requirements.txt/.env.example).

## Standalone status
Self-contained, same as the sibling repo — `CLAUDE.md` + 8 agents present; no parent/gym
dependency. No `venv/` yet (nothing to install — F1 not started). Do NOT commit `.env` (doesn't
exist yet either).
