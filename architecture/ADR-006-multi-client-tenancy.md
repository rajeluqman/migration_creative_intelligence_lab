# ADR-006 — Multi-client tenancy (dim_client + tenant-scoped asset identity)

- **Status:** Accepted (ratified by @data-architect; owner sign-off to implement 2026-06-22)
- **Date:** 2026-06-22
- **Deciders:** @data-architect (ultimate veto — author), owner (sign-off to build),
  @senior-data-engineer (buildability), @scope-guardian (additive-only, no v1 scope creep)
- **Amends:** `DATA_MODEL.md` §3/§4/§6/§10, `ERD_consolidated.md` §1/§2/§3/§5/§6,
  `DATA_DICTIONARY.md`, `STTM.md` (`dim_asset` lineage), `ingest_drive_to_s3.py` docstring
  (path-inconsistency flag resolved in favour of the client-partitioned form).
- **Does NOT touch:** ADR-002 (graph over star), ADR-003 (chunking in Silver), ADR-004
  (perf-veto), ADR-005 (storage/serving). This is **purely additive** — the two facts, the
  bridges, and every existing SCD strategy are unchanged.

## Context

The pipeline serves more than one client, but the Gold model has no client dimension. Two
concrete defects follow from that omission:

1. **Commingling defect.** There is no `client_id` anywhere in Gold. A query cannot scope a
   search to one client's footage; every chunk lives in one undifferentiated pool. This is a
   correctness and a confidentiality problem, not a convenience gap.
2. **Cross-tenant identity collision.** `asset_id = SHA-256(video bytes)` is a *global*
   content hash. Two different clients delivering byte-identical stock footage (a common,
   licensed-clip reality) hash to the **same** `asset_id` → one `dim_asset` row → silent
   cross-tenant attribution. Client B's chunks, lineage, and (in v1.5) performance would
   merge into Client A's asset. A content hash is the right identity *within a tenant*; it is
   the wrong identity *across* tenants.

The existing `content_sha256` near-duplicate signal (`dq_flag = likely_near_dup`) must be
preserved — that is intra-client de-dup and it is correct. The fix must not collapse it.

## Decision

### A — `dim_client` is a new, first-class dimension (one domain = one dimension)

A new Gold dimension `dim_client`. Grain: **one row per client account.** Per Clean-ERD
Doctrine axis 2, client semantics get their own dimension; they are **not** overloaded onto
`dim_asset`.

