# Troubleshooting Library — Creative Intelligence Pipeline (INDEX)

> Failure-path twin of the optimization library, mirroring the pharma gym's troubleshooting
> structure. One card per failure mode, per phase. Symptom presented FAR from root → trace
> backward (observability-first). Content is English.

> ## 🚧 STATUS: STUB — BACKLOG-gated (single-doc form)
> **This INDEX file *is* the entire Tier-1 troubleshooting artifact for now.** Per the
> @senior-data-engineer + @scope-guardian co-sign (2026-06-22), it is **not** split into
> per-phase files yet — that contradicts BACKLOG's "shrink to a single doc" guidance.
> - **Gate:** see `BACKLOG.md` → "Gym apparatus port" **Tier 1**. A real incident card is
>   authored only AFTER (1) v1 ships, AND (2) ≥1 real incident is hit during the build.
> - **Owner:** @senior-data-engineer (no dedicated agent — the incubator/drill-loop and gym
>   agents are **Tier 2/3 REJECTED**, see the "Gym drill-loop" section at the bottom).
> - **Authoring rule:** every ✅ HARDENED card cites a real `file:line` from the actual fix.
>   **No fabricated incidents, no invented citations.** The one seed below is explicitly
>   🟡 APPLICABLE (undrilled), not a claim that an incident happened.
> - **Split rule (lazy):** promote cards into their own `0N_<phase>.md` file only when that one
>   phase earns **≥3–4 real cards** — split on volume, never preemptively on taxonomy.

## Binding translation note (read first)
**ADR-008 (2026-06-24):** this repo runs Fabric-managed PySpark notebooks + a Fabric
Warehouse, not the sibling repo's DuckDB/dbt/local-Airflow stack. Generic on-prem/IaaS Spark
troubleshooting advice ("check the Spark UI / executor logs / shuffle spill") still mostly
applies — Spark IS the engine now — but translate the *cluster-ops* assumptions (you don't
own the cluster; it's a managed Fabric capacity) and drop anything dbt-specific (dbt is
dropped):

| Generic (self-managed Spark cluster) | This project (Fabric-managed PySpark + Warehouse) |
|---------------------------------------|----------------------------------------------------|
| Spark UI / stage timeline | Fabric notebook's built-in Spark UI (monitoring hub) — same data, managed not self-hosted |
| Executor OOM / shuffle spill | Fabric notebook session size / Spark pool config (no manual `SET memory_limit`; resize the session) |
| Cluster/driver logs | Fabric notebook run history + Data Factory pipeline activity run log |
| S3A connector errors | OneLake `abfss://` shortcut/connector errors (no S3A — no S3 in this stack, ADR-008) |
| Stuck stage | Data Factory pipeline activity retry/backoff exhaustion / `gemini_api` rate-limit stall |
| dbt run timing | Fabric Warehouse query history (Gold is T-SQL views, not a dbt run) |

## Card format (copy this)
```
### <ID> — <symptom, far from root>
- **Phase:** triage | ingestion | extraction | transformation | load | validation | orchestration | cicd | postmortem
- **Status:** ✅ HARDENED (fix cited) | 🟡 APPLICABLE (real, undrilled)
- **Symptom (business/observability):** what a stakeholder/monitor sees first.
- **Backward trace:** observable → … → root.
- **Root cause:** the actual defect.
- **Fix / guard:** `path/to/file:LN` (✅ only).
- **LLM-specific twist:** what makes this harder than deterministic ETL (if any).
- **Junior mistake:** the wrong first move.
```

## Phase map (planned files — none split out yet; see split rule above)
All phases are **⬜ gated · 0 cards** until the BACKLOG Tier-1 gate trips. The first card for
any phase is authored inline under "Seed card" below, in this single doc, until a phase earns
≥3–4 real cards.

| File | Phase | Status | Cards | Example failure modes for this project |
|------|-------|--------|-------|----------------------------------------|
| `01_triage.md` | Triage | ⬜ gated | 0 | "search returns nothing" / "correlation mart empty" — where to look first |
| `03_ingestion.md` | Drive→OneLake | ⬜ gated | 0 | 0-byte download, truncated video, hash collision, Drive rate limit |
| `04_extraction.md` | Gemini | ⬜ gated | 0 | malformed JSON, truncated response, schema drift across model_version, hallucinated theme |
| `05_transformation.md` | Silver/Gold | ⬜ gated | 0 | array-explode fan-out blow-up, FK orphan chunk, double-count across bridge_ad_chunk |
| `06_validation.md` | DQ | ⬜ gated | 0 | constraint gate flapping on LLM variance, golden-set drift, sample-gate blocking everything |
| `07_orchestration.md` | Fabric Data Factory | ⬜ gated | 0 | activity retry exhaustion, 429 storm, skip-existing not firing |
| `08_load_perf.md` | Perf ingest | ⬜ gated | 0 | ad_id→asset_id unmapped, EDITED-only FK violation, restated metrics double-loaded |
| `09_postmortem.md` | Postmortem | ⬜ gated | 0 | template + sealed-rubric pattern |

## Example card (seed)
### TS-EXT-01 — "Silver chunk count dropped to zero for a batch, but no error logged"
- **Phase:** extraction
- **Status:** 🟡 APPLICABLE (undrilled)
- **Symptom:** overnight run "succeeded" (exit 0) but `silver_chunk` gained 0 rows for 12 videos.
- **Backward trace:** empty Silver → Bronze rows present but `chunks` array empty →
  Gemini returned valid JSON with `{"chunks": []}` → prompt/model returned no segments (or a
  content-safety block) → no schema violation, so nothing quarantined.
- **Root cause:** valid-but-empty LLM output passes the schema gate; only a *non-empty* business
  rule catches it.
- **Fix / guard:** add a GE expectation `chunks length >= 1` at the Bronze→Silver boundary
  (`great_expectations/` suite) → quarantine empties for human review.
- **LLM-specific twist:** "schema-valid yet semantically empty" — the unreliable-narration risk;
  deterministic ETL never produces this.
- **Junior mistake:** trusting exit 0 + valid JSON as "data is fine."

## Gym drill-loop (incubator) — REJECTED scope, do NOT build
> Tier 2/3 of the Gym apparatus port (`BACKLOG.md` → "Gym apparatus port") is **REJECTED**:
> the incubator + incident-drill loop and any gym agents (e.g. bottleneck-saboteur) are NOT
> in scope, v1 or v2. Retained here only to record the boundary, not as an option.
>
> For provenance only (NOT a build target here): the pharma gym's `INCUBATOR.md` drill pattern
> injected one failure per card in an incubator (fake creds, throwaway bucket, per-drill branch),
> traced backward, wrote a post-mortem, and diffed vs a sealed rubric. This project deliberately
> does not adopt it — see the BACKLOG ruling for why (more reviewers than builders on a single-dev
> build).
