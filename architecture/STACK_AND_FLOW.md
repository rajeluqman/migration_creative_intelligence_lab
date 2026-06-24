# STACK & END-TO-END FLOW — Creative Intelligence Pipeline (Microsoft Fabric build)

**Status:** Consolidated view (v1 + v1.5) · derived from the ratified `DATA_MODEL.md`,
`DATA_MODEL_v1.5_PERFORMANCE.md`, the round-1/round-2 debates (historical, pre-Fabric), and
**ADR-008** (physical stack migration to Microsoft Fabric, 2026-06-24).
**Purpose:** one place to see every tool and the full flow, as built in this repo
(`migration_creative_intelligence_lab`). The sibling repo `creative_intelligence_lab` runs the
original S3 + DuckDB + Snowflake stack this document used to describe — see ADR-008 for the
supersession record and ADR-001/005/007 for the historical reasoning.

---

## 1. The tool stack by layer

| Stage | Tool | Role | Status |
|-------|------|------|--------|
| **Source** | Google Drive API + Python | pull client's messy video folder | v1 |
| **Landing** | **OneLake Lakehouse `Files/`** (write-once) + `hashlib` SHA-256 | content-addressed video bytes `Files/landing/<client_id>/video/<asset_id>.<ext>` | v1 |
| **Extraction** | **Gemini API (Flash-first)** + `responseSchema` (structured output) | video → semantic-chunk JSON, verbatim | v1 |
| **Prompt mgmt** | versioned prompt registry (`prompt_version`/`prompt_hash`/`model_version`) | reproducibility + drift attribution | enhancement |
| **Bronze** | **OneLake Lakehouse `Files/`** (raw JSON, append-only) | immutable raw Gemini JSON + raw Meta/TikTok CSV | v1 / v1.5 |
| **Silver** | **PySpark notebook** (Fabric Lakehouse) → Delta tables + **Great Expectations** | flatten/unnest → chunk rows; schema + range gates | v1 |
| **Gold** | **Fabric Warehouse, T-SQL `VIEW`s** over a OneLake shortcut into the Lakehouse | graph + feature store + perf marts | v1 / v1.5 |

