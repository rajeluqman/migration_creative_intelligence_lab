# ADR-002 — Asset-lineage graph + chunk feature store over a Kimball star

- **Status:** Accepted
- **Date:** 2026-06-20
- **Deciders:** @data-architect (ratified, AMENDED ruling), @senior-data-engineer; @analytics-engineer dissent overruled
- **Context refs:** `DATA_MODEL.md` §1–4, round-1 debate Q1/Q4, `ERD_consolidated.md`
- **Supersedes the default assumption** that a portfolio DE pipeline must land a Kimball star.

## Context

The pipeline turns advertising video into queryable creative intelligence. The conceptual model
has two first-class entities (`asset`, `chunk`) and two relationships that are graph edges by
nature: asset→asset lineage (RAW→EDITED) and chunk↔chunk compatibility (mix-and-match adjacency).
The owner's instinct (and the other four portfolio pipelines) leaned toward a Kimball star.

## Decision

Model Gold as an **asset-lineage graph + chunk feature store**: `dim_asset` (node, self-referencing
`parent_asset_id`), `fact_chunk` (feature row, grain = one semantic chunk), and explicit edge/bridge
tables (`bridge_asset_lineage`, `bridge_chunk_compatibility`). A vector index (DuckDB VSS) sits
**beside** the relational model, never inside a column. Do **not** force a Kimball star.

## Rationale

1. **No additive fact, no stable measurement grain.** A star models a measurement process against
   conformed dimensions. Here the "facts" are LLM-extracted features (`standalone_score`,
   `chunk_theme`, `sentiment`) — opinions with confidence, not additive metrics. There is nothing
   to `SUM` across dimensions.
2. **The query pattern is graph traversal, not slice-and-dice.** Real queries traverse RAW→EDITED
   children→chunks→compatible-next-chunks. Forcing a star means fighting the model every time
   `next_compatible_themes[]` needs a self-join.
3. **Honesty / seniority signal.** Bolting a 4th conformed dimension on to "look Kimball" is
   cargo-cult an experienced reviewer will spot. Naming the model what it is (graph + feature store)
   and justifying it is the stronger signal.
4. **Arrays are a query-hostile smell** → exploded into bridge tables (`dim_keyword_bridge`,
   `dim_theme_bridge`), one row per chunk per tag. No `ARRAY` columns survive into Gold.

## Rejected alternatives

| Alternative | Why rejected |
|-------------|--------------|
| **Kimball star (fact_chunk + 4 conformed dims)** | No additive fact; graph traversal fights the star; the 4th dim would be cosmetic. |
| **Flat Gold table (one wide row per chunk)** | Discards `bridge_chunk_compatibility` — the entire anti-Frankenstein mechanism and the north-star query. (See ADR — flat fallback rejected, round-1.) |
| **Pure graph DB (Neo4j etc.)** | New infra outside the locked stack; relational + bridge tables in DuckDB express the graph adequately at this scale. |

## Consequences

- **Positive:** the model matches the domain; mix-and-match and lineage are first-class; dbt + DuckDB
  express it natively; the v1.5 performance layer attaches cleanly via `bridge_ad_chunk`.
- **Negative / accepted:** "graph + feature store" needs a one-line explanation to stakeholders used
  to stars — handled by `ERD_consolidated.md`.
- **@analytics-engineer dissent:** instinct toward a star was overruled; its dbt-layering and
  array-explosion contributions were adopted in full.
- **Locked:** grain = semantic chunk; no star refactor without a new ADR.
