# AGENT ROSTER RECOMMENDATION — Creative Intelligence Pipeline

**Decided:** 2026-06-20 · **Proposed by** @product-owner · **Ratified by** @data-architect
**Context:** This is a single-dev portfolio build, much smaller than the 20-agent gym it
borrows from. The roster must ship, not teach.

## Verdict: **6 core agents** (hard cap 7)

| # | Agent | Model | Why essential here |
|---|-------|-------|--------------------|
| 1 | **@data-architect** | Opus | The hard part is the model itself (graph vs star, Bronze/Silver/Gold immutability, chunk grain). Veto holder. |
| 2 | **@senior-data-engineer** | Sonnet | Builds the pipeline; owns LLM-call idempotency, skip-existing, deferrable orchestration. |
| 3 | **@data-quality-steward** | Sonnet | Non-negotiable for an LLM pipeline — the 4 gates, "unreliable narration" risk, golden-dataset threshold. |
| 4 | **@scope-guardian** | Sonnet | Without it this over-scopes (the Gemini chat already sprawled into 4 apps). Keeps v1 honest. |
| 5 | **@product-owner** | Sonnet | Owns the single north-star user story + definition of done; keeps it demo-able. |
| 6 | **@finops-agent** | Sonnet | Gemini token cost is existential at scale; part-time review is enough. |
| 7 | **@qa-engineer** | Haiku | **Conditional** — activate when golden-dataset testing becomes its own workstream (it will, per the Q6 ruling). De-facto 7th on activation. |

## Cut as dead weight for THIS project

| Agent | Why not seated |
|-------|----------------|
| @business-analyst | Delivered a decisive one-time Q3 ruling (now absorbed into the AoR). No standing stakeholders beyond the owner. **Consultable, not seated.** |
| @data-platform-engineer | Its orchestration ruling (deferrable Airflow, binary-store separation) is now codified in the AoR. No ongoing seat at local-Airflow scale. **Consultable, not seated.** |
| @project-manager | No team to manage on a single-dev build. |
| @analytics-engineer | Its dbt-layering contribution is folded into senior-DE's remit at this size. |
| @devops-orchestrator, @infra-reality-agent | No cloud-fleet / MWAA provisioning in v1 (local Airflow). |
| @documentation-sherpa, @cheatsheet-generator | Docs are lightweight here; not a separate workstream. |
| @optimization-librarian, @incident-responder, @bottleneck-saboteur, @cikgu | **Gym/training apparatus** — this project ships a product, it does not run a learning gym. |

## Notes
- "Consultable, not seated" = bring @business-analyst / @data-platform-engineer back for a
  single ruling if a new question arises in their lane, but they hold no standing review seat.
- If v2 unlocks the backlog (vector DB / RAG generator / ad-performance ingestion), re-open
  the roster — RAG would likely re-seat a quality/eval role and possibly an ML-leaning
  engineer, and ad-performance ingestion would re-seat @data-platform-engineer + @business-analyst.
- This roster is for the **Creative Intelligence project only**; it does not alter the gym's
  20-agent cabinet.
