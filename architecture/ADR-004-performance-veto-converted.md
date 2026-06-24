# ADR-004 — Performance-correlation layer: veto converted, not reversed

- **Status:** Accepted (supersedes the round-1 veto on `fact_ad_performance`)
- **Date:** 2026-06-20
- **Deciders:** @data-architect (ratified), @scope-guardian (veto lifted→converted), @business-analyst, @data-quality-steward, @senior-data-engineer
- **Context refs:** `DATA_MODEL_v1.5_PERFORMANCE.md`, round-2 debate, ADR-002

## Context

Round 1 vetoed `fact_ad_performance` + proxy attribution because (a) performance data was "often
absent" and (b) attributing an edited ad's conversions *backward* onto its RAW source clips is
manufactured causality. The premise changed: clients now send **winning ads that arrive WITH
Meta/TikTok funnel metrics**, and the owner wants performance-correlation ("which video performs is
no longer luck").

## Decision

**Convert** (not reverse) the round-1 veto. Add a **descriptive, within-winners, within-platform
performance-correlation layer**: `bronze_ad_performance_raw`, `fact_ad_performance` (grain: 1 edited
ad × 1 platform × 1 day, raw counts), `bridge_ad_chunk` (editor's asserted cut), `dim_platform`,
`fct_ad_kpi` (ratios view), and one correlation mart. Metrics attach to the **EDITED ad that
actually ran** — never propagated backward onto RAW via `parent_asset_id`.

## Rationale

1. **The principle did not move; the data crossed to the correct side of it.** The vetoed object was
   *backward propagation across the lineage edge*. The new object attaches metrics to the edited ad
   the platform actually measured — a different object on a different grain. *Provenance before
   propagation* holds.
2. **Position-aligned attribution is defensible.** A funnel metric maps to a chunk **role/position**,
   not the whole ad: Hook Rate (3s) ↔ the hook chunk, CTR-Link ↔ the CTA chunk (time-range join via
   `int_metric_chunk_alignment`). This shrinks the attribution from "whole-ad black box" to
   "stage-scoped" — real progress, still correlation not causation.
3. **Edited ads are chunked too.** To map metrics to chunk roles on the edited ad's own clock, the
   edited ad is run through the existing chunking pipeline (ADR-003), producing its own `fact_chunk`
   rows. Lineage to RAW stays navigation-only — no metric rides backward.
4. **Raw counts only; ratios derived.** Sum-of-ratios ≠ ratio-of-sums; ratios live in `fct_ad_kpi`.

## Binding honesty gates (governance — release blockers)

- **G1 within-winners:** library is winners-only (no losing baseline) → only "AMONG ads that already
  succeeded, theme A appears more in top performers" is honest. Causal/lift language is forbidden output.
- **G2 within-platform:** no pooling Meta + TikTok (different denominators/windows); cross-platform =
  rank-direction agreement only.
- **G3 sample ladder:** n<5 BLOCK · 5–11 DIRECTIONAL (Spearman) · ≥12 & ≥5/group SUGGESTIVE
  (Mann-Whitney U + Bonferroni).
- **G4 double-count guard:** 1 ad → N chunks; aggregate at theme/sentiment/role grain.

## Rejected / still-vetoed (→ v2 backlog)

| Item | Why still out |
|------|---------------|
| Proxy metrics on RAW via `parent_asset_id` | **Permanent** — manufactured causality. |
| Causal "chunk caused conversion" claims | Requires a controlled swap-one-chunk creative experiment. |
| Predictive ML scoring / variant factory / RAG / vector DB | Gated on the correlation mart proving signal first; winners-only n<12 cannot train an honest predictor. |
| Cross-platform pooled magnitudes | Different measurement semantics (`dim_platform`). |
| Connectorized ingest (Fivetran/Airbyte/Meta-API) | Over-engineering at 3–15 ads; manual CSV→S3 until ~50+ ads/week + DA TCO sign-off. |

## Consequences

- **Positive:** "no longer luck" is delivered as an honest, gated correlation mart; zero changes to
  existing v1 objects; sequenced as v1.5 after the v1 search demo ships.
- **Negative / accepted:** small-n means most insights stay DIRECTIONAL, not "proven" — disclosed by design.
- **Locked:** honesty gates are release blockers owned by @data-quality-steward; lifting any v2 item
  requires a new ADR citing demonstrated signal.