> **Storage = OneLake (ADR-008, owner directive 2026-06-24, supersedes ADR-005's S3).** All
> layers persist to one Lakehouse: `Files/landing`, `Files/bronze` (verbatim, append-only) and
> Delta Tables for Silver. Gold is **never** a second copy of Silver — it is T-SQL **views** in
> the Warehouse reading the Lakehouse via a OneLake shortcut (Binding Condition 1, ADR-008).
> Tradeoff (accepted, same class as ADR-005's): no longer offline-$0 standalone — a fresh
> workspace needs a Fabric capacity (trial or paid).
| **Stats** | Python (pandas + scipy), run in a Fabric notebook | Mann-Whitney U + Bonferroni (SUGGESTIVE tier only) | v1.5 |
| **Serving / demo** | **Power BI Direct Lake** (reads Delta directly, no import/duplication) + **Fabric Copilot / Azure OpenAI** (QA/summarization veneer, not source of truth) | semantic search + correlation queries (ADR-008) | v1 / v1.5 |
| **Orchestration** | **Fabric Data Factory pipeline** (per-asset activities, retry/backoff, skip-existing) | async, rate-limit-aware run | v1 |
| **Quality** | Great Expectations (run in notebooks) + lineage/boundary contracts | per-layer gates incl. honesty gates | v1 / v1.5 |
| **CI/CD** | GitHub Actions (`py_compile` + `ruff` + lineage/boundary contracts + GE-JSON) | static gates, PR→main | v1 |
| **Telemetry** | `fact_extraction_run` (tokens/cost/latency/retries/confidence) | FinOps + ops dashboard | enhancement |
| **Render (v2)** | FFmpeg | stitch chunk sequence → candidate mp4 | v2 |

**Rejected (do not add):** Databricks / Glue / MWAA / Fivetran-Airbyte / Pinecone-Weaviate-
Qdrant-Chroma-Milvus-FAISS / dedicated vector DB. Reason: KB–MB structured scale; the only real
cost/latency is the Gemini API call (unchanged from the original rationale — see ADR-001,
historical). **Spark is no longer rejected** — Fabric's PySpark notebooks are now the Bronze/
Silver compute engine (ADR-008); what stays rejected is a *standalone* Databricks/Glue cluster
outside the Fabric capacity.
**Serving veneer (ADR-008):** Power BI Direct Lake + Copilot/Azure OpenAI over Gold Warehouse
views (NOT as transform engine — PySpark/T-SQL stay that; NOT as a source of truth — the
Lakehouse Delta tables stay that).

---

## 2. End-to-end flow — the whole picture

```
                          ┌──────────────────────────────────────────────────────────┐
                          │  CLIENT delivers a Google Drive folder (messy compilation │
                          │  of RAW creative video + sometimes EDITED winning ads)    │
                          └───────────────────────────────┬──────────────────────────┘
                                                          │ Google Drive API + Python (Fabric notebook)
                                                          ▼
   PATH A — VIDEO (raw AND edited)            ┌──────────────────────────────────────────┐
   ══════════════════════════════            │  LANDING  (OneLake Lakehouse Files/)      │
                                             │  Files/landing/<client_id>/video/<id>.ext │  asset_id = SHA-256(client_id:content_sha256)
                                             └───────────────┬──────────────────────────┘
                                                             │  skip-existing on hash (idempotent, $-firewall)
                                                             ▼
                                             ┌──────────────────────────────┐
                                             │  Gemini API (Flash)           │  structured output (responseSchema)
                                             │  prompt_version + model_version│  → semantic-chunk JSON, verbatim
                                             └───────────────┬──────────────┘
                                                             ▼
                                ┌───────────────────────────────────────────────────────┐
                                │  BRONZE  Files/bronze/asset_raw  (Lakehouse, append)   │  ← re-parse, NEVER re-pay
                                └───────────────────────────┬───────────────────────────┘
                                                            │ PySpark notebook + Great Expectations (schema gate)
                                                            ▼
                                ┌───────────────────────────────────────────────────────┐
                                │  SILVER  silver_chunk (Delta, 1 row = 1 semantic chunk)│  ← chunking lives HERE
                                │  filler removed · ts normalized · GE range gate        │     standalone_score 1..5
                                └───────────────────────────┬───────────────────────────┘
                                                            │ OneLake shortcut → Fabric Warehouse T-SQL views
                                                            ▼
                ┌───────────────────────────────────────────────────────────────────────────┐
                │  GOLD (graph + feature store, T-SQL VIEWs)                                 │
                │   dim_asset (RAW+EDITED, self-ref parent) · fact_chunk (grain=chunk)        │
                │   bridge_asset_lineage · bridge_chunk_compatibility · keyword/theme bridges │
                └───────────────────────────────────────────────┬───────────────────────────┘
                                                                 │
                                                                 │   ┌──────────────────────────────────────┐
                                                                 │   │  EDITED ad ALSO ingested via Path B  │
   PATH B — PERFORMANCE (Meta / TikTok)                          │   │  for its funnel metrics              │
   ════════════════════════════════════                         │   └──────────────────────────────────────┘
   manual CSV export ──► Lakehouse Files/ ──► bronze_ad_performance_raw
        │  (immutable)                          │  PySpark notebook: stg_meta + stg_tiktok → union
        ▼                                       ▼
   dim_platform                       fact_ad_performance (grain: ad × platform × DAY, raw counts)
   (Meta 3s/TikTok 6s)                          │
                                                 │   bridge_ad_chunk  (editor's asserted cut: ad → chunk + role + position)
                                                 ▼            │
                                       int_metric_chunk_alignment  ◄────────────┘   (time-range join: Hook Rate ↔ hook chunk,
                                                 │                                       CTR-Link ↔ cta chunk; one chunk per metric)
                                                 ▼
                                       fct_ad_kpi (ratios, VIEW) ──► fct_ad_metric_chunk ──► mart_chunk_perf_correlation
                                                                                  │  (within-platform, within-winners,
                                                                                  │   sample-size regime, honesty_note)
                                                                                  ▼
                ┌───────────────────────────────────────────────────────────────────────────┐
                │  SERVING / DEMO  (Power BI Direct Lake over Gold Warehouse views;          │
                │                   Fabric Copilot / Azure OpenAI QA veneer)                 │
                │   • "find clips: theme=X, sentiment=Y, standalone_score>=4"   (v1 north-star)│
                │   • "which Hook-chunk themes correlate with Hook Rate >=25%?" (v1.5)         │
                │   • "mine unused RAW chunks matching winning themes"          (v1.5)         │
                └───────────────────────────────────────────────────────────────────────────┘

   ORCHESTRATION (Fabric Data Factory): per-asset pipeline activities, retry/backoff, skip-existing
   QUALITY (GE + lineage/boundary contracts): per-layer gates + v1.5 honesty gates (within-winners / within-platform / sample ladder)
   CI/CD (GitHub Actions): py_compile + ruff + lineage/boundary contracts + GE-JSON, PR→main
```

---

## 3. The two ingestion paths (why there are two)

- **Path A (video):** every video — RAW *and* EDITED — goes through Drive→OneLake→Gemini→
  Bronze→Silver→Gold. This produces `fact_chunk` rows. The EDITED ad gets its **own** chunk
  rows in its **own** timeline (needed for the position-aligned Hook-Rate mapping).
- **Path B (performance):** only EDITED ads that actually ran have Meta/TikTok metrics. These
  arrive as **manual CSV export → OneLake Lakehouse `Files/` → `bronze_ad_performance_raw`**
  and become `fact_ad_performance`. They are stitched to Path A through `bridge_ad_chunk`
  (which chunks are in the cut) — never by propagating metrics backward onto RAW (permanent
  veto, unchanged from the original ruling).

**Join key reality:** `ad_id` (platform creative id) → `asset_id` (edited asset) is a manual
seed (`map_ad_asset.csv`) at 3–15 ads, enforced by a referential-integrity check (the lineage
contract's R5-equivalent for this join, or a GE `relationships`-style expectation — implemented
when the Gold T-SQL views land in F2).

---

## 4. Stage → resume-stack mapping (portfolio fit)

| This project uses | Resume line it demonstrates |
|-------------------|------------------------------|
| OneLake + medallion + PySpark notebooks + Fabric Warehouse (T-SQL) + GE + GitHub Actions | Microsoft Fabric (Lakehouse/Warehouse), medallion architecture, ELT, Great Expectations, CI/CD |
| Gemini API structured output + prompt versioning | LLM-in-production / Gemini API (the *distinct* differentiator) |
| Fabric Data Factory pipeline (retry/backoff, skip-existing) | Pipeline orchestration in the Microsoft ecosystem (advanced patterns, not toy pipelines) |
| star-vs-graph decision + bridge tables + SCD | Dimensional modelling, data architecture judgement |
| within-winners / sample-size honesty gates | Data quality, statistical literacy (rare in DE portfolios) |
| Power BI Direct Lake + Fabric Copilot / Azure OpenAI veneer | AI-enabled analytics in the Microsoft ecosystem (JD-targeted) |

**Distinctiveness vs the 4 existing pipelines:** this is the only one that is *LLM-extraction +
graph/feature-store + non-deterministic-output testing*, now also the only one built **totally
on Microsoft Fabric** end to end. Not another batch star schema.
