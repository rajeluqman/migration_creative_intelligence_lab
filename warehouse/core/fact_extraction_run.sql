-- Gold T-SQL VIEW. Ported from models/marts/core/fact_extraction_run.sql (ADR-008).
-- Operational telemetry (enhancement): tokens/cost/latency/confidence.
-- STUB (WHERE 1=0) in the sibling repo too — populated from the extract notebook's run log
-- (Files/bronze/<client>/extraction_run_log/*.json) when wired; Gold change needs DA sign-off.
CREATE VIEW fact_extraction_run AS
SELECT
    CAST(NULL AS VARCHAR(36))    AS run_id,
    asset_id,
    CAST(NULL AS VARCHAR(50))    AS model_version,
    CAST(NULL AS VARCHAR(20))    AS prompt_version,
    CAST(NULL AS BIGINT)         AS tokens_in,
    CAST(NULL AS BIGINT)         AS tokens_out,
    CAST(NULL AS DECIMAL(10,4))  AS api_cost,
    CAST(NULL AS DECIMAL(10,2))  AS processing_time_sec,
    CAST(NULL AS INT)            AS retry_count,
    CAST(NULL AS DECIMAL(5,4))   AS extraction_confidence
FROM silver_chunk
WHERE 1 = 0;   -- stub: populate from the extraction run log