| column | type | notes |
|--------|------|-------|
| `client_id` (PK) | VARCHAR | short stable slug, e.g. `voltecx` — used as the S3 partition token |
| `client_name` | VARCHAR | display name |
| `account_support_owner` | VARCHAR | internal owner of the relationship |
| `drive_folder_id` | VARCHAR | the client's source Google Drive folder |
| `landing_ttl_days` | INT | per-client landing retention (feeds ADR-007's guarded delete) |
| `status` | VARCHAR | `active` \| `paused` \| `offboarded` |

**SCD strategy: SCD0 reference.** `client_id` is an immutable assigned key; the descriptive
columns are operational reference data, hand-curated via a seed, rebuilt on each run. No
history table — consistent with `dim_platform` (ERD §5). `dim_client` is sourced from a seed
(`seeds/dim_client.csv`), not from the ingestion manifest.

### B — `client_id` FK on `dim_asset`; identity scoped to (client_id, content_sha256)

- `dim_asset` gains `client_id` (FK → `dim_client`) and keeps `content_sha256` as a
  **separate non-key column** (the within-client near-dup signal that drives `dq_flag`).
- Asset identity is now **scoped to the tenant**: the logical key is
  `(client_id, content_sha256)`.

### C — Physical key form (the unambiguous pick)

**`asset_id = SHA-256( client_id || ':' || content_sha256 )`.** A deterministic composite
hash, not a random surrogate.

Rationale for this form over a concatenated `asset_key`:
- `asset_id` stays a **single VARCHAR PK**. Every downstream contract that already keys on
  `asset_id` — the Bronze path convention `bronze/<client_id>/asset_raw/<asset_id>.parquet`,
  `stg_gemini_raw.sql`, `fact_chunk.asset_id`, all `relationships` tests — keeps working
  **unchanged**. No FK widened to a composite, no join rewrites.
- It is still **content-addressed and deterministic**: same client + same bytes → same
  `asset_id`, every time, with no lookup. Idempotency and re-parse-from-Bronze survive.
- `content_sha256` remains visible as its own column for intra-client de-dup, so the
  near-dup signal is not destroyed by folding the client in.

### D — `client_id` is NOT a stored column on `fact_chunk`

Per Clean-ERD Doctrine axis 4 (serving = view, never a duplicated truth) and the grain rule:
`fact_chunk` grain is **one semantic chunk** and nothing else. Client is reached by join
(`fact_chunk.asset_id → dim_asset.client_id`). If filter performance on a serving surface
demands a pre-joined `client_id`, it is exposed on a **VIEW**, never stored on the fact.

### E — Cost firewall (§9) preserved

Skip-existing becomes **client-scoped**: the same client re-delivering the same bytes still
hashes to the same `asset_id` and is skipped — re-delivery is still free. Only the *cross-client*
collapse is stopped (two clients, identical bytes → two distinct `asset_id`s, as it must be).
The §9 firewall ("re-parse, never re-pay") is untouched.

### F — Removal / re-curation is deliberately OUT for v1

Support staff removing a video from a client's curated Drive folder (an asset leaving the
client's *current curated set*) is **named OUT for v1** (ERD §6, DATA_MODEL §6). Landing and
Bronze stay append-only and immutable — **removal never deletes Bronze.** The v1.5 model for
this is `bridge_client_asset_curation` (SCD2 membership of an asset in a client's current
curated set), recorded here so it is a named future object, not an accidental gap.

## Rationale

- A content hash is the correct identity *within* a trust boundary and the wrong identity
  *across* one. Scoping the hash to `client_id` makes the identity match the actual grain of
  uniqueness ("this client's copy of these bytes").
- Choosing the deterministic-hash form keeps `asset_id` a single PK, so the change is additive
  at the schema level and a no-op at the join level — the cheapest correct fix.
- `dim_client` as its own dimension keeps `dim_asset` domain-pure; it carries operational
  attributes (`drive_folder_id`, `landing_ttl_days`) that belong to the *client*, not the asset.

## Rejected alternatives

1. **`client_id` as a plain prefix column on `dim_asset`, identity left as the global byte
   hash.** Rejected: leaves the collision intact — two clients, identical bytes still share one
   `asset_id` PK; the FK would not save the row from merging.
2. **Concatenated composite key `asset_key = client_id || content_sha256` as the PK.** Rejected:
   forces a composite FK through `fact_chunk` and every bridge, rewriting joins and the Bronze
   path for no identity benefit the hash form doesn't already give.
3. **Overload `dim_asset` with client attributes (folder id, TTL, owner).** 🛑 Clean-ERD axis 2
   violation (mixed-domain dimension). Client operational data is a second entity.
4. **Store `client_id` on `fact_chunk` for filter speed.** Rejected as the default (axis 4) —
   reach by join; promote to a serving view only if a query proof demands it.
5. **Separate physical bucket/database per client.** Rejected at this scale: operational
   sprawl, breaks the single Gold-S3 source-of-truth (ADR-005) for no v1 benefit; row-level
   `client_id` scoping is sufficient for <10K videos.

## Consequences

- **Positive:** cross-tenant collision eliminated; per-client search/scoping enabled; the
  intra-client near-dup signal preserved; change is additive and join-stable; `dim_asset` stays
  domain-pure.
- **Negative / accepted:** `asset_manifest.csv` gains a `client_id` column and the ingestion
  script must compute `asset_id` from `(client_id, content_sha256)` rather than raw bytes —
  a one-line derivation change (see hand-off). The byte-hash is retained as `content_sha256`.
- **Bounded:** removal/re-curation stays OUT for v1 (named, not silently dropped);
  `bridge_client_asset_curation` is the v1.5 home for it.

## Clean-ERD verdict

grain ✓ · domain-purity ✓ · bridges-not-CTE ✓ (curation deferred as a real bridge, not a CTE)
· serving-as-view ✓ (`client_id` on facts via join/view) · SCD-isolated ✓ (`dim_client` SCD0)
