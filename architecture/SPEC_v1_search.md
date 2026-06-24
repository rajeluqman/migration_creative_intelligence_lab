# BUILD SPEC — v1 Search & Mix-and-Match Demo (ships FIRST)

**Status:** Draft for build · **Owner:** @senior-data-engineer · **Authority:** `DATA_MODEL.md`
(ratified v1 AoR), ADR-002/003. Closes gap-check **BLOCKER-1** + leg-(b) gap.
**Engine:** DuckDB + dbt-duckdb. SQL is DuckDB dialect.
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

## 1. RULING — vector/VSS is OUT of v1, IN for v1.5 (fast-follow)

**Decision (@data-architect to ratify):** v1 search is **structured filter + keyword/full-text
search only**. Semantic vector search (embeddings + DuckDB VSS) is a **v1.5 fast-follow**, not v1.

**Rationale:**
1. The north-star is fully satisfiable by structured predicates (`chunk_theme`, `sentiment`,
   `standalone_score`) + keyword/text match on `transcript_segment`. Vector search is the
   *interesting* half but not the *required* half.
2. Embeddings add a second extraction step (an embedding model call per chunk) + a column +
   an index-build cost. That is real scope, and v1 must ship.
3. Shipping the deterministic search first means the demo is testable with exact assertions
   (no embedding-similarity fuzziness in the first green build).

**What this means concretely:** v1 uses DuckDB's built-in predicates + the `fts` extension for
keyword search. The `embedding` column on `fact_chunk` (shown in `ERD_consolidated.md`) is
**reserved/nullable in v1**, populated in v1.5 when VSS lands. No model change needed to add it later.

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
select
    c.chunk_id, c.asset_id, a.asset_name,
    c.start_sec, c.end_sec, c.standalone_score,
    c.chunk_theme, c.sentiment, c.transcript_segment
from {{ ref('fact_chunk') }} c
join {{ ref('dim_asset') }} a using (asset_id)
where c.chunk_theme = 'Hook'
  and c.sentiment   = 'energetic'
  and c.standalone_score >= 4
  and c.transcript_segment ilike '%jimat elektrik%'   -- v1.5: replace/augment with FTS or VSS
order by c.standalone_score desc, c.start_sec;
```

### 2.3 Full-text option (DuckDB `fts`, optional in v1)
```sql
install fts; load fts;
-- build once after fact_chunk materializes:
pragma create_fts_index('fact_chunk', 'chunk_id', 'transcript_segment');
-- query:
select *, fts_main_fact_chunk.match_bm25(chunk_id, 'jimat elektrik') as score
from fact_chunk where score is not null order by score desc;
```

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
select
    h.chunk_id      as hook_chunk,   h.asset_id as hook_asset,  h.transcript_segment as hook_text,
    n.chunk_id      as next_chunk,   n.asset_id as next_asset,  n.chunk_theme as next_theme,
    n.transcript_segment as next_text
from {{ ref('fact_chunk') }} h
join {{ ref('bridge_chunk_compatibility') }} bc on bc.chunk_id = h.chunk_id
join {{ ref('fact_chunk') }} n
     on n.chunk_theme = bc.compatible_theme
    and n.chunk_id <> h.chunk_id
where h.chunk_theme = 'Hook'
  and h.standalone_score >= 4
  and n.standalone_score >= 4
order by h.chunk_id;
```

### 3.3 Full-sequence assembly (v1 = 3-step demo, recursive optional)
For the v1 demo, a 3-step Hook→Body→CTA assembly is enough (chain the 2-step join twice). A
generalized N-step walk over the compatibility graph (DuckDB `WITH RECURSIVE`) is a v1.5
enhancement — keep v1 to a fixed-length, readable assembly so the demo is deterministic.

### 3.4 Demo deliverable
`analyses/assemble_sequence.sql` (dbt analysis) + a CLI flag `python scripts/search_cli.py
--assemble` printing N candidate coherent sequences with their source assets and timestamps —
ready to hand to an editor (or, in v2, to FFmpeg).

---

## 4. Tests (v1)

| Test | Target | Rule |
|------|--------|------|
| grain | `fact_chunk` | `unique(chunk_id)`, `not_null` |
| FK | `fact_chunk.asset_id` | `relationships` → `dim_asset` |
| range | `fact_chunk.standalone_score` | `dbt_expectations` between 1 and 5 |
| asset type | `dim_asset.asset_type` | `accepted_values ['RAW','EDITED']` |
| no orphan compat | `bridge_chunk_compatibility.chunk_id` | `relationships` → `fact_chunk` |
| assembler safety | `assemble_sequence` | assert every chunk in any returned sequence has `standalone_score >= 4` (a singular dbt test) |
| search smoke | `search_cli` | golden: on the seed fixtures, S1 returns the expected hook chunk |

---

## 5. Build order

1. `dim_asset` (from `asset_manifest` seed) + `fact_chunk` + `bridge_chunk_compatibility` + keyword/theme bridges — `dbt build -s marts.core`.
2. `scripts/search_cli.py` leg (a) — structured + `ilike`; add `fts` index if time permits.
3. `analyses/assemble_sequence.sql` + `--assemble` flag — leg (b).
4. Wire the two demo commands into `README_BUILD.md` as the v1 demo.

**Out of v1 (→ v1.5 / v2):** embeddings + VSS semantic search · recursive N-step assembly ·
FFmpeg render · all performance tables (separate `SPEC_v1.5_performance_marts.md`).
