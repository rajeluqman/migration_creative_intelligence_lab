# BUILD SPEC — v1 Search & Mix-and-Match Demo (ships FIRST)

**Status:** Draft for build · **Owner:** @senior-data-engineer · **Authority:** `DATA_MODEL.md`
(ratified v1 AoR), ADR-002/003. Closes gap-check **BLOCKER-1** + leg-(b) gap.
**Engine (ADR-008, Fabric build):** Fabric Warehouse, T-SQL `VIEW`s over a OneLake shortcut.
SQL is T-SQL dialect; views are queried directly (no dbt `ref()` templating — dbt is dropped).
**Why this spec exists:** v1 ships before v1.5, but until now only v1.5 had a build spec. This
brings the first-shipping capability to the same depth.

---

## 0. Scope — the two v1 legs

The v1 north-star (`DATA_MODEL §10`): *"As a marketer, I paste a Drive folder link and search
every video by spoken line / theme / sentiment, getting timestamped clips with a
`standalone_score` so I know what's safe to reuse."* That is two query legs:

- **Leg (a) — Search** the chunk feature store (find clips).
- **Leg (b) — Mix-and-Match** a coherent sequence from compatible chunks (assemble safely).

Both run over the v1 Gold tables only: `fact_chunk`, `dim_asset`, `bridge_chunk_compatibility`,
`dim_keyword_bridge`, `dim_theme_bridge`. No performance tables (those are v1.5).

---

## 1. RULING — vector/semantic search is OUT, full stop, in this Fabric build (ADR-008)

**Decision (@data-architect to ratify):** v1 search is **structured filter + keyword/text-match
search only**. Unlike the sibling repo (where DuckDB VSS made semantic vector search a cheap
v1.5 fast-follow), **this repo has no in-stack vector index at all** — ADR-008 Binding Condition
4 explicitly bans introducing a dedicated vector DB, and Fabric Copilot/Azure OpenAI is scoped
as a QA/summarization veneer only, never a retrieval index (`BACKLOG.md` "Other v2 items").
Semantic search is not "v1.5 fast-follow" here; it is **not assumed by default** — wanting it
would need a fresh ADR weighing a real option (e.g. Azure AI Search) against scope, not a
restated v1.5 plan.

**Rationale:**
1. The north-star is fully satisfiable by structured predicates (`chunk_theme`, `sentiment`,
   `standalone_score`) + keyword/text match on `transcript_segment`. Vector search is the
   *interesting* half but not the *required* half.
2. Embeddings add a second extraction step (an embedding model call per chunk) + a column +
   an index-build/hosting cost — and in this stack, no $0 in-engine fallback exists the way
   DuckDB VSS did, so the cost is real, not deferred-and-cheap. v1 must ship without it.
3. Shipping the deterministic search first means the demo is testable with exact assertions
   (no embedding-similarity fuzziness in the first green build).

**What this means concretely:** v1 uses T-SQL predicates + `LIKE` for keyword search (§2.3).
The `embedding` column on `fact_chunk` (shown in `ERD_consolidated.md`) stays
**reserved/nullable** — present in the schema for portability, populated by nothing in this
repo's locked stack. No model change needed if a future ADR ever revisits this.

---

## 2. Leg (a) — Search surface

### 2.1 Query patterns (the demo serves these)
| # | Marketer question | Mechanism |
|---|-------------------|-----------|
| S1 | "Hooks with energetic sentiment, safe to reuse" | filter `chunk_theme='Hook' AND sentiment='energetic' AND standalone_score>=4` |
| S2 | "Any clip mentioning 'jimat elektrik'" | keyword/FTS on `transcript_segment` |
| S3 | "All clips tagged keyword X" | join `dim_keyword_bridge` |
| S4 | "Which raw video is this clip from" | join `dim_asset` (asset_id) / `bridge_asset_lineage` |

### 2.2 Reference query (S1 + S2 combined)
```sql
-- Reusable clips matching a theme + sentiment + free-text, ranked by safety
-- Gold Warehouse VIEWs queried directly (no dbt ref() — dbt dropped, ADR-008)
select
    c.chunk_id, c.asset_id, a.asset_name,
    c.start_sec, c.end_sec, c.standalone_score,
    c.chunk_theme, c.sentiment, c.transcript_segment
from fact_chunk c
join dim_asset a on a.asset_id = c.asset_id
where c.chunk_theme = 'Hook'
  and c.sentiment   = 'energetic'
  and c.standalone_score >= 4
  and c.transcript_segment like '%jimat elektrik%'   -- T-SQL LIKE; default Fabric Warehouse
                                                       -- collation is case-insensitive (no ILIKE needed)
order by c.standalone_score desc, c.start_sec;
```

