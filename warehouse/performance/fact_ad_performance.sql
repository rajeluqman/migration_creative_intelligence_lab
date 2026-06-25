-- Gold T-SQL VIEW. Ported from models/marts/performance/fact_ad_performance.sql (ADR-008).
-- GRAIN: 1 edited-ad x 1 platform x 1 DAY. Raw counts only. ADR-004 / SPEC §2.
-- Reads the Silver Delta table int_ad_perf_unioned + the seed Delta tables.
CREATE VIEW fact_ad_performance AS
SELECT
    u.ad_id,
    p.platform_id,
    u.perf_date,
    m.asset_id,
    u.impressions, u.plays_3s, u.plays_25, u.plays_50, u.plays_75, u.plays_100,
    u.sum_watch_time_sec, u.play_count, u.link_clicks, u.results, u.spend,
    SYSUTCDATETIME() AS load_ts
FROM int_ad_perf_unioned u
JOIN dim_platform p ON p.platform_name = u.platform_name
JOIN map_ad_asset m ON m.ad_id = u.ad_id;
