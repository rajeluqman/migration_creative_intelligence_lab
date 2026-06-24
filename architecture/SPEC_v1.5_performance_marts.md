# BUILD SPEC — v1.5 Performance Marts (`fct_ad_kpi` + correlation layer)

**Status:** Draft for build · **Owner:** @senior-data-engineer + @analytics-engineer
**Authority:** `DATA_MODEL_v1.5_PERFORMANCE.md` (ratified 2026-06-20) — this spec implements it,
does not change it. **Honesty gates (§7) are release blockers** owned by @data-quality-steward.
**Engine (ADR-008, Fabric build):** PySpark notebooks (Bronze→Silver, the `stg_*`/`int_*`
conform+union steps below) + Fabric Warehouse T-SQL `VIEW`s (Gold, `fact_ad_performance` onward)
over a OneLake shortcut. No dbt — object names below are notebook cells / T-SQL views, not
dbt models, and `{{ ref(...) }}` is replaced by plain object names throughout. SQL snippets
below illustrate logic, not final syntax — exact T-SQL (`CAST` vs `::`, etc.) is finalized
when the Gold Warehouse views are actually built (F2).

---

## 0. Model lineage

```
bronze_ad_performance_raw (Meta CSV)      bronze_ad_performance_raw (TikTok CSV)
            │                                          │
       stg_meta_perf                              stg_tiktok_perf
            └──────────────────┬───────────────────────┘
                       int_ad_perf_unioned        (conform → 1 schema, +platform)
                               │
                       fact_ad_performance        (Gold · grain: ad×platform×DAY · raw counts)
                               │
        ┌──────────────────────┼─────────────────────────────────────┐
        │                      │                                      │
   fct_ad_kpi            int_metric_chunk_alignment            (bridge_ad_chunk + fact_chunk
   (ratios view)         (which chunk owns which metric)         + dim_platform + dim_asset)
        │                      │
        └─────────┬────────────┘
            fct_ad_metric_chunk            (1 ad × platform × metric → value + mapped chunk + features)
                  │
        mart_chunk_perf_correlation        (platform × metric × feature → n_ads, median, regime)  ← SURFACED
```

> **Decision boundary:** T-SQL marts produce grouped aggregates + `sample_size` + a directional
> rank. The **statistical significance test** (Spearman / Mann-Whitney U + Bonferroni) is a
> thin **Python post-step** (`scripts/significance_post_step.py`, a Fabric notebook: Warehouse
> query → pandas → scipy) that only runs for the `SUGGESTIVE` tier — SQL does not compute
> p-values. See §6.

---

## 1. Staging — multi-platform conformance

Two parallel models, conform to one schema, union. Conformed column names are canonical;
platform-native names are mapped here and **only** here.

`stg_meta_perf` / `stg_tiktok_perf` → emit identical columns:

| canonical column | Meta source | TikTok source |
|------------------|-------------|----------------|
| `ad_id` | `ad_id` | `ad_id` |
| `perf_date` | `date` | `stat_time_day` |
| `impressions` | `impressions` | `impressions` |
| `plays_3s` | `video_3_sec_watched_actions` | `video_views_p_3s` (count, not rate) |
| `plays_25/50/75/100` | `video_p25/p50/p75/p100_watched_actions` | `video_views_p25/p50/p75/p100` |
| `sum_watch_time_sec` | `video_avg_time_watched_actions × plays` ¹ | `total_watch_time` |
| `play_count` | `video_play_actions` | `video_views` |
| `link_clicks` | `inline_link_clicks` | `clicks_destination` |
| `results` | `actions{purchase|lead}` | `conversions` |
| `spend` | `spend` | `spend` |

¹ If Meta only exposes the *average*, reconstruct `sum_watch_time_sec = avg_time_watched ×
play_count` at staging so the fact stores a **summable** quantity (BA ruling — never store a
bare average).

```sql
-- int_ad_perf_unioned (Silver, PySpark notebook conform+union step)
select 'meta'   as platform_name, * from stg_meta_perf
union all
select 'tiktok' as platform_name, * from stg_tiktok_perf
```
Silver dedup key: `(ad_id, platform_name, perf_date)` — last-write-wins on `load_ts`
(platforms restate; keep the latest pull of a given day).

---

## 2. `fact_ad_performance` (Gold)

Grain: **1 edited-ad × 1 platform × 1 DAY**. Raw counts only — **no ratios**.

