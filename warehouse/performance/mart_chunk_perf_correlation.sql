-- Gold T-SQL VIEW. Ported from models/marts/performance/mart_chunk_perf_correlation.sql (ADR-008).
-- Surfaced insight. Within-platform, within-winners, sample-gated. SPEC §6.
-- KEY TRANSLATION: DuckDB `median(metric_value)` aggregate has no T-SQL equivalent — T-SQL's
-- PERCENTILE_CONT is window-only, so the median is computed as a window over the feature
-- partition, then collapsed to one row per group with MAX (median is constant per partition).
-- The n<5 BLOCK / 5-11 DIRECTIONAL / >=12 SUGGESTIVE regime + honesty_note are preserved verbatim.
CREATE VIEW mart_chunk_perf_correlation AS
WITH base AS (
    SELECT platform_id, metric_name,
           CAST('chunk_theme' AS VARCHAR(20)) AS feature_dim,
           chunk_theme AS feature_value, ad_id, metric_value
    FROM fct_ad_metric_chunk
    WHERE metric_value IS NOT NULL
),
with_median AS (
    SELECT platform_id, metric_name, feature_dim, feature_value, ad_id,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY metric_value)
               OVER (PARTITION BY platform_id, metric_name, feature_dim, feature_value) AS median_metric
    FROM base
),
grouped AS (
    SELECT platform_id, metric_name, feature_dim, feature_value,
           COUNT(DISTINCT ad_id) AS n_ads,
           MAX(median_metric)    AS median_metric  -- constant per partition; MAX collapses to one row
    FROM with_median
    GROUP BY platform_id, metric_name, feature_dim, feature_value
)
SELECT
    platform_id, metric_name, feature_dim, feature_value, n_ads, median_metric,
    RANK() OVER (PARTITION BY platform_id, metric_name ORDER BY median_metric DESC) AS rank_in_platform,
    CASE WHEN n_ads < 5 THEN 'BLOCK' WHEN n_ads < 12 THEN 'DIRECTIONAL' ELSE 'SUGGESTIVE' END AS evidence_regime,
    'Among winning ads only - within-platform ranking, correlation not causation' AS honesty_note
FROM grouped;
