# Build quickstart
1. `bash setup.sh`              # scaffold + venv + deps (no dbt; Fabric notebooks run in-workspace)
2. `cp .env.example .env`       # fill GEMINI_API_KEY, FABRIC_WORKSPACE (creative-intel-ws), FABRIC_LAKEHOUSE (creative_intel_lh)
3. Open the Fabric workspace, attach the Lakehouse — no local `profiles.yml` equivalent;
   Bronze/Silver notebooks and Gold Warehouse views run inside the Fabric capacity
4. Implement the stubs marked `TODO` from architecture/SPEC_v1.5_performance_marts.md in
   `notebooks/` (Bronze/Silver, F1) and `warehouse/` (Gold T-SQL views, F2)
5. Run notebooks in pipeline order (see STACK_AND_FLOW.md §2) — v1 first
6. Run the Gold Warehouse performance views + `python scripts/significance_post_step.py`   # v1.5
Architecture of record: architecture/  (DATA_MODEL*, SPEC*, ADR-00*, STACK_AND_FLOW, ERD*, DBT_DAG)
