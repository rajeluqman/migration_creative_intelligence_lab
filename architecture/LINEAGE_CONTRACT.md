# LINEAGE & DATA-FIDELITY CONTRACT

> **Owner:** @data-architect (ULTIMATE VETO). **Enforced by:** `tests/lineage_contract.py`
> (CI + pre/post-edit hook). **Status:** active. **Source ADR:** ADR-006 (tenant-scoped
> identity) + ADR-008 (OneLake path grammar, 2026-06-24 — identity formula itself unchanged).

## Why this exists
A doc or ADR is *guidance* — an LLM or a tired human can skip it. This contract is the same
rule expressed as **code that runs automatically**, so "check lineage & fidelity FIRST" is
enforced, not remembered. If the manifest drifts from the model, the build goes red and the
edit is blocked. Nobody has to babysit it.

## What it governs
The landing manifest (`seeds/asset_manifest.csv`) — the lineage spine that ties every raw
asset back to a **real client** and a **content hash**, with a storage path that proves it.

## The rules (all HARD unless noted)
| # | Rule | Rationale |
|---|------|-----------|
| R1 | Required cols (`asset_id, client_id, content_sha256, asset_type, source_uri`) non-empty | no headless rows |
| R2 | `asset_id`, `content_sha256` are 64-char lowercase hex | content-hash identity |
| R3 | **Identity:** `asset_id == sha256("{client_id}:{content_sha256}")` | ADR-006 tenant-scoped key — folds client into the id |
| R4 | `source_uri == abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/Files/landing/<client_id>/video/<asset_id>.<ext>`, and the path's client + hash segments **equal** their columns | storage path *proves* lineage; no drift |
| R5 | **Referential:** `client_id` exists in `seeds/dim_client.csv` | no orphan tenant |
| R6 | `asset_id` unique | one row per asset |
| R7 | `client_id` not a generic placeholder; *grandfathered* ids WARN instead of fail | real short codes, debt stays named |

## The `demo_client` debt — RESOLVED 2026-06-22
The placeholder `demo_client` slug was renamed to the real client short code **`voltecx`**
(matching `dim_client.csv` → VoltecX) during the first real Drive run. All `asset_id`s (R3)
and `source_uri`s (R4) were re-derived under the new slug (the hash folds `client_id`, so this
was a deliberate, tracked migration — not a string swap), and the manifest re-landed clean.
`demo_client` stays in the `PLACEHOLDER_DENYLIST` (it remains a forbidden generic name) but is
**no longer `GRANDFATHERED`** — no row uses it. A future placeholder client (e.g. `test`,
`tbd`) still hard-fails R7 as intended.

## Path-scheme migration — 2026-06-24 (ADR-008)
Storage moved S3 → OneLake. `source_uri` values and the R4 regex were rewritten from
`s3://creative-intel-lake/landing/...` to
`abfss://creative-intel-ws@onelake.dfs.fabric.microsoft.com/creative_intel_lh.Lakehouse/Files/landing/...`.
**The identity formula did not move**: `asset_id == sha256("{client_id}:{content_sha256}")`
(R3) is independent of storage path, so no hash was recomputed — only the `source_uri` column
in `seeds/asset_manifest.csv` was rewritten to the new scheme.

## How to run
```bash
python tests/lineage_contract.py                      # default seeds/
python tests/lineage_contract.py <manifest> <dim_client>
```
- **CI:** `.github/workflows/ci.yml` → "Lineage contract" gate (PR + push to main).
- **Hook:** `.claude/hooks/governance_guard.py` auto-runs it after any edit to the manifest,
  `dim_client.csv`, or the ingest script, and blocks on failure.

## Changing a rule
Rules are owned by @data-architect. To relax/extend one: update this doc AND
`tests/lineage_contract.py` in the same change, with a one-line rationale — same as an ERD edit.
