# DBT_DAG.md — SUPERSEDED (ADR-008, 2026-06-24)

**dbt is dropped from this repo.** ADR-008 replaces the dbt-duckdb transform layer with PySpark
notebooks (Bronze/Silver) + T-SQL views in a Fabric Warehouse (Gold) — there is no `dbt_project.yml`,
no `models/` tree, and no `ref()`/`source()` dependency graph in this repo to document.

The model-level **lineage itself is unchanged** (same staging→intermediate→marts shape, same
grain, same bridges) — only the execution mechanism moved. The Fabric-native equivalent of this
document (notebook execution order + Data Factory pipeline activity graph) is written in **F3
(Orchestration)** once `pipelines/creative_intel_fabric.json` exists — see `PROJECT_STATUS.md`
for what's pending.

Original content (dbt project tree, model DAG, materialization table) is preserved in the
sibling repo `creative_intelligence_lab`, where dbt-duckdb still runs.

See `architecture/ADR-008-migrate-to-microsoft-fabric.md` and the rewritten
`architecture/STACK_AND_FLOW.md` for the current build.
