-- Gold T-SQL VIEW. Ported from models/marts/performance/bridge_ad_chunk.sql (ADR-008).
-- Editor's asserted cut: ad -> chunk + role + position (the v1.5 unlock). SPEC §2.
-- The EDL (edit_decision_list seed, loaded as Delta) is the editor's RECORDED assertion of what
-- is physically in the cut — a fact, not an inference (ADR-004). asset_id resolves from the
-- chunk's own fact_chunk row. GRAIN guarded by GE (great_expectations/expectations/bridge_ad_chunk.json).
CREATE VIEW bridge_ad_chunk AS
SELECT
    edl.ad_id,
    edl.chunk_id,
    fc.asset_id,
    edl.chunk_role,
    edl.position_in_ad,
    edl.start_sec,
    edl.end_sec
FROM edit_decision_list edl
JOIN fact_chunk fc ON fc.chunk_id = edl.chunk_id;
