# Great Expectations suites (per layer)
Bootstrap with `great_expectations init` after `setup.sh`. Suites to build:
- bronze_asset_raw: valid JSON, chunks length >= 1 (catches schema-valid-but-empty LLM output)
- silver_chunk: standalone_score in [1,5], sentiment enum, non-empty chunk_theme
- fact_ad_performance: counts/spend >= 0, platform enum, EDITED-only FK, every ad -> >=1 chunk
- mart_chunk_perf_correlation: n_ads<5 => BLOCK (not surfaced), honesty_note not null
See architecture/SPEC_v1.5_performance_marts.md §7 for the full gate list.
