# DATA MODEL — v1.5 PERFORMANCE ADDENDUM

**Owner:** @data-architect · **Status:** Ratified 2026-06-20 (Round 2 convene)
**Extends:** `DATA_MODEL.md` (v1 Architecture of Record) · **Debate:** `../debate/ROUND_02_PERFORMANCE_DEBATE.md`

> **What changed:** winning ads now arrive **with** Meta/TikTok funnel metrics. Round-1
> Veto 1 (`fact_ad_performance`) is **CONVERTED** — metrics now attach to the **EDITED ad
> that actually ran** (no backward propagation onto raw sources). This addendum adds a
> **descriptive, within-winners, within-platform performance-correlation layer**. It touches
> **zero** existing v1 objects.

---

## 1. Governing principle (unchanged, reaffirmed)

*Provenance before propagation — a model must not encode an inference as if it were a fact.*

| | Round 1 (vetoed) | Round 2 (allowed) |
|---|---|---|
| Where metrics attach | pushed **backward** onto RAW via `parent_asset_id` | on the **EDITED ad that ran** |
| Claim type | "raw clip drove $40K" (manufactured causality) | "among winners, theme A appears more in top performers" (labeled correlation) |
| Lineage edge | abused for attribution | **navigation/search only** (unchanged) |

**Permanently forbidden:** backward metric propagation across `parent_asset_id`; any claim a
specific chunk *caused* a metric (platforms measure the whole **bundle**); market-wide
"driver" claims from a winners-only library.

## 2. The funnel metrics

| Metric | Definition (numerator / denominator) | Stored? | Target |
|--------|--------------------------------------|---------|--------|
| Hook Rate | `plays_3s / impressions` | derived | ≥25% |
| Hold Rate | `plays_25 / plays_3s`, `plays_50 / plays_3s` | derived | watch drop-off |
| Average Play Time | `sum_watch_time_sec / play_count` | derived (store the two counts) | ≥5s |
| CTR (Link) | `link_clicks / impressions` — **NOT** CTR-all | derived | ≥1% |
| CPA / Cost Per Result | `spend / results` | derived | — |
| CVR | `results / link_clicks` | derived | 1–3% |

**Rule:** the base fact stores **raw counts only**; every ratio is derived in `fct_ad_kpi`.
*Sum-of-ratios ≠ ratio-of-sums* — storing ratios breaks re-aggregation and rots on redefinition.

## 3. New objects (zero changes to existing v1 objects)

### `bronze_ad_performance_raw` (own bronze source)
Verbatim CSV/API capture · append-only · immutable · `+ load_ts, source_file, content_hash`.
Re-parse-not-repay contract (platforms backdate/restate → preserve the original pull). **Not**
mixed with `bronze_asset_raw`.

### `fact_ad_performance` — Gold
**Grain (locked): 1 edited-ad (`ad_id`) × 1 platform × 1 DAY.** Daily snapshot, additive
counts (NOT lifetime cumulative). Raw counts only:
| column | type | notes |
|--------|------|-------|
| `ad_id` (PK part) | VARCHAR | platform creative id — the thing that ran (≠ asset_id) |
| `platform_id` (PK part, FK) | VARCHAR | → dim_platform |
| `perf_date` (PK part) | DATE | daily grain |
| `asset_id` (FK) | VARCHAR | → dim_asset, **constrained `asset_type='EDITED'`** |
| `impressions` | BIGINT | |
| `plays_3s`,`plays_25`,`plays_50`,`plays_75`,`plays_100` | BIGINT | retention checkpoints |
| `sum_watch_time_sec`,`play_count` | DECIMAL/BIGINT | derive Average Play Time, never store the ratio |
| `link_clicks`,`results`,`spend` | BIGINT/DECIMAL | |
| `load_ts` | TIMESTAMP | |

### `bridge_ad_chunk` — Gold (THE UNLOCK)
An **editor's recorded assertion of what is physically in the cut** — a fact, not an inference.
| column | type | notes |
|--------|------|-------|
| `ad_id` (FK) | VARCHAR | → fact_ad_performance |
| `asset_id` (FK) | VARCHAR | the EDITED asset |
| `chunk_id` (FK) | VARCHAR | → **edited-ad** `fact_chunk` row (see §4) |
| `chunk_role` | VARCHAR | enum: `hook` \| `body` \| `social_proof` \| `cta` |
| `position_in_ad` | INT | sequence in the final cut |
| `start_ts` / `end_ts` | TIME | in the **EDITED** timeline |
| PK | (`ad_id`,`chunk_id`) | 1 ad → N chunks |

### `dim_platform` — Gold (tiny, SCD0) — the anti-pooling key
| column | notes |
|--------|-------|
| `platform_id` (PK) | |
| `platform_name` | meta \| tiktok |
| `hook_window_sec` | Meta=3, TikTok=6 — drives the time-range join, never hardcoded |
| `hold_milestones[]` | retention checkpoint definitions |

### `fct_ad_kpi` — metric layer (view)
Derives all ratios from `fact_ad_performance` with explicit denominators. Rates range-tested
∈ [0,1]. The only place ratios live.

