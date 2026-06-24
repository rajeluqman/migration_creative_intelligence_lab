# ROUND 2 DEBATE LOG — Performance Data Arrives

**Date:** 2026-06-20 · **Facilitator:** @data-architect (veto holder, reconsidering own Veto 1)
**Trigger:** Premise change — client now sends **winning ads that arrive WITH Meta/TikTok
funnel metrics**. Owner wants performance-correlation: "which video performs is no longer luck."
**Outcome:** Round-1 Veto 1 **CONVERTED** (not lifted) → new **v1.5 Performance Addendum**.
See `../architecture/DATA_MODEL_v1.5_PERFORMANCE.md`.

---

## The metrics in scope (funnel order)
`Impression → Hook Rate (3s plays / impressions, ≥25%) → Average Play Time (≥5s) →
CTR-Link (link_clicks / impressions, ≥1%) → Cost Per Result / CPA → CVR (1–3%)`
plus Hold Rate (plays at 25/50/75/100%). CTR-**Link** ≠ CTR-**All** (vanity).

---

## Panel positions (condensed)

### @business-analyst
- **Store raw counts, derive ratios** in the metric layer (ratios can't re-aggregate;
  avg of avg is wrong). "Average Play Time" needs an explicit denominator → store
  `sum_watch_time_sec` + `play_count`. Flag CTR-link distinct from CTR-all.
- **STRONGEST IDEA — position-aligned mapping:** a funnel metric maps to a chunk **role**,
  not the whole ad. Hook Rate (3s) ↔ the chunk whose `[start_ts,end_ts]` contains the 3s
  mark; CTR-Link ↔ the CTA chunk. **Time-range join**, not equality; needs a straddle
  tie-break + `coverage_confidence` flag.
- Honest claim = correlation across the winning-ad population, chunk-role-stratified.
  Causal ("this chunk caused conversion") needs a controlled swap-one-chunk test = v2.
  Day-one question: *"Across our winning ads, which Hook-chunk themes/sentiments correlate
  with Hook Rate ≥25%?"*

### @senior-data-engineer
- `fact_ad_performance` grain = **1 edited-ad × 1 platform × 1 DAY** (daily snapshot,
  additive; NOT lifetime — platforms restate retroactively). Raw counts only + `ad_id`
  (platform creative id), `asset_id` FK (`asset_type='EDITED'`), `platform_id`, `perf_date`.
- **`bridge_ad_chunk` = the real unlock** — `ad_id, asset_id, chunk_id, chunk_role, position_in_ad,
  start_ts/end_ts (edited timeline)`. It is an **editor's assertion of the cut** (a fact),
  not a statistical inference — same standard round 1 demanded of lineage.
- Mine-the-library traversal: `fact_ad_performance → bridge_ad_chunk → fact_chunk →
  bridge_asset_lineage → raw source`; candidate pool = `fact_chunk WHERE theme IN(winning)
  AND standalone_score>=4 AND chunk_id NOT IN(bridge_ad_chunk)`.
- `dim_platform` needed (Meta 3s vs TikTok 6s windows differ). Perf gets its **own** bronze
  source `bronze_ad_performance_raw` (verbatim, re-parse-not-repay), not mixed with video.
- Net: 1 bronze source, 2 Gold tables, 1 tiny dim, **zero changes to existing objects**.

### @analytics-engineer
- Conform Meta vs TikTok via `stg_meta_perf` + `stg_tiktok_perf` → union + platform column +
  conformed names. Ratios in `fct_ad_kpi` view / metric layer, **never** the base fact.
- Correlation mart joins fact → bridge → chunk; **GUARD double-count** (1 ad → N chunks;
  naive join inflates N-fold) → aggregate at theme/sentiment/role grain.
- dbt tests: rates ∈[0,1], `platform` accepted_values, FK relationships.

### @data-quality-steward — SOFT VETO until honesty gates exist
- Attribution trap is one grain deeper than round 1: platforms emit metrics for the **whole
  bundle**, never per `chunk_id`. Model must **never** claim chunk causes metric.
- **Survivorship bias is fatal to lift-claims:** library = winners only, no losing baseline →
  only honest framing is *"AMONG ads that already succeeded, theme A appears more in top
  performers"* (within-winners ranking), stated verbatim on every output.