```sql
-- warehouse/performance/fact_ad_performance.sql  (Fabric Warehouse, T-SQL VIEW, F2)
-- int_ad_perf_unioned / dim_platform / map_ad_asset are Silver Delta tables (PySpark notebook
-- conform+union step), reached here via a OneLake shortcut — no dbt ref()
select
    u.ad_id,
    p.platform_id,
    u.perf_date,
    m.asset_id,                       -- resolved EDITED asset (see §2.1)
    u.impressions,
    u.plays_3s, u.plays_25, u.plays_50, u.plays_75, u.plays_100,
    u.sum_watch_time_sec, u.play_count,
    u.link_clicks, u.results, u.spend,
    current_timestamp as load_ts
from int_ad_perf_unioned u
join dim_platform p on p.platform_name = u.platform_name
join map_ad_asset m  on m.ad_id = u.ad_id   -- manual ad_id→asset_id seed (§2.1)
```

### 2.1 `ad_id → asset_id` mapping (manual seed, v1.5)
At 3–15 ads, this is a hand-maintained seed `seeds/map_ad_asset.csv`
(`ad_id, asset_id`). Enforced, not assumed — by Great Expectations on the Silver Delta table
(no dbt; dbt is dropped, ADR-008):
- referential check: `fact_ad_performance.asset_id` → `dim_asset.asset_id`
- accepted-values gate: the joined `dim_asset.asset_type` must be `'EDITED'`
- not-null gate on the mapped `asset_id` (an unmapped ad fails the build — no silent orphan).

---

## 3. `fct_ad_kpi` — the ratios (view, lifetime-aggregated per ad×platform)

The **only** place ratios live. Aggregate daily counts to ad-lifetime first (SUM the counts),
**then** divide — `ratio-of-sums`, never `avg-of-ratios`.

```sql
-- warehouse/performance/fct_ad_kpi.sql  (Fabric Warehouse, T-SQL VIEW, F2)
with agg as (
    select ad_id, platform_id,
           sum(impressions) impressions, sum(plays_3s) plays_3s,
           sum(plays_25) plays_25, sum(plays_50) plays_50,
           sum(sum_watch_time_sec) watch_sec, sum(play_count) play_count,
           sum(link_clicks) link_clicks, sum(results) results, sum(spend) spend
    from fact_ad_performance
    group by 1,2
)
select
    ad_id, platform_id,
    plays_3s::double      / nullif(impressions,0) as hook_rate,      -- ≥0.25 target
    plays_25::double      / nullif(plays_3s,0)    as hold_rate_25,   -- denom = prior funnel stage
    plays_50::double      / nullif(plays_3s,0)    as hold_rate_50,
    watch_sec::double     / nullif(play_count,0)  as avg_play_time_sec, -- ≥5s target
    link_clicks::double   / nullif(impressions,0) as ctr_link,       -- ≥0.01 target (NOT ctr_all)
    spend::double         / nullif(results,0)     as cpa,
    results::double       / nullif(link_clicks,0) as cvr             -- 0.01–0.03 target
from agg
```
`nullif(...,0)` guard: a zero denominator yields NULL (not a divide error and not a fake 0).

---

## 4. `int_metric_chunk_alignment` — position-aligned mapping (the hard part)

Maps each funnel metric of each ad to the **one chunk** that owns it. Two mapping kinds:

- **Time-anchored** (`hook`, retention `r25/r50/r75/r100`): the chunk whose
  `[start_sec, end_sec)` **contains** the anchor second. Anchor for `hook` =
  `dim_platform.hook_window_sec`; for `rNN` = `pct × edited_asset.duration_sec`.
- **Role-anchored** (`ctr_link`): the chunk with `chunk_role = 'cta'`.

> **Storage note (deviates from the prose model for arithmetic):** `bridge_ad_chunk` stores
> chunk offsets as **`start_sec` / `end_sec` (DOUBLE, seconds from ad start)**, not wall-clock
> `TIME`. Video offsets are durations, not times-of-day — seconds make the range join clean.