### correlation mart (×1) — the "no longer luck" engine
Joins `fact_ad_performance → bridge_ad_chunk → fact_chunk` at **theme / sentiment / chunk-role
grain, within a single platform**. Double-count-guarded (never sum ad metrics across the
bridge's N chunks). Carries `sample_size` + regime label (§6).

## 4. Keystone ruling — edited ads are chunked too

The position-aligned Hook-Rate mapping needs chunks on the **edited ad's own clock**.
Therefore the **EDITED ad is run through the SAME Bronze→Silver→Gold chunking pipeline** as raw
assets, producing its **own `fact_chunk` rows** (`asset_id`=edited, timestamps in the edited
timeline). `bridge_ad_chunk.chunk_id` references those rows.

**Guardrail:** edited-ad chunks are NEVER fused with / averaged into the RAW source chunks
reachable via `bridge_asset_lineage`. Lineage stays a **navigation** edge. The "mine the
library for more chunks like the winning Hook" traversal —
`fact_ad_performance → bridge_ad_chunk → fact_chunk(edited) → bridge_asset_lineage → raw source →
candidate pool` — is a **search**, not an attribution. No metric rides backward across lineage.

Candidate-mining pool:
```sql
fact_chunk
WHERE chunk_theme IN (themes from winning Hook chunks)
  AND standalone_score >= 4
  AND chunk_id NOT IN (SELECT chunk_id FROM bridge_ad_chunk)   -- unused raw inventory
```

## 5. Core mechanism — position-aligned funnel↔chunk-role mapping

A funnel metric maps to a chunk **role/position**, not the whole ad. **Time-range join**, not
equality:
- **Hook Rate (3s view)** ↔ chunk where `start_ts <= hook_window_sec < end_ts`
  (`hook_window_sec` from `dim_platform`: Meta 3s, TikTok 6s).
- **CTR (Link)** ↔ the chunk with `chunk_role='cta'`.
- **Retention 25/50/75/100%** ↔ the chunk covering that elapsed-time position.

**Tie-break (binding):** straddling anchor → chunk with **greater temporal overlap**;
exact-midpoint tie → **earlier** chunk (`position_in_ad ASC`). Deterministic, documented.

**`coverage_confidence` (binding):** HIGH (anchor cleanly inside one chunk) · MEDIUM (straddle
resolved by tie-break) · LOW (no chunk covers the anchor). **LOW rows are surfaced but excluded
from correlation aggregates** by default.

## 6. Binding honesty gates (governance — release blockers)

@data-quality-steward owns this suite; v1.5 does not ship without it.

- **G1 — Within-winners framing (verbatim on every output):**
  *"AMONG ads that already succeeded, theme A appears more often in the top performers."*
  Lift / causal / "drives conversion" language is **forbidden output** and gated. (Library is
  winners-only → no losing baseline → no counterfactual → no driver claim.)
- **G2 — Within-platform only:** NO pooling of Meta + TikTok (different denominators/windows).
  Cross-platform = **rank-direction agreement only** ("theme A ranks top-3 on both"), never
  pooled magnitude.
- **G3 — Sample-size ladder** (`sample_size` column gates insight surfacing):

  | n (within-platform, within-group) | Regime | Method |
  |---|---|---|
  | **n < 5** | **BLOCK** (anecdotal, not surfaced) | — |
  | **n = 5–11** | **DIRECTIONAL** (labeled "not significant") | Spearman / rank |
  | **n ≥ 12 AND ≥5/group** | **SUGGESTIVE** | Mann-Whitney U (non-parametric) + Bonferroni |

- **G4 — Double-count guard:** `bridge_ad_chunk` is 1 ad → N chunks; aggregate at
  theme/sentiment/role grain; a GE expectation asserts no ad's impressions are multiplied by
  chunk count (no dbt test — dbt is dropped, ADR-008).
- **GE gates:** rates ∈[0,1]; counts & spend ≥0; `platform` & `chunk_role` accepted-values;
  every `ad_id` resolves to ≥1 chunk via bridge (referential check); `asset_id` FK is
  `asset_type='EDITED'`; `sample_size` present and gating.

## 7. Ingest & sequencing

- **v1 search demo ships FIRST, untouched.** v1.5 is purely additive (zero existing-object changes).
- **Ingest = manual CSV → OneLake** at 3–15 ads. `ad_id → asset_id` mapping is
  manual/filename-based, enforced via a GE referential check (no dbt — dbt is dropped,
  ADR-008). Connector (Fivetran/Airbyte/Meta-API) revisited only past **~50+ ads/week with
  @data-architect TCO sign-off**.

## 8. v1.5 scope line & what stays vetoed

**IN (v1.5):** `bronze_ad_performance_raw` + `fact_ad_performance` + `bridge_ad_chunk` +
`dim_platform` + `fct_ad_kpi` view + **one** correlation mart + edited-ad `fact_chunk` rows.

**🛑 STILL VETOED → v2 backlog:** predictive / auto-optimizing ML scoring · variant factory ·
RAG · vector DB (all gated on the mart **proving signal first** — winners-only, survivorship-
biased, n<12 cannot train an honest predictor) · causal "chunk caused conversion" claims
(require a controlled **swap-one-chunk creative experiment**) · backward metric propagation
across `parent_asset_id` (**permanent**) · cross-platform pooled magnitudes · connectorized
ingest (until volume + TCO sign-off).
