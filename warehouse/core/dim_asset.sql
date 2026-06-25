-- Gold T-SQL VIEW (Fabric Warehouse over OneLake shortcut). Ported from
-- models/marts/core/dim_asset.sql (dbt/DuckDB -> T-SQL, ADR-008). Node table, RAW + EDITED.
-- asset_type + parent_asset_id come from the ingestion manifest (Delta seed), NOT a literal.
-- The manifest is the system of record for asset identity. ADR-002/003/006.
CREATE VIEW dim_asset AS
SELECT
    asset_id,                 -- SHA-256(client_id ':' content_sha256) — tenant-scoped (ADR-006)
    client_id,                -- FK -> dim_client; tenancy boundary, NOT NULL
    content_sha256,           -- raw byte hash; non-key, intra-client near-dup detection
    parent_asset_id,          -- RAW->EDITED discovery lineage; NULL for RAW
    asset_name,
    asset_type,               -- RAW | EDITED
    duration_sec,
    source_uri,               -- abfss OneLake URI (ADR-008)
    ingested_at,              -- provenance, immutable (write-once at landing)
    CAST(NULL AS VARCHAR(40)) AS dq_flag,
    SYSUTCDATETIME()          AS load_ts  -- audit, volatile (view refresh time; no dbt build — ADR-008)
FROM asset_manifest;
