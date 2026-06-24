# ADR-008 — Migrate the physical stack to Microsoft Fabric

- **Status:** Accepted, fully closed (owner override; ratified-with-conditions by @data-architect; @scope-guardian co-signed Binding Condition 5 2026-06-24 — see "Sign-off" below)
- **Date:** 2026-06-24
- **Deciders:** owner (override), @data-architect (ultimate veto — conditional approve), @scope-guardian (co-sign, scope-not-creep)
- **Amends:** ADR-001 (transform-engine axis — DuckDB → PySpark/Fabric notebooks), ADR-005
  (storage + serving axis — S3/Snowflake → OneLake/Power BI Direct Lake), ADR-007 (landing-TTL
  enforcement mechanism — S3 lifecycle → OneLake Files lifecycle), `CLAUDE.md` stack table +
  STOP-GATE, `architecture/STACK_AND_FLOW.md` (fully rewritten, not just amended).
- **Does NOT touch:** ADR-002 (graph over star), ADR-003 (chunking in Silver), ADR-004
  (perf-veto conversion), ADR-006 (multi-client tenancy / identity formula) — the **logical**
  data model is unchanged: same two facts, same bridges, same grain, same SCD strategy, same
  `asset_id = sha256("{client_id}:{content_sha256}")` identity formula. Only the physical
  engine and storage substrate move.

## Context

Owner directive (2026-06-24): migrate this project's **ecosystem and tools stack totally** to
Microsoft Fabric. Driver: a specific job target (Lam Research, "Data Operations Specialist")
strongly prefers hands-on Microsoft Fabric (Lakehouse/Warehouse, pipelines feeding Power BI,
Copilot). This repo (`migration_creative_intelligence_lab`) is a **new, separate repo** from
the original `creative_intelligence_lab` — the original stays as the historical S3+DuckDB+
Snowflake build; this repo carries the same governed apparatus (8 cabinet agents, ADRs,
cheatsheets, learning curriculum, lineage/boundary contracts) forward onto a different physical
stack. Per owner instruction, **everything except the ecosystem/tools stack must keep the same
structure** — this ADR is the supersession record that makes that split explicit and auditable,
the same way ADR-005 amended ADR-001 rather than silently overwriting it.

## Decision

| Layer | Was (ADR-001/005) | Now (ADR-008) |
|---|---|---|
| Storage | Unified S3 (`landing/bronze/silver/gold`) | **OneLake** (Fabric Lakehouse `Files/` + Delta Tables) |
| Bronze + Silver compute | DuckDB (dbt-duckdb) | **PySpark notebooks** (Fabric Lakehouse), writing Delta |
| Transform framework | dbt Core (dbt-duckdb adapter) | **Dropped.** Replaced by PySpark notebooks (Bronze/Silver) + T-SQL views (Gold) |
| Gold marts | DuckDB external parquet (dbt models) | **Fabric Warehouse, T-SQL `VIEW`s** over a OneLake shortcut into the Lakehouse |
| Orchestration | Local Airflow DAG | **Fabric Data Factory pipeline** |
| Serving | Snowflake Cortex veneer / DuckDB VSS fallback | **Power BI Direct Lake** (reads Delta directly, no import/duplication) + **Fabric Copilot / Azure OpenAI** for QA/summarization veneer |
| AI extraction | Gemini (multimodal video) | **Unchanged** — Gemini kept for video extraction; Copilot/Azure OpenAI is an *added* QA/summarization layer, not a replacement |
| Identity | `asset_id = sha256(client_id:content_sha256)` | **Unchanged** |
| Logical model | 10-table graph+star hybrid, two facts, bridges | **Unchanged** |

Path convention (replaces `s3://<bucket>/landing/<client_id>/video/<asset_id>.<ext>`):

```
abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/Files/landing/<client_id>/video/<asset_id>.<ext>
```

`<workspace>` and `<lakehouse>` are parametrized the same way `<bucket>` was — this repo's
default values are `creative-intel-ws` / `creative_intel_lh` (see `tests/lineage_contract.py`).

## Rationale

1. **Portfolio-fit override**, same class of decision as ADR-005 (owner overrode cabinet
   local-first for Snowflake trial credits). Here the override is for a named job target's
   explicit "strongly preferred: Microsoft Fabric" requirement.
2. **The logical model is the hard part of this project (CLAUDE.md), and it survives
   untouched.** This is a physical re-platforming, not a redesign — @data-architect confirmed
   the Clean-ERD Doctrine holds across the move (see Sign-off).
