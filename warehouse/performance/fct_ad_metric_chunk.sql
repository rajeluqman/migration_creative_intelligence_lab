-- Gold T-SQL VIEW. Ported from models/marts/performance/fct_ad_metric_chunk.sql (ADR-008).
-- 1 ad x platform x metric -> metric value + mapped chunk features. SPEC §5.
-- DuckDB `using()` -> T-SQL ON.
CREATE VIEW fct_ad_metric_chunk AS
SELECT
    al.ad_id, al.platform_id, al.metric_name,
    CASE al.metric_name
        WHEN 'hook_rate'    THEN k.hook_rate
        WHEN 'hold_rate_25' THEN k.hold_rate_25
        WHEN 'ctr_link'     THEN k.ctr_link
    END AS metric_value,
    al.chunk_id, al.chunk_role, al.coverage_confidence,
    fc.chunk_theme, fc.sentiment, fc.standalone_score
FROM int_metric_chunk_alignment al
JOIN fct_ad_kpi k ON k.ad_id = al.ad_id AND k.platform_id = al.platform_id
JOIN fact_chunk fc ON fc.chunk_id = al.chunk_id
WHERE al.coverage_confidence IN ('HIGH', 'MEDIUM');
