-- Gold T-SQL VIEW. Ported from models/marts/core/fact_chunk.sql (ADR-008).
-- Feature row. GRAIN = one semantic chunk. ADR-002. Reads the Silver Delta table.
CREATE VIEW fact_chunk AS
SELECT
    chunk_id, asset_id, chunk_sequence,
    start_sec, end_sec, transcript_segment,
    chunk_theme, sentiment, standalone_score
FROM silver_chunk;
