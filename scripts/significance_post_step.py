"""SUGGESTIVE-tier significance: Fabric Warehouse -> pandas -> scipy Mann-Whitney U + Bonferroni."""
# TODO (SPEC_v1.5_performance_marts.md §6): read mart_chunk_perf_correlation rows where
# evidence_regime='SUGGESTIVE' (query the Gold Warehouse view, not DuckDB — ADR-008);
# within-platform groups only; write back p_value + is_significant. Stub in the sibling repo too.
