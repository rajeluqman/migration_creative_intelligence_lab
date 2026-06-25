-- Gold T-SQL VIEW. Ported from models/marts/performance/fct_ad_kpi.sql (ADR-008).
-- Ratios derived here ONLY (ratio-of-sums: SUM the daily counts to ad-lifetime, THEN divide).
-- SPEC §3. DuckDB `::double` -> T-SQL CAST(... AS FLOAT); nullif guard preserved verbatim.
CREATE VIEW fct_ad_kpi AS
WITH agg AS (
    SELECT ad_id, platform_id,
           SUM(impressions) AS impressions, SUM(plays_3s) AS plays_3s, SUM(plays_25) AS plays_25,
           SUM(sum_watch_time_sec) AS watch_sec, SUM(play_count) AS play_count,
           SUM(link_clicks) AS link_clicks, SUM(results) AS results, SUM(spend) AS spend
    FROM fact_ad_performance
    GROUP BY ad_id, platform_id
)
SELECT ad_id, platform_id,
    CAST(plays_3s AS FLOAT)    / NULLIF(impressions, 0) AS hook_rate,
    CAST(plays_25 AS FLOAT)    / NULLIF(plays_3s, 0)    AS hold_rate_25,
    CAST(watch_sec AS FLOAT)   / NULLIF(play_count, 0)  AS avg_play_time_sec,
    CAST(link_clicks AS FLOAT) / NULLIF(impressions, 0) AS ctr_link,
    CAST(spend AS FLOAT)       / NULLIF(results, 0)     AS cpa,
    CAST(results AS FLOAT)     / NULLIF(link_clicks, 0) AS cvr
FROM agg;
