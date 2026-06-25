-- Ad-hoc T-SQL demo queries against the Gold Warehouse views (ADR-008; not a Warehouse view,
-- not built by any framework — there is no dbt-equivalent in this stack). Ported from the
-- sibling repo's analyses/demo_queries.sql (DuckDB -> T-SQL).
-- The three demo queries (full text: SPEC_v1_search.md §2/§3, SPEC_v1.5_performance_marts.md §8):
--   1) v1 north-star search (theme + sentiment + standalone_score + LIKE on transcript)
--   2) Hook-theme x Hook Rate correlation (within-platform, within-winners)
--   3) mine unused RAW chunks matching winning themes
-- Stub pointer in the sibling repo too; write the real T-SQL when Gold has real rows (F-parity).
SELECT 'see SPEC_v1_search.md §2/§3 + SPEC_v1.5_performance_marts.md §8' AS todo;
