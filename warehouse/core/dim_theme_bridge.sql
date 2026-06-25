-- Gold T-SQL VIEW. Ported from models/marts/core/dim_theme_bridge.sql (ADR-008).
-- One row per chunk per theme (single theme per chunk here — no array, plain select).
CREATE VIEW dim_theme_bridge AS
SELECT chunk_id, chunk_theme AS theme
FROM silver_chunk;
