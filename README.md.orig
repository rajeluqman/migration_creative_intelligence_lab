# Creative Intelligence Pipeline — Cabinet Convene (Side Project)

> **Status:** Standalone project. It began as a side convene that borrowed the cabinet
> agents from a separate gym, but the 7 agents it needs now live in `.claude/agents/` here
> — no external dependency. See `AGENT_ROSTER_RECOMMENDATION.md` for the roster rationale.

## What this project is
An ETL/ELT pipeline that turns **messy raw advertising video** (client uploads a Google
Drive folder of compilations — long, short, near-duplicate creative footage) into
**structured, queryable creative intelligence**: every line of dialogue, hook, theme,
sentiment, and a "can this clip stand alone?" score — so a marketing team can search,
mix-and-match, and generate new high-converting ad scripts from past footage.

## The flow the owner sketched (prototype → production)
1. **Source** — client Google Drive folder link (messy compilation videos).
2. **Landing (S3 raw)** — Drive → S3 via API/script. Near-duplicate videos exist
   (differ by 2–3 seconds) → need a content-based identity, not a random number.
3. **Bronze** — raw, append-only. Keep the *exact* Gemini API response word-for-word.
   No business logic yet (re-parse without re-paying API).
4. **Silver** — cleansed, tabular, row-per-segment. Filler words removed, timestamps
   normalized, entities/keywords extracted.
5. **Gold** — modelled (star / asset-graph / feature store) for query + downstream apps.

## The hard problems the owner raised (these are the debate seeds)
- **P1 — Identity:** near-duplicate videos. Owner's instinct: content hash (MD5/SHA-256)
  as `asset_id`; identical hash = exact dup, skip re-processing.
- **P2 — Proxy performance:** raw/unedited videos have NO ad-performance data. Only the
  *edited* clip that actually ran as an ad has spend/impressions/conversions — and often
  even that isn't available. The owner does NOT want ROAS reporting right now; the goal
  is a **searchable, queryable creative feature store**, not a media-buying dashboard.
- **P3 — Frankenstein content:** cutting 40 videos into ~10-second slices by timestamp and
  mixing them produces clips that are sometimes irrelevant / message-breaks. How do we
  model the data so mix-and-match stays coherent?
- **P4 — Semantic chunking:** owner's direction is to stop cutting by *duration* and start
  cutting by *meaning* — Gemini emits "semantic chunks" with `chunk_theme`, `sentiment`,
  `standalone_score` (1–5: safe to reuse alone), `next_compatible_themes`.
- **P5 — Testing:** how do we test an LLM-driven pipeline whose output is non-deterministic
  JSON with business-logic constraints?
- **P6 — Portfolio fit:** owner wants this as a CV portfolio project. Owner's resume stack:
  Python (PySpark/Pandas), SQL, Spark, dbt Core, Airflow, Databricks, Snowflake, Delta Lake,
  AWS (Glue/S3/Lambda/MWAA/Step Functions), Azure (ADF/ADLS/Key Vault), Great Expectations,
  GitHub Actions CI/CD, Power BI, MLflow, Gemini API, Slack alerts. Which subset is the
  honest, scalable stack for THIS use case?

## Downstream apps this Gold layer should enable
1. AI-powered creative search engine (SQL/text/vector over the feature store).
2. RAG-based script/creative-brief generator (retrieve winning segments → Gemini).
3. Creative-ops analytics dashboard (which hooks/themes correlate with winners).
4. Automated tagging + asset archiving (auto-organize the messy Drive/S3).

## Deliverables of this convene (logged in this folder)
- `debate/00_AGENDA.md` — contested questions put to the cabinet.
- `debate/DEBATE_LOG.md` — each agent's position + the data-architect's synthesis/rulings.
- `architecture/DATA_MODEL.md` — the agreed conceptual/logical data model + star/graph schema.
- `AGENT_ROSTER_RECOMMENDATION.md` — how many / which agents THIS project actually needs.
