-- Gold T-SQL VIEW. Ported from models/marts/core/bridge_asset_lineage.sql (ADR-008).
-- RAW -> EDITED edge. Navigation only; NEVER carries metrics (ADR-002/004).
-- STUB (WHERE 1=0) in the sibling repo too — population mechanism unspecified (STTM open item).
CREATE VIEW bridge_asset_lineage AS
SELECT asset_id AS parent_asset_id, asset_id AS child_asset_id
FROM dim_asset
WHERE 1 = 0;   -- stub: populate from edit lineage when a ratified mechanism exists
