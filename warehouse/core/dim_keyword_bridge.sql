-- Gold T-SQL VIEW. Ported from models/marts/core/dim_keyword_bridge.sql (ADR-008).
-- The DuckDB `unnest(keywords)` is done upstream in the Silver notebook (Spark explode ->
-- silver_chunk_keyword), same reason as bridge_chunk_compatibility; this view is the passthrough.
CREATE VIEW dim_keyword_bridge AS
SELECT chunk_id, keyword
FROM silver_chunk_keyword;
