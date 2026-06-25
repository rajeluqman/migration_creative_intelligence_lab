-- Gold T-SQL VIEW. Ported from models/marts/core/bridge_chunk_compatibility.sql (ADR-008).
-- Mix-and-match adjacency. The DuckDB `unnest(next_compatible_themes)` is done upstream in the
-- Silver notebook (Spark explode -> silver_chunk_compatibility) because Fabric Warehouse does
-- not read Delta array columns cleanly; this view is the plain passthrough.
CREATE VIEW bridge_chunk_compatibility AS
SELECT
    chunk_id,
    compatible_theme,
    CAST(NULL AS DECIMAL(5,4)) AS theme_match_score
FROM silver_chunk_compatibility;
