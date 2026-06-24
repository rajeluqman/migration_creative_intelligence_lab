# Debate Agenda — Creative Intelligence Pipeline

Facilitator: **@data-architect** (ULTIMATE VETO on data model + architecture).
Each agent answers from their lane only. Cite a principle/ADR-style reason, not opinion.

## Contested questions

**Q1 — Paradigm.** Is the Gold layer a Kimball star, or is it fundamentally an
**asset lineage graph + feature store (+ optional vector index)**? Is forcing a star
schema here honest, or cargo-cult? (data-architect leads; senior-DE, analytics-eng weigh in)

**Q2 — Asset identity (P1).** Content hash as `asset_id`. But near-duplicates differ by
2–3s → their hashes DIFFER (hash = exact-byte only). So content-hash does NOT dedup
"almost the same" videos. Do we need perceptual/fuzzy dedup, or is exact-hash enough +
a separate similarity step? (data-architect, data-quality-steward)

**Q3 — Parent–child lineage (P2).** Self-referencing `parent_asset_id` (RAW → EDITED) to
let raw clips inherit "proxy performance" from their edited children. Is this sound, or
does it overstate causality? Given the owner says perf data is often ABSENT, do we even
build the `fact_ad_performance` table now, or stub it? (data-architect, business-analyst)

**Q4 — Grain & semantic chunking (P3/P4).** The real unit of value is the **semantic
chunk** (a standalone marketing beat), not the video. Confirm grain = one chunk. Validate
`standalone_score` (1–5) and `next_compatible_themes[]` as the mechanism that prevents
Frankenstein mix-and-match. Where does chunking live — Bronze, Silver, or Gold?
(data-architect, senior-DE, analytics-eng)

**Q5 — Bronze/Silver/Gold boundaries for unstructured + LLM.** What exactly is immutable
in Bronze (raw Gemini JSON), what's conformed in Silver (flattened chunk rows), what's
modelled in Gold (asset dim, feature/chunk fact, lineage, performance bridge)?
(senior-DE, data-platform-engineer)

**Q6 — Quality & testing of a non-deterministic LLM pipeline (P5).** JSON-schema gate,
business-constraint gate (`1<=standalone_score<=5`), golden-dataset human agreement
threshold, GE suites per layer, idempotent re-processing. What's the minimum credible
test strategy? (data-quality-steward, qa-engineer)

**Q7 — Tool stack & portfolio honesty (P6).** From the owner's resume stack, what is the
*honest, scalable* tool set for THIS workload (video + LLM + small-to-medium structured
output)? Is Spark/Databricks justified, or over-engineering vs DuckDB/dbt? What makes this
a STRONG distinct portfolio piece (not a clone of the 4 existing pipelines)?
(senior-DE, data-platform-engineer, finops-agent)

**Q8 — Cost & scale.** Gemini video processing cost at 40 → 500 → 5000 videos. Idempotency
/ skip-existing as a cost control. Where's the spend cliff? (finops-agent)

**Q9 — Scope.** MVP cut line. What is explicitly OUT of v1 (vector DB? RAG generator?
ad-performance ingestion? perceptual dedup?) to avoid scope creep on a portfolio project?
(scope-guardian, product-owner)

**Q10 — Roster.** How many agents does THIS project actually need (it's smaller than the
20-agent gym)? Which personas are essential, which are dead weight here?
(product-owner + data-architect synthesize)
