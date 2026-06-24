# Creative Intelligence Pipeline — Microsoft Fabric Migration

> **Status:** Standalone project, sibling of `creative_intelligence_lab`. This repo is the
> **Microsoft Fabric migration** of that project (`architecture/ADR-008-migrate-to-microsoft-fabric.md`,
> 2026-06-24) — every apparatus (agents, ADRs, governance contracts, cheatsheets, the cikgu
> curriculum) keeps the **same structure** as the sibling repo; only the ecosystem/tools stack
> migrated, totally, to Microsoft Fabric. The original repo's framing is preserved verbatim in
> `README.md.orig` and `debate/` as the historical record this migration builds on.

## What this project is
An ETL/ELT pipeline that turns **messy raw advertising video** (client uploads a Google
Drive folder of compilations — long, short, near-duplicate creative footage) into
**structured, queryable creative intelligence**: every line of dialogue, hook, theme,
sentiment, and a "can this clip stand alone?" score — so a marketing team can search,
mix-and-match, and generate new high-converting ad scripts from past footage.

## The flow, as built on Fabric
1. **Source** — client Google Drive folder link (messy compilation videos).
2. **Landing (OneLake Lakehouse `Files/`)** — Drive → OneLake via a Fabric notebook. Near-
   duplicate videos exist (differ by 2–3 seconds) → need a content-based identity, not a
   random number.
3. **Bronze** — raw, append-only, in the same Lakehouse `Files/`. Keep the *exact* Gemini API
   response word-for-word. No business logic yet (re-parse without re-paying API).
4. **Silver** — PySpark notebook → Delta Tables, cleansed, row-per-semantic-chunk. Filler
   words removed, timestamps normalized, entities/keywords extracted.
5. **Gold** — Fabric Warehouse T-SQL `VIEW`s over a OneLake shortcut (graph + feature store +
   performance marts) for query + downstream apps.

## The hard problems (unchanged by the migration — these are domain-level)
- **P1 — Identity:** near-duplicate videos. Content hash (SHA-256) folded with `client_id` as
  `asset_id`; identical hash = exact dup, skip re-processing (ADR-006).
- **P2 — Proxy performance:** raw/unedited videos have NO ad-performance data. Only the
  *edited* clip that actually ran as an ad has spend/impressions/conversions. The goal is a
  **searchable, queryable creative feature store**, not a media-buying dashboard.
- **P3 — Frankenstein content:** cutting videos into ~10-second slices by timestamp and mixing
  them produces clips that are sometimes irrelevant / message-breaks. Modelled via
  `standalone_score` + `bridge_chunk_compatibility`.
- **P4 — Semantic chunking:** cut by *meaning*, not *duration* — Gemini emits semantic chunks
  with `chunk_theme`, `sentiment`, `standalone_score` (1–5), `next_compatible_themes`.
- **P5 — Testing:** how do we test an LLM-driven pipeline whose output is non-deterministic
  JSON with business-logic constraints? Golden-dataset + value-range/schema gates.
- **P6 — Portfolio fit (this repo's answer):** the sibling repo's ADR-001 deliberately picked
  the *minimal* footprint (DuckDB, no Spark/Snowflake/Airflow) for KB–MB structured data. This
  repo goes the other direction on purpose: it runs the **Microsoft Fabric subset** of the
  target resume stack end to end (PySpark notebooks, Lakehouse/Warehouse, Data Factory, Power
  BI, Azure OpenAI/Copilot) — accepted as a named trade-off in ADR-008 even though the data
  volume alone wouldn't demand it.

## Downstream apps this Gold layer should enable (v2, NOT v1 — see CLAUDE.md "v1 Scope LOCKED")
1. AI-powered creative search engine (SQL/text/vector over the feature store).
2. RAG-based script/creative-brief generator (retrieve winning segments → Gemini).
3. Creative-ops analytics dashboard (which hooks/themes correlate with winners).
4. Automated tagging + asset archiving (auto-organize the messy Drive/OneLake).

## Deliverables logged in this repo
- `architecture/ADR-008-migrate-to-microsoft-fabric.md` — the migration decision record
  (layer-by-layer mapping, binding conditions, rejected alternatives).
- `architecture/STACK_AND_FLOW.md` — the Fabric stack + end-to-end flow, as built here.
- `debate/00_AGENDA.md` + `debate/DEBATE_LOG.md` — the original cabinet convene (historical,
  pre-Fabric; never retroactively edited).
- `architecture/DATA_MODEL.md` — the agreed conceptual/logical data model + star/graph schema
  (unchanged by the migration — only the physical engine moved).
- `AGENT_ROSTER_RECOMMENDATION.md` — how many / which agents this project needs (unchanged).
- `PROJECT_STATUS.md` — current build state + what's pending (F1 notebooks, F2 Warehouse
  views, F3 Data Factory pipeline, F4 serving).
