# Learning Curriculum — Creative Intelligence Pipeline

> Owned by @cikgu. The learning PATH for this project: each module pairs a concept with the
> real artifact that embodies it, the WHY-before-HOW questions you must answer first, and a DIY
> build task. Teach in order; close each module with a `LEARNING_LOG.md` entry.
> Run @cikgu as a MAIN session (not a subagent) for actual teaching.

**Score:** start 100. Track in `LEARNING_LOG.md`. Hint = -5. < 60 forces a docs break.

| # | Module | You must be able to answer (WHY) | Artifact (read AFTER you've tried) | DIY |
|---|--------|----------------------------------|-----------------------------------|-----|
| **M0** | The domain & the goal | Why is this "creative intelligence" and not "video transcription"? What are the 3 legs (search / mix-match / correlation)? | `README.md`, `architecture/STACK_AND_FLOW.md` | — |
| **M1** | Medallion for unstructured + LLM | Why keep raw Gemini JSON forever? What does "re-parse, never re-pay" buy you? Why is chunking in Silver, not Bronze? | `ADR-003`, `DATA_MODEL.md §3` | explain the cost firewall in 3 sentences |
| **M2** | Graph + feature store (not star) | Why is a Kimball star the wrong shape here? What makes `fact_chunk` a "feature row" not a "fact"? | `ADR-002`, `ERD_consolidated.md` | draw the ERD from memory; check vs `erd.dbml` |
| **M3** | The semantic-chunk grain | Why is the chunk (not the video, not a 10s slice) the unit of value? How does `standalone_score` + `bridge_chunk_compatibility` kill "Frankenstein" videos? | `DATA_MODEL.md §1-2`, `SPEC_v1_search.md §3` | build the `bridge_chunk_compatibility` Gold view DIY (array explode) |
| **M4** | LLM-in-pipeline engineering | Why structured output (`responseSchema`) over regex markers? Why version the prompt + model? Why content-hash identity? | `SPEC_v1.5...` context, `STACK_AND_FLOW §1` | build `scripts/run_gemini_extract.py` skeleton DIY |
| **M5** | Testing non-deterministic pipelines | A row can be schema-valid yet semantically wrong — why? What are the 4 gates? Why quarantine-not-retry? Why is the golden-set the only deploy blocker? | `SPEC_v1.5... §7`, `cheatsheets/troubleshooting/00_INDEX.md` (TS-EXT-01) | write the GE "chunks length >= 1" expectation DIY |
| **M6** | PySpark notebooks + Fabric Warehouse mechanics | What's the Bronze/Silver notebook vs the Gold T-SQL view split? Why is Gold a `VIEW`, never a duplicated table? Why Fabric/PySpark now instead of the original DuckDB build? | `ADR-008`, `STACK_AND_FLOW.md`, the `notebooks/` + `warehouse/` tree | build the Gold `fact_chunk` T-SQL view DIY, diff vs ref |
| **M7** | Orchestration | Why retry/backoff activities + rate-limit-aware looping, not a synchronous polling loop? What is a Data Factory `ForEach` activity for? Why skip-existing? | `pipelines/creative_intel_fabric.json` (answer key), `STACK_AND_FLOW §2`, `DATA_MODEL §8` | DIY a parse-clean Data Factory pipeline from scratch; diff vs the reference; verify it validates with no activity errors |
| **M8** | Performance correlation layer | Why was `fact_ad_performance` vetoed then CONVERTED, not reversed? What is the position-aligned funnel↔chunk-role mapping? Why is `bridge_ad_chunk` a FACT not an inference? | `ADR-004`, `SPEC_v1.5... §4-5` | build `int_metric_chunk_alignment.sql` DIY (the time-range join) |
| **M9** | Statistical honesty | Why within-winners only? Why within-platform only? Why does n<5 BLOCK? What's survivorship bias here? | `SPEC_v1.5... §6`, `ADR-004` honesty gates | explain why you CANNOT say "this hook drove conversions" |
| **M11** | CI/CD & static gates | Why run CI at all on a solo project? Why "static gates" (lint/compile/contracts) and NOT a full Fabric-capacity run? Why is it $0 and secret-free? What does each gate actually catch? | `.github/workflows/ci.yml`, `cheatsheets/troubleshooting/00_INDEX.md` | DIY: add a deliberately-banned import and watch `tests/boundary_contract.py` turn the gate red, then fix it green |
| **M10** | Portfolio framing | What makes this distinct from the other 4 pipelines? Defend each big decision in interview form (incl. "walk me through your CI"). | all ADRs, `AGENT_ROSTER_RECOMMENDATION.md` | draft 5 resume bullets → @business-analyst honesty check |

## How a module runs (the ritual)
1. @cikgu poses the WHY questions. You answer from reasoning — NO reading yet.
2. You sketch the solution shape.
3. THEN you open the artifact and compare to your reasoning.
4. For DIY modules: @cikgu writes a `learning/diy/TICKET_<name>.md`; you build in
   `learning/diy/`; diff vs the real model line-by-line; quiz WHY on every gap.
5. LEARNING_LOG entry + score update.

## Suggested order
M0 → M1 → M2 → M3 → M6 (so you can actually run the Fabric build) → M11 (lock CI early so every
later DIY stays green) → M4 → M5 → M7 → M8 → M9 → M10.
(M6 is pulled early because the hands-on DIYs need a working notebook/Warehouse build; M11
right after so your CI catches regressions from M7-M9 onward.)
