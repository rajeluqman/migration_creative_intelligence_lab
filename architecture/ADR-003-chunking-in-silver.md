# ADR-003 — Semantic chunking lives in Silver; Bronze stays verbatim

- **Status:** Accepted
- **Date:** 2026-06-20
- **Deciders:** @data-architect (ratified), @senior-data-engineer, @finops-agent
- **Context refs:** `DATA_MODEL.md` §3, round-1 debate Q4/Q8, ADR-001

## Context

Gemini emits semantic chunks (meaning-bounded segments with `chunk_theme`, `sentiment`,
`standalone_score`, `next_compatible_themes[]`). The chunking decision is non-deterministic LLM
output. The question: which medallion layer owns chunking — Bronze, Silver, or Gold?

## Decision

**Chunking happens in Silver.** Bronze (`bronze_asset_raw`) stores the **verbatim, immutable**
Gemini JSON response plus `model_version` / `prompt_version`. Silver (`silver_chunk`) parses that
frozen Bronze JSON into one row per semantic chunk and applies cleaning + GE gates.

## Rationale

1. **Replay-without-repay (cost firewall).** Bronze must stay the verbatim API response so any
   downstream re-model is a **re-parse, never a re-pay** of the Gemini API — the single most
   important cost control (per @finops-agent, ADR-001 stack). Chunking in Bronze would bake a
   non-deterministic, billable decision into the raw layer and destroy that guarantee.
2. **Silver is the conform layer.** Parsing JSON → tabular chunk rows, removing filler, normalizing
   timestamps, range-gating `standalone_score` is exactly Silver's job. One Bronze blob → N Silver
   rows is a clean fan-out, not a risky transform.
3. **Gold is too late.** By Gold we already model relationships *between* chunks, which requires
   chunk boundaries to already exist. Chunking in Gold would pollute marts with parsing logic.
4. **Reproducibility.** With `model_version`/`prompt_version` on the immutable Bronze row, a chunking
   change is re-run from Bronze and diffed — no new API spend, full audit trail (ties to the
   golden-dataset quality gate).

## Rejected alternatives

| Alternative | Why rejected |
|-------------|--------------|
| **Chunk in Bronze** | Destroys replay-without-repay; bakes a non-deterministic billable decision into the raw layer. |
| **Chunk in Gold** | Too late — relationship modelling needs chunk boundaries first; pollutes marts with parsing. |
| **Chunk in the Python extraction step (pre-Bronze)** | Same problem as Bronze: the raw artifact would no longer be the verbatim API response. |

## Consequences

- **Positive:** Bronze is a permanent cost firewall and replay anchor; Silver owns all parsing/cleaning;
  re-chunking is free and auditable.
- **Negative / accepted:** Silver carries the GE schema + range gates (more test surface) — desired.
- **Locked:** Bronze is verbatim/immutable; moving chunking out of Silver requires a new ADR.
