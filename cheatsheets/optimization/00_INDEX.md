# Optimization Library — Creative Intelligence Pipeline (INDEX)

> Mirror of the pharma gym's optimization library, adapted to this project.
> A **static catalog** of performance/cost techniques, one card per technique, each tied to a
> real layer of THIS pipeline. Cards are fed by real findings (an SLA/perf observation →
> 🟡 APPLICABLE → ✅ DONE once applied and cited). Content is English.

> ## 🚧 STATUS: STUB — BACKLOG-gated (single-doc form)
> **This INDEX file *is* the entire Tier-1 optimization artifact for now.** Per the
> @senior-data-engineer + @scope-guardian co-sign (2026-06-22), it is **not** split into
> per-layer files yet — that would be premature sprawl against BACKLOG's "shrink to a single
> doc" guidance.
> - **Gate:** see `BACKLOG.md` → "Gym apparatus port" **Tier 1**. A real card is authored only
>   AFTER (1) v1 ships, AND (2) a real perf/cost finding exists to document.
> - **Owner:** @senior-data-engineer (no dedicated agent — Tier 2/3 REJECTED in BACKLOG).
> - **Authoring rule:** every ✅ card cites a real `file:line` from an actual fix. **No fabricated
>   findings, no invented citations, no speculative ✅ cards.** The one seed below is explicitly
>   🟡 APPLICABLE, not a claim of work done.
> - **Split rule (lazy):** promote a card into its own `0N_<layer>.md` file only when that one
>   layer earns **≥3–4 real cards** — split on volume, never preemptively on taxonomy.
> - **Co-sign is one event, already done** — authoring the first real card needs no fresh
>   ceremony, just the gate conditions met + a real citation.

## How to use
1. Each layer file holds cards. Fill one card per technique.
2. Classify every card: **✅ DONE** (applied + cited `file:line`) · **🟡 APPLICABLE** (real, not yet
   applied) · **⬜ N/A** (doesn't apply here — say why).
3. Every ✅ card MUST cite a real `path:line`. No fabricated citations.

## Card format (copy this)
```
### <ID> — <technique name>
- **Layer:** ingestion | bronze | silver | gold | serving | orchestration | dq | shared
- **Status:** ✅ DONE | 🟡 APPLICABLE | ⬜ N/A
- **What:** one line — the technique.
- **Why here:** why it matters for THIS workload (video + LLM + small structured output).
- **Applied at:** `path/to/file.sql:LN` (✅ only) — or "not yet".
- **Junior mistake:** the trap a junior falls into that this avoids.
- **Measured effect:** before → after (latency / $ / rows), if known.
```

## Layer map (planned files — none split out yet; see split rule above)
All layers are **⬜ gated · 0 cards** until the BACKLOG Tier-1 gate trips. The `File` column
names where a layer's cards will live IF/WHEN it earns ≥3–4 real cards; until then, the first
card for any layer is authored inline under "Seed cards" below, in this single doc.

| # | Layer | Eventual file | Status | Cards | Focus for this project |
|---|-------|---------------|--------|-------|------------------------|
| 01 | Drive→OneLake | `01_ingestion.md` | ⬜ gated | 0 | content-hash skip-existing, parallel download, manifest watermark |
| 02 | Gemini API | `02_extraction_llm.md` | ⬜ gated | 0 | Flash-vs-Pro, structured output, prompt caching, batch, idempotent skip |
| 03 | Bronze | `03_bronze.md` | ⬜ gated | 0 | Lakehouse Files JSON, partition by date, immutable append |
| 04 | Silver | `04_silver.md` | ⬜ gated | 0 | PySpark vectorization, Delta predicate/partition pushdown, array explode once |
| 05 | Gold | `05_gold.md` | ⬜ gated | 0 | bridge-table joins, incremental marts, Warehouse view materialization cost |
| 06 | Serving | `06_serving.md` | ⬜ gated | 0 | query shaping, Direct Lake refresh/caching, Copilot query cost |
| 07 | Fabric Data Factory | `07_orchestration.md` | ⬜ gated | 0 | activity retry/backoff config, gemini_api rate-limit sizing, dynamic pipeline parameterization |
| 08 | Quality | `08_dq.md` | ⬜ gated | 0 | gate ordering cheapest-first, quarantine-not-retry on LLM output |

## Seed cards (🟡 APPLICABLE only — directional, not work-done claims)
### OPT-EXT-01 — Cache raw Gemini JSON in Bronze forever (re-parse, never re-pay)
- **Layer:** bronze / extraction
- **Status:** 🟡 APPLICABLE (build pending)
- **What:** persist the verbatim Gemini response immutably; all re-models re-parse Bronze.
- **Why here:** the API call is the only real cost cliff; re-running it on a re-model is the
  single most expensive avoidable mistake (ADR-003, finops round-1).
- **Applied at:** not yet — target the Silver notebook's Bronze-read cell, never calling the API.
- **Junior mistake:** re-calling Gemini whenever the schema changes → re-billing the whole library.
- **Measured effect:** target — a full re-model of 500 videos = $0 API (vs $20–150 re-pay).

## Cross-layer junior-mistakes drill table (fill as cards land)
| # | Junior mistake | Layer | Card |
|---|----------------|-------|------|
| 1 | Re-call Gemini on every re-model | bronze/ext | OPT-EXT-01 |
| 2 | Over-provisioning the Spark session for KB–MB data | silver | (see ADR-008 — Fabric chosen for skill-fit despite small data; right-size the pool small) |
| 3 | Store ratios in the fact | gold | OPT-GOLD-?? |
| 4 | Synchronous per-video polling in Data Factory | orchestration | OPT-ORC-?? |