### 2.3 Keyword matching (T-SQL `LIKE`, v1 — no in-stack full-text/vector index)
Fabric Warehouse does not carry DuckDB's `fts` extension, and a dedicated full-text or vector
index is out of scope here (§1). v1 keyword matching is plain `LIKE` predicates as in §2.2 — no
BM25 ranking, no relevance score. At this row count (KB–MB scale) a sequential scan with `LIKE`
is not a performance concern; if ranked free-text search is ever wanted, that is new scope
routed through a fresh ADR (§1), not a v1/v1.5 default.

### 2.4 Demo deliverable
`scripts/search_cli.py` — a thin CLI: `python scripts/search_cli.py --theme Hook --sentiment energetic
--min-score 4 --contains "jimat elektrik"` → prints the ranked clip table. (Or a one-cell notebook.)
This is the v1 demo artifact (one screenshot proves the north-star).

---

## 3. Leg (b) — Mix-and-Match assembler (anti-Frankenstein)

The owner's original pain: cutting by timestamp produces incoherent "Frankenstein" videos. The
fix is to assemble only along the compatibility edge, only from standalone-safe chunks.

### 3.1 Rules (from `DATA_MODEL §2` / ADR-002)
- Only chunks with `standalone_score >= 4` are eligible.
- A sequence starts with a `Hook` chunk; each next chunk's `chunk_theme` must appear in the
  previous chunk's `bridge_chunk_compatibility` (the `compatible_theme` adjacency).
- Chunks may come from different assets (that's the point — cross-asset assembly).

### 3.2 Reference query — valid 2-step seeds (Hook → compatible next)
```sql
-- Candidate Hook -> next-chunk pairs that are safe and theme-compatible
-- Gold Warehouse VIEWs queried directly (no dbt ref() — dbt dropped, ADR-008)
select
    h.chunk_id      as hook_chunk,   h.asset_id as hook_asset,  h.transcript_segment as hook_text,
    n.chunk_id      as next_chunk,   n.asset_id as next_asset,  n.chunk_theme as next_theme,
    n.transcript_segment as next_text
from fact_chunk h
join bridge_chunk_compatibility bc on bc.chunk_id = h.chunk_id
join fact_chunk n
     on n.chunk_theme = bc.compatible_theme
    and n.chunk_id <> h.chunk_id
where h.chunk_theme = 'Hook'
  and h.standalone_score >= 4
  and n.standalone_score >= 4
order by h.chunk_id;
```

### 3.3 Full-sequence assembly (v1 = 3-step demo, recursive optional)
For the v1 demo, a 3-step Hook→Body→CTA assembly is enough (chain the 2-step join twice). A
generalized N-step walk over the compatibility graph (a T-SQL recursive CTE — no `RECURSIVE`
keyword needed, unlike DuckDB; self-referencing `WITH cte AS (... UNION ALL ...)`) is a v1.5
enhancement — keep v1 to a fixed-length, readable assembly so the demo is deterministic.

### 3.4 Demo deliverable
`analyses/assemble_sequence.sql` (ad-hoc T-SQL, not a dbt analysis — dbt is dropped, ADR-008)
+ a CLI flag `python scripts/search_cli.py --assemble` printing N candidate coherent sequences
with their source assets and timestamps — ready to hand to an editor (or, in v2, to FFmpeg).

---

## 4. Tests (v1)

| Test | Target | Rule |
|------|--------|------|
| grain | `fact_chunk` | `unique(chunk_id)`, `not_null` — GE expectation on the Silver Delta table |
| FK | `fact_chunk.asset_id` | referential check → `dim_asset` (GE or a Warehouse view-level assertion) |
| range | `fact_chunk.standalone_score` | GE expectation, between 1 and 5 |
| asset type | `dim_asset.asset_type` | GE `accepted_values`-equivalent: `['RAW','EDITED']` |
| no orphan compat | `bridge_chunk_compatibility.chunk_id` | referential check → `fact_chunk` |
| assembler safety | `assemble_sequence` | assert every chunk in any returned sequence has `standalone_score >= 4` (a single GE/script-level assertion — no dbt) |
| search smoke | `search_cli` | golden: on the seed fixtures, S1 returns the expected hook chunk |

---

## 5. Build order

1. `dim_asset` (from `asset_manifest` seed) + `fact_chunk` + `bridge_chunk_compatibility` +
   keyword/theme bridges — build the Gold Warehouse views (`warehouse/core/*.sql`, F2) over
   the Silver Delta tables (no dbt; dbt is dropped, ADR-008).
2. `scripts/search_cli.py` leg (a) — structured + `LIKE` (§2.3 — no in-stack full-text index).
3. `analyses/assemble_sequence.sql` + `--assemble` flag — leg (b).
4. Wire the two demo commands into `README_BUILD.md` as the v1 demo.

**Out of v1, and not assumed for v1.5 either (§1 — no in-stack vector index, ADR-008):**
embeddings + semantic vector search. **Out of v1, planned for v1.5:** recursive N-step
assembly · all performance tables (separate `SPEC_v1.5_performance_marts.md`). **Out of v1/v1.5,
v2 only:** FFmpeg render.
