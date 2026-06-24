# BRD — Business Requirements Document
## Creative Intelligence Pipeline

**Owner:** @product-owner (draft consolidated from `CLAUDE.md` by cabinet doc-gap convene)
**Status:** DRAFT — pending @product-owner review pass
**Date:** 2026-06-22
**Domain:** Advertising / creative-ops intelligence

---

## 1. Background

A client delivers a Google Drive folder of raw ad video — near-duplicate compilation
footage, mixing RAW source clips and sometimes already-EDITED winning ads — with no
structure and no reuse path. The marketing team currently has no way to search past
footage by message, tone, or reuse-safety; assembling a new ad means re-watching hours of
unstructured video. Source: `CLAUDE.md` Project Overview.

## 2. Stakeholders

| Role | Concern |
|------|---------|
| Marketing / creative team | Search past footage by hook/theme/sentiment; pull standalone-safe segments to assemble a new ad (the north-star user) |
| Client | Supplies the raw Drive footage and, for winning ads, Meta/TikTok performance CSVs (v1.5) |
| Owner (single-dev) | Builds and operates the pipeline; also fills @data-architect / @senior-data-engineer / @finops-agent roles in the cabinet |

## 3. Business Requirements

1. Turn messy raw ad video into a structured, queryable creative feature store — every
   line of dialogue, hook, theme, sentiment, and a `standalone_score` (can this clip be
   reused alone?). (`CLAUDE.md` Project Overview)
2. Resolve near-duplicate video identity deterministically (content hash), not by a
   random/arbitrary key — the client's footage is full of near-duplicate compilations.
   (`CLAUDE.md` "hard problems" §Identity; `architecture/DATA_MODEL.md` §4 `dim_asset.asset_id`)
3. Model chunks so they can be recombined without breaking the message — mixing 10s
   slices "Frankensteins" the creative. (`CLAUDE.md` "hard problems" §Frankenstein content;
   `architecture/ADR-002-graph-over-star.md`)
4. Chunk by semantic meaning, not fixed duration — Gemini emits `chunk_theme`,
   `sentiment`, `standalone_score`, `next_compatible_themes`. (`CLAUDE.md` "hard problems"
   §Semantic chunking; `architecture/ADR-003-chunking-in-silver.md`)
5. Gate a non-deterministic LLM pipeline so a schema-valid-but-wrong row never silently
   reaches Gold. (`CLAUDE.md` "hard problems" §Testing; `architecture/DATA_MODEL.md` §7)
6. **(v1.5, not v1)** Where winning ads arrive with Meta/TikTok funnel metrics, surface a
   descriptive, within-winners correlation between chunk theme/role and performance — never
   a causal claim. (`architecture/ADR-004-performance-veto-converted.md`)

## 4. Business Definitions

- **Asset** = one creative video, RAW or EDITED. Identity = `asset_id`, the SHA-256 of the
  video bytes (not a random key) — this is the near-duplicate answer.
- **Chunk** = one semantically complete marketing beat (Hook, Problem, Solution, Social
  Proof, CTA…) — the grain of the whole model, emitted by Gemini at meaning boundaries,
  not fixed-duration slices.
- **`standalone_score`** = 1–5, GE range-gated — how safe a chunk is to reuse alone,
  outside its original ad.
- **`next_compatible_themes`** = the set of chunk themes that can validly follow this
  chunk in a new assembly, without breaking the message (anti-Frankenstein).
- **Near-duplicate** = two assets that are substantially the same footage (e.g. a
  compilation re-export). Flagged via `dq_flag = likely_near_dup` (MEDIUM signal, no
  auto-merge) — `architecture/DATA_MODEL.md` §4.
- **Winning ad (v1.5)** = an EDITED asset that actually ran on a platform and has
  Meta/TikTok funnel metrics attached via `fact_ad_performance`.

## 5. Scope Notes

v1 = the queryable creative feature store only, per `CLAUDE.md` "v1 Scope (LOCKED)".

**OUT of v1 (v2 BACKLOG — `BACKLOG.md`):**
- AI creative search engine (an app on top of the feature store)
- RAG script/brief generator
- Creative-ops analytics dashboard
- Automated tagging / asset archiving
- ROAS / ad-performance ingestion beyond the within-winners correlation layer (v1.5 only)
- Dedicated vector DB (attribute-filtered T-SQL Warehouse views over Direct Lake cover v1
  search; Fabric Copilot/Azure OpenAI is a QA/summarization veneer, not a vector index — ADR-008)
- Perceptual/fuzzy near-duplicate dedup (the model's answer is content-hash + a flagged
  signal, not auto-merge — see `architecture/DATA_MODEL.md` §4)

**IN for v1.5 (additive, zero changes to v1 objects):** the performance-correlation layer
per `architecture/ADR-004-performance-veto-converted.md` and
`architecture/DATA_MODEL_v1.5_PERFORMANCE.md`.

## 6. KPIs / Targets

This is a single-dev portfolio build, not a production system with a paying-customer SLA —
the targets below are the ones already committed elsewhere in the architecture, restated
here for one-place visibility. None are newly invented for this BRD.

| Metric | Target | Source |
|--------|--------|--------|
| Golden-dataset semantic agreement | ≥80% (Jaccard, ±1 on score) — the only gate allowed to fail a deploy | `architecture/DATA_MODEL.md` §7 gate 3 |
| Silver constraint-pass rate before Gold build | ≥95% | `architecture/DATA_MODEL.md` §7 promotion rule |
| Gemini cost ceiling (cost firewall) | 40 videos ≈ $1–5; 500 ≈ $20–150 | `architecture/DATA_MODEL.md` §9 |
| v1.5 correlation insight surfacing | n<5 BLOCK · n 5–11 DIRECTIONAL · n≥12 (≥5/group) SUGGESTIVE | `architecture/ADR-004-performance-veto-converted.md` G3 |

**Tracked, no committed target yet** (flag honestly rather than invent a number):
% of Gold chunks with `standalone_score >= 4` (the reusable-inventory signal the
north-star query depends on) — worth watching once Gold has real rows, no threshold set.

## 7. SLA

No production SLA. This is a batch, on-demand pipeline run (not a live system with
paying-customer uptime commitments) — stated honestly rather than fabricated. The closest
operational commitment is the cost firewall above (§6) and the FinOps discipline around the
Fabric capacity SKU (pause/teardown when idle — `architecture/ADR-008-migrate-to-microsoft-fabric.md`,
`.claude/agents/finops-agent.md`; supersedes ADR-005's Snowflake-trial teardown framing).

## 8. Sign-off Gate

| Agent | Status | Reason | Date |
|-------|--------|--------|------|
| @data-architect | ✅ APPROVED (doc-gap convene) | BRD addition is documentation of already-ratified decisions, no new data-model objects; required §4/§6 stale-veto reconciliation completed first | 2026-06-22 |
| @scope-guardian | ✅ APPROVED (doc-gap convene) | Documentation-debt closure, not scope creep — restates CLAUDE.md verbatim, no new feature | 2026-06-22 |
| @product-owner | ⬜ PENDING | This draft was consolidated from CLAUDE.md by the doc-gap convene, not yet reviewed by @product-owner directly | — |