```sql
-- int_metric_chunk_alignment.sql
with anchors as (   -- one row per ad × platform × metric, with the anchor second
    select f.ad_id, f.platform_id, 'hook_rate' as metric_name,
           pl.hook_window_sec as anchor_sec
    from (select distinct ad_id, platform_id from fact_ad_performance) f
    join dim_platform pl using (platform_id)
    union all
    select f.ad_id, f.platform_id, m.metric_name,
           m.pct * a.duration_sec as anchor_sec
    from (select distinct ad_id, platform_id from fact_ad_performance) f
    join map_ad_asset ma using (ad_id)
    join dim_asset a on a.asset_id = ma.asset_id
    cross join (values ('hold_rate_25',0.25),('hold_rate_50',0.50),
                       ('retention_75',0.75),('retention_100',1.00)) m(metric_name,pct)
),
time_aligned as (   -- range join: chunk covering the anchor, with overlap tie-break
    select an.ad_id, an.platform_id, an.metric_name, b.chunk_id, b.chunk_role,
           case
             when an.anchor_sec >= b.start_sec and an.anchor_sec < b.end_sec then 'HIGH'
             else 'MEDIUM'  -- nearest-by-overlap fallback (straddle / boundary)
           end as coverage_confidence,
           row_number() over (
             partition by an.ad_id, an.platform_id, an.metric_name
             order by  -- prefer containing chunk; then greater overlap; then earlier position
               case when an.anchor_sec >= b.start_sec and an.anchor_sec < b.end_sec then 0 else 1 end,
               (least(b.end_sec, an.anchor_sec+0.001) - greatest(b.start_sec, an.anchor_sec-0.001)) desc,
               b.position_in_ad asc
           ) as pick
    from anchors an
    join bridge_ad_chunk b using (ad_id)   -- chunks of THIS edited ad
),
role_aligned as (   -- ctr_link → the cta chunk
    select ad_id, platform_id, 'ctr_link' as metric_name, chunk_id, chunk_role,
           'HIGH' as coverage_confidence,
           row_number() over (partition by ad_id, platform_id
                              order by position_in_ad) as pick
    from bridge_ad_chunk
    where chunk_role = 'cta'
)
select ad_id, platform_id, metric_name, chunk_id, chunk_role, coverage_confidence
from time_aligned where pick = 1
union all
select ad_id, platform_id, metric_name, chunk_id, chunk_role, coverage_confidence
from role_aligned where pick = 1
```

**Why this is also the double-count guard:** each (ad, platform, metric) resolves to **exactly
one** chunk (`pick = 1`). Joining the metric to that one chunk cannot inflate the ad's counts
across its N chunks — the inflation risk (§7 G4) is structurally eliminated for aligned metrics.
If an anchor has no covering chunk at all, `coverage_confidence` is left as `MEDIUM`/nearest;
a true gap (no chunk within tolerance) is tagged `LOW` downstream and **excluded from aggregates**.

---

## 5. `fct_ad_metric_chunk` — analysis-ready base (1 ad × platform × metric)

Joins the metric value (`fct_ad_kpi`) to its owning chunk's features.

```sql
-- fct_ad_metric_chunk.sql
select
    al.ad_id, al.platform_id, al.metric_name,
    case al.metric_name
        when 'hook_rate'    then k.hook_rate
        when 'hold_rate_25' then k.hold_rate_25
        when 'hold_rate_50' then k.hold_rate_50
        when 'ctr_link'     then k.ctr_link
        -- retention_75/100 read from a counts view if needed
    end                                   as metric_value,
    al.chunk_id, al.chunk_role, al.coverage_confidence,
    fc.chunk_theme, fc.sentiment, fc.standalone_score
from int_metric_chunk_alignment al
join fct_ad_kpi  k  using (ad_id, platform_id)
join fact_chunk  fc on fc.chunk_id = al.chunk_id      -- EDITED-ad chunk rows
where al.coverage_confidence in ('HIGH','MEDIUM')                  -- LOW excluded (G-coverage)
```

---

## 6. `mart_chunk_perf_correlation` — the surfaced insight (with honesty baked in)

Grain: **1 platform × 1 metric × 1 feature-dimension × 1 feature-value.**
**Within-platform only** (G2 — platform is in the grain, never aggregated across).

```sql
-- mart_chunk_perf_correlation.sql  (example for the chunk_theme dimension)
with base as (
    select platform_id, metric_name,
           'chunk_theme' as feature_dim, chunk_theme as feature_value,
           ad_id, metric_value
    from fct_ad_metric_chunk
    where metric_value is not null
),
grouped as (
    select platform_id, metric_name, feature_dim, feature_value,
           count(distinct ad_id)          as n_ads,           -- sample size (G3)
           median(metric_value)           as median_metric,
           avg(metric_value)              as mean_metric,
           min(metric_value)              as min_metric,
           max(metric_value)              as max_metric
    from base
    group by 1,2,3,4
)
select *,
    -- within-platform rank of this feature-value for this metric (directional signal)
    rank() over (partition by platform_id, metric_name
                 order by median_metric desc)                 as rank_in_platform,
    -- G3 sample-size regime — GATES surfacing
    case
        when n_ads < 5  then 'BLOCK'         -- anecdotal: not surfaced as insight
        when n_ads < 12 then 'DIRECTIONAL'   -- Spearman/rank, "not significant"
        else                 'SUGGESTIVE'    -- eligible for Mann-Whitney U + Bonferroni
    end                                                        as evidence_regime,
    -- G1 mandatory framing, carried as data so every consumer renders it
    'Among winning ads only — within-platform ranking, correlation not causation'
                                                               as honesty_note
from grouped
```

**Python significance post-step (SUGGESTIVE rows only):** export the relevant `base` rows to
pandas; for each `(platform, metric, feature_dim)` run Mann-Whitney U comparing top-vs-rest
feature groups, apply Bonferroni across the tests in that family, write back `p_value` +
`is_significant`. Rows with `evidence_regime <> 'SUGGESTIVE'` get `p_value = NULL`,
`is_significant = false` — they are never promoted to "significant".