- **Sample ladder:** n<5 BLOCK (anecdotal); n=5–11 DIRECTIONAL (Spearman/rank, "not
  significant"); n≥12 & ≥5/group SUGGESTIVE (Mann-Whitney U + Bonferroni).
- **Within-platform only** — no pooling (different denominators/windows). Cross-platform =
  rank-direction agreement only.
- GE gates: rates∈[0,1], counts/spend≥0, platform enum, every ad→≥1 chunk via bridge,
  `sample_size` column gates surfacing.

### @scope-guardian — VETO LIFTED but CONVERTED to v1.5
- Premise changed = ruling changed (not creep). But **v1 search demo ships first, untouched.**
- v1.5 IN: `fact_ad_performance` + `bridge_ad_chunk` + one correlation mart (SQL).
- 🛑 Pre-emptive VETO on over-reach: predictive ML scoring / "auto-optimizing variant factory"
  / RAG / vector DB → v2, only after the mart proves signal exists.
- Ingest = **manual CSV→S3** (Fivetran/Airbyte/Meta-API = over-engineering at 3–15 ads;
  connector only past ~50+ ads/week with DA TCO sign-off).

---

## @data-architect — binding round-2 rulings

### Veto 1 → CONVERTED, not reversed
The original principle was *"no backward propagation across `parent_asset_id` — provenance
before propagation."* The vetoed object was pushing the edited ad's metrics **backward onto
RAW sources**. The new proposal attaches metrics to **the EDITED ad that actually ran** — a
different object on a different grain, no backward propagation. **The line did not move; the
data crossed to the correct side of it.**
- **NOW ALLOWED:** `fact_ad_performance` on the edited ad; correlation across the winning-ad
  population; chunk-role-stratified discovery.
- **STILL FORBIDDEN (permanent):** ❌ propagating edited metrics back onto RAW via lineage;
  ❌ any claim a specific chunk *caused* a metric (bundle-level measurement); ❌ market-wide
  "driver" claims from a winners-only library.

### Keystone ruling — the EDITED ad is run through the chunking pipeline
The position-aligned Hook-Rate mapping needs chunks **on the edited ad's own clock**. So the
**edited ad is run through the SAME Bronze→Silver→Gold chunking pipeline**, producing its
**own `fact_chunk` rows** (`asset_id`=edited, `start_ts/end_ts` in edited timeline).
`bridge_ad_chunk.chunk_id` references THOSE rows. **Guardrail:** edited-ad chunks are never
fused with / averaged into the RAW source chunks reachable via lineage — lineage stays a
**navigation** edge; the "mine the library" traversal is a **search**, not an attribution.
No metric ever rides backward across lineage.

### Ratified
- New tables: `bronze_ad_performance_raw`, `fact_ad_performance` (daily, raw counts),
  `bridge_ad_chunk` (editor's asserted cut), `dim_platform` (anti-pooling key), `fct_ad_kpi`
  (ratios view), **one** correlation mart. Edited-ad `fact_chunk` rows via existing pipeline.
- Position-aligned funnel↔chunk-role mapping = **core mechanism**: time-range join +
  greater-overlap tie-break (midpoint tie → earlier chunk) + `coverage_confidence`
  (LOW excluded from aggregates). Platform view-window from `dim_platform`, never hardcoded.
- Honesty regime = **binding governance gates** (within-winners verbatim, within-platform
  only, sample ladder, double-count guard, GE suite). v1.5 does not ship without them;
  @data-quality-steward owns the suite as a **release blocker**.
- v1.5 sequencing (v1 first), manual CSV→S3 ingest, and the pre-emptive ML veto — all ratified.

### 🛑 Pre-emptive veto upheld (v2 backlog)
Predictive/auto-optimizing ML scoring · variant factory · RAG · vector DB — all gated on the
correlation mart proving signal first (a winners-only, survivorship-biased, n<12 sample
cannot train an honest predictor). Causal claims require a controlled swap-one-chunk
experiment = v2 design, not a query.

**Verdict: APPROVED for v1.5 as specified.** Hand to @senior-DE (logical→physical) with
@analytics-engineer; @data-quality-steward owns the gate suite.