3. Bronze/Silver as **PySpark notebooks** (not T-SQL) because the Gemini JSON unnest/explosion
   logic (`stg_gemini_raw`'s `unnest(json_extract(...))` pattern) is naturally a dataframe
   operation, and PySpark is the Fabric-native choice for that shape of work — it also
   directly demonstrates the Spark skill Lam's JD implies via "Fabric data experiences."
4. **Gold as T-SQL Warehouse views** (not Lakehouse SQL endpoint) because the JD explicitly
   weights "Strong coding skills (SQL...) for data transformation" and Power BI Direct Lake
   pairs cleanly with a Warehouse's T-SQL surface for the serving story.
5. **dbt is dropped, not ported**, because Fabric has no first-party dbt-fabric story as clean
   as the PySpark-notebook + Warehouse-view pattern Fabric is built around, and porting dbt
   would dilute the "totally Fabric" demonstration the portfolio goal requires. The dbt-specific
   skill is still demonstrated elsewhere in the candidate's portfolio (other repos use dbt).

## Consequences

- **Lost:** the $0, fully-local, no-cloud-dependency posture DuckDB gave. Fabric requires a
  workspace/capacity (trial or paid) — same tradeoff class as ADR-005's Snowflake trial-credit
  bet, now extended to the whole stack.
- **Lost:** dbt's test/doc-generation tooling (`dbt test`, `dbt docs generate`) — replaced by
  Great Expectations suites run inside notebooks (already the project's pattern for LLM-output
  gates) plus this repo's existing rules-as-code contracts (lineage/boundary).
- **Gained:** every layer of the stack now maps to something in the JD's preferred-skills list
  (Fabric Lakehouse/Warehouse/pipelines, Power BI, AI-in-the-Microsoft-ecosystem).
- **Named risk (flagged by @data-architect):** a physical Warehouse + Power BI Direct Lake
  makes it easy to slip into materializing a wide one-big-table for "BI speed." This is the
  single Clean-ERD axis under tension — held by Binding Condition 1 below.

## Binding Conditions (from @data-architect's sign-off — must hold for every F1-F4 commit)

1. **Serving stays a VIEW.** Gold marts are T-SQL `VIEW`s in the Warehouse over the
   OneLake-shortcut Delta tables. `fct_ad_kpi` and all ratios remain views — never stored
   columns on `fact_ad_performance` (ERD §6). Power BI Direct Lake reads the Delta facts/dims
   directly. No materialized wide OBT; any physical wide table requires query-proof first.
2. **Bronze stays immutable + verbatim.** The Gemini response is stored **word-for-word** in
   Lakehouse **`Files/`** (not a Delta table), append-only. Silver Delta tables are rebuilt
   from Bronze Files (re-parse, never re-pay), matching ADR-003's existing principle.
3. **Lineage path rule moves to `abfss://...onelake...`; the identity formula does not move.**
   `asset_id = sha256("{client_id}:{content_sha256}")` is unchanged. `tests/lineage_contract.py`
   R4 and `architecture/LINEAGE_CONTRACT.md` are updated to the new path grammar.
4. **ERD §6 OUT-list holds verbatim.** Power BI Copilot / Azure OpenAI are QA/summarization
   veneer only — never a source of truth, never introduce a predictive score column, a RAG
   store, a dedicated vector DB, RAW-proxy metrics, or `client_id` leaking onto `fact_chunk`.
5. **This ADR amends ADR-001/005/007 by reference** (their bodies are preserved verbatim with a
   superseded-status header, not rewritten — same convention ADR-005 used on ADR-001), and
   **@scope-guardian must co-sign** that the Fabric migration is a portfolio-driven physical
   migration, not v1 scope creep (the v1 Scope LOCKED list in `CLAUDE.md` is unchanged: still no
   AI search engine, RAG generator, dashboard app, or automated tagging).

## Sign-off

**@data-architect — Clean-ERD Doctrine verdict:**
`grain ✓ · domain-purity ✓ · bridges-not-CTE ✓ · serving-as-view ⚠ (conditional, Binding
Condition 1) · SCD-isolated ✓`. **APPROVED** — the logical model survives an engine swap by
construction; the single exposed flank is axis 4 (serving-as-view), held by Binding Condition 1.

**@scope-guardian — co-sign:** **APPROVED — stays within v1, no scope creep detected.**
Checked: (1) `CLAUDE.md` "v1 Scope (LOCKED)" — the four OUT items (AI search engine, RAG
generator, ops dashboard, automated tagging) plus ROAS/vector-DB are still named OUT, verbatim,
in this repo's `CLAUDE.md` and reinforced in `BACKLOG.md`'s "Other v2 items" list — nothing
softened or reclassified as in-scope. (2) `README.md` "Downstream apps" section explicitly
labels all four apps "v2, NOT v1" — same four, same framing as the sibling repo. (3)
`architecture/STACK_AND_FLOW.md` §1 rejected-tech list still bans dedicated vector DBs
(Pinecone/Weaviate/Qdrant/Chroma/Milvus/FAISS) and Databricks/Glue as standalone clusters;
Fabric Copilot/Azure OpenAI is scoped, in writing, as a read-only QA/summarization veneer over
Gold — not a RAG store, not a predictive feature, not a new serving product. (4) Binding
Condition 4 (above) independently locks the same OUT-list at the architecture-contract level,
and Binding Condition 1 prevents the Warehouse+Power BI move from backsliding into a dashboard
product via a materialized wide table. (5) The decision table, rationale, and consequences are
100% physical/tool-substrate (storage engine, compute engine, orchestration tool, serving
veneer) — no new pipeline stage, no new output column, no new client-facing capability. Path A
(video→chunk) and Path B (performance, correlation-only, RAW-backward-propagation still
permanently vetoed) are unchanged. This is the same shape of override as ADR-005 (portfolio/job-
target driven infra choice), not a reopening of what v1 *does*. Verdict: a legitimate
portfolio-driven physical migration. v1 scope is untouched.

## Rejected alternatives

- **Port dbt via `dbt-fabric` onto Fabric Warehouse, keep DuckDB-shaped transforms.** Rejected
  — dilutes the "totally Fabric" portfolio demonstration; PySpark notebooks are the more
  JD-relevant skill to show, and Fabric's own data-engineering story is built around them, not
  around a third-party dbt adapter.
- **All layers as Lakehouse Spark SQL (no separate Warehouse).** Rejected — loses the explicit
  T-SQL surface the JD calls out ("SQL... for data transformation"), and Power BI Direct Lake
  over a Warehouse is a cleaner, more standard serving story than Direct Lake over Lakehouse
  SQL endpoints for this case.
- **Replace Gemini with Azure OpenAI for video extraction.** Rejected — Azure OpenAI's
  multimodal video handling is weaker than Gemini's for this use case; Gemini stays for
  extraction, Copilot/Azure OpenAI is additive (QA/summarization), not a replacement.
</content>
