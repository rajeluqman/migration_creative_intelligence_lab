-- Gold T-SQL VIEW. Ported from models/intermediate/int_metric_chunk_alignment.sql (ADR-008).
-- Position-aligned mapping: each funnel metric -> the ONE owning chunk. SPEC §4.
-- Time-anchored metrics (hook/hold) via range join on the EDITED ad's timeline; role-anchored
-- metric (ctr_link) via chunk_role='cta'. Deterministic tie-break + coverage_confidence.
-- Exactly one chunk per (ad,platform,metric) = the double-count guard (preserved verbatim).
-- DuckDB->T-SQL: `::double`->CAST AS FLOAT; `using()`->ON; `values(...) m(...)`->(VALUES...) AS m(...);
-- least/greatest are native in Fabric Warehouse T-SQL.
CREATE VIEW int_metric_chunk_alignment AS
WITH ad_platform AS (
    SELECT DISTINCT ad_id, platform_id FROM fact_ad_performance
),
anchors AS (
    -- hook anchor = platform hook window (Meta 3s / TikTok 6s, from dim_platform)
    SELECT ap.ad_id, ap.platform_id, 'hook_rate' AS metric_name,
           CAST(pl.hook_window_sec AS FLOAT) AS anchor_sec
    FROM ad_platform ap
    JOIN dim_platform pl ON pl.platform_id = ap.platform_id
    UNION ALL
    -- hold anchor = pct * edited-asset duration
    SELECT ap.ad_id, ap.platform_id, m.metric_name, m.pct * a.duration_sec AS anchor_sec
    FROM ad_platform ap
    JOIN map_ad_asset ma ON ma.ad_id = ap.ad_id
    JOIN dim_asset a ON a.asset_id = ma.asset_id
    CROSS JOIN (VALUES ('hold_rate_25', 0.25)) AS m(metric_name, pct)
),
time_aligned AS (
    SELECT an.ad_id, an.platform_id, an.metric_name, b.chunk_id, b.chunk_role,
           CASE WHEN an.anchor_sec >= b.start_sec AND an.anchor_sec < b.end_sec
                THEN 'HIGH' ELSE 'MEDIUM' END AS coverage_confidence,
           ROW_NUMBER() OVER (
             PARTITION BY an.ad_id, an.platform_id, an.metric_name
             ORDER BY CASE WHEN an.anchor_sec >= b.start_sec AND an.anchor_sec < b.end_sec THEN 0 ELSE 1 END,
                      (LEAST(b.end_sec, an.anchor_sec) - GREATEST(b.start_sec, an.anchor_sec)) DESC,
                      b.position_in_ad ASC
           ) AS pick
    FROM anchors an
    JOIN bridge_ad_chunk b ON b.ad_id = an.ad_id
),
role_aligned AS (
    SELECT ap.ad_id, ap.platform_id, 'ctr_link' AS metric_name, b.chunk_id, b.chunk_role,
           'HIGH' AS coverage_confidence,
           ROW_NUMBER() OVER (PARTITION BY ap.ad_id, ap.platform_id ORDER BY b.position_in_ad) AS pick
    FROM ad_platform ap
    JOIN bridge_ad_chunk b ON b.ad_id = ap.ad_id AND b.chunk_role = 'cta'
)
SELECT ad_id, platform_id, metric_name, chunk_id, chunk_role, coverage_confidence
FROM time_aligned WHERE pick = 1
UNION ALL
SELECT ad_id, platform_id, metric_name, chunk_id, chunk_role, coverage_confidence
FROM role_aligned WHERE pick = 1;