---

## 7. Quality gates (release blockers — @data-quality-steward owns)

GE expectations on the new objects (no dbt schema tests — dbt is dropped, ADR-008):

| Gate | Object | Rule | Severity |
|------|--------|------|----------|
| rates ∈ [0,1] | `fct_ad_kpi` | `hook_rate, hold_rate_*, ctr_link, cvr` between 0 and 1 | CRITICAL |
| non-negative | `fact_ad_performance` | all counts & `spend` ≥ 0 | CRITICAL |
| platform enum | `fact_ad_performance` | `accepted_values(platform_id)` from `dim_platform` | CRITICAL |
| role enum | `bridge_ad_chunk` | `chunk_role ∈ {hook,body,social_proof,cta}` | CRITICAL |
| edited-only FK | `fact_ad_performance` | mapped `asset_id` has `asset_type='EDITED'` | CRITICAL |
| every ad → ≥1 chunk | `fact_ad_performance` | each `ad_id` resolves to ≥1 `bridge_ad_chunk` row | CRITICAL (block promotion) |
| **G4 double-count** | `fct_ad_metric_chunk` | each `(ad_id,platform_id,metric_name)` appears **exactly once** | CRITICAL |
| **G3 surfacing** | `mart_chunk_perf_correlation` | rows with `n_ads < 5` are `BLOCK` and excluded from any surfaced view | CRITICAL |
| **G-coverage** | `int_metric_chunk_alignment` | `LOW` coverage excluded from `fct_ad_metric_chunk` | HIGH |
| mapping present | `map_ad_asset` seed | no `ad_id` in fact without a mapped `asset_id` | CRITICAL |

**G1 (within-winners) and G2 (within-platform)** are structural: `platform_id` is in every
correlation grain (no cross-platform pooling possible without an explicit, reviewed join), and
`honesty_note` ships as a column so no consumer can render an insight without the caveat.

---

## 8. Example analyst queries

**Q (day-one): "Across our winning ads, which Hook-chunk themes correlate with Hook Rate ≥25%?"**
```sql
select platform_id, feature_value as hook_theme,
       n_ads, round(median_metric,3) as median_hook_rate,
       rank_in_platform, evidence_regime, honesty_note
from mart_chunk_perf_correlation
where metric_name = 'hook_rate'
  and feature_dim = 'chunk_theme'
  and evidence_regime <> 'BLOCK'          -- honesty gate G3
order by platform_id, median_hook_rate desc;
```

**Q: "Which CTA-chunk sentiment is associated with the best CTR-Link, per platform?"**
```sql
select platform_id, feature_value as cta_sentiment, n_ads,
       round(median_metric,4) as median_ctr_link, evidence_regime
from mart_chunk_perf_correlation
where metric_name = 'ctr_link' and feature_dim = 'sentiment'
  and evidence_regime <> 'BLOCK'
order by platform_id, median_ctr_link desc;
```

**Q (mine the library for next winners): "Unused raw Hook chunks matching the themes that rank
top-3 for Hook Rate."**
```sql
with winning_themes as (
    select distinct feature_value as theme
    from mart_chunk_perf_correlation
    where metric_name='hook_rate' and feature_dim='chunk_theme'
      and evidence_regime <> 'BLOCK' and rank_in_platform <= 3
)
select fc.chunk_id, fc.asset_id, fc.chunk_theme, fc.standalone_score, fc.transcript_segment
from fact_chunk fc
join dim_asset a on a.asset_id = fc.asset_id and a.asset_type = 'RAW'
where fc.chunk_theme in (select theme from winning_themes)
  and fc.standalone_score >= 4
  and fc.chunk_id not in (select chunk_id from bridge_ad_chunk)   -- never used in an ad yet
order by fc.standalone_score desc;
```

---

## 9. Build order (suggested)

1. `dim_platform` seed + `map_ad_asset` seed.
2. `bronze_ad_performance_raw` ingest (manual CSV → OneLake) + `stg_*` + `int_ad_perf_unioned`.
3. `fact_ad_performance` + its CRITICAL gates (esp. edited-only FK, every-ad→chunk).
4. `bridge_ad_chunk` populate (requires edited ads already chunked through the v1 pipeline).
5. `fct_ad_kpi`.
6. `int_metric_chunk_alignment` → `fct_ad_metric_chunk` (with G4 + coverage gates).
7. `mart_chunk_perf_correlation` + the Python significance post-step.
8. Wire the three example queries as the demo.

**Out of this spec (still v2 per veto):** predictive scoring, variant factory, RAG, vector DB,
causal swap-one-chunk experiment, cross-platform pooled magnitudes, connectorized ingest.
