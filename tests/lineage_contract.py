#!/usr/bin/env python3
"""Lineage & data-fidelity contract — deterministic gate over the landing manifest.

This is the ENFORCEMENT half of architecture/LINEAGE_CONTRACT.md. The doc states the
rules; this script makes them true on every CI run, pre-commit, and post-edit hook.
It encodes @data-architect's "check lineage & fidelity FIRST" so it does not depend on
anyone (human or LLM) remembering to look. Code does not get tired.

Validates seeds/asset_manifest.csv against seeds/dim_client.csv. Stdlib only ($0, no deps).
Exit 0 = contract holds. Exit 1 = hard violation (blocks build/edit).

Rules (all HARD unless noted):
  R1  required columns present and non-empty
  R2  asset_id and content_sha256 are 64-char lowercase hex
  R3  IDENTITY (ADR-006): asset_id == sha256(f"{client_id}:{content_sha256}")
  R4  source_uri == abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/
      Files/landing/<client_id>/video/<asset_id>.<ext> (ADR-008, OneLake path grammar), and the
      <client_id> + <asset_id> path segments MATCH their columns (no lineage drift)
  R5  REFERENTIAL: client_id exists in dim_client.csv (no orphan tenant)
  R6  asset_id is unique
  R7  client_id not a placeholder (denylist) — HARD, except GRANDFATHERED ids which
      emit a loud WARN so the debt stays named (Clean-ERD doctrine) instead of silent

Run:  python tests/lineage_contract.py            # default seeds/
      python tests/lineage_contract.py <manifest.csv> <dim_client.csv>
"""

from __future__ import annotations

import csv
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "seeds" / "asset_manifest.csv"
DIM_CLIENT = REPO / "seeds" / "dim_client.csv"

REQUIRED_COLS = ["asset_id", "client_id", "content_sha256", "asset_type", "source_uri"]
HEX64 = re.compile(r"^[0-9a-f]{64}$")
# abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/Files/landing/
# <client_id>/video/<asset_id>.<ext>   (ADR-006 client-partitioned identity, ADR-008 OneLake path)
URI = re.compile(
    r"^abfss://(?P<workspace>[^@]+)@onelake\.dfs\.fabric\.microsoft\.com/"
    r"(?P<lakehouse>[^/]+)\.Lakehouse/Files/landing/(?P<client>[^/]+)/video/"
    r"(?P<hash>[0-9a-f]{64})\.\w+$"
)

# Generic non-client names that must never reach production lineage.
PLACEHOLDER_DENYLIST = {"", "demo_client", "test", "tbd", "todo", "unknown", "client", "na", "none"}
# Grandfathered debt is now EMPTY — the demo_client placeholder was renamed to the real slug
# 'voltecx' on 2026-06-22 (asset_ids re-derived; see architecture/LINEAGE_CONTRACT.md). demo_client
# stays denylisted (still a forbidden generic name) but no longer needs a WARN-only exemption.
GRANDFATHERED: set[str] = set()


def _load_clients(path: Path) -> set[str]:
    with path.open(newline="") as f:
        return {r["client_id"] for r in csv.DictReader(f)}


def check(manifest: Path, dim_client: Path) -> list[str]:
    errors: list[str] = []
    warns: list[str] = []
    clients = _load_clients(dim_client)
    seen: dict[str, int] = {}
    grandfathered_hits: dict[str, int] = {}

    with manifest.open(newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # +1 header, +1 to 1-index
            cid = (row.get("client_id") or "").strip()
            sha = (row.get("content_sha256") or "").strip()
            aid = (row.get("asset_id") or "").strip()
            uri = (row.get("source_uri") or "").strip()
            tag = f"row {i} ({row.get('asset_name', '?')[:30]})"

            # R1 required
            for col in REQUIRED_COLS:
                if not (row.get(col) or "").strip():
                    errors.append(f"R1 {tag}: required column '{col}' is empty")

            # R2 hex shape
            if not HEX64.match(aid):
                errors.append(f"R2 {tag}: asset_id not 64-hex: {aid!r}")
            if not HEX64.match(sha):
                errors.append(f"R2 {tag}: content_sha256 not 64-hex: {sha!r}")

            # R3 identity formula (ADR-006)
            if HEX64.match(sha) and cid:
                expect = hashlib.sha256(f"{cid}:{sha}".encode()).hexdigest()
                if expect != aid:
                    errors.append(
                        f"R3 {tag}: asset_id {aid[:12]}… != sha256('{cid}:content_sha256')={expect[:12]}…"
                    )

            # R4 uri lineage consistency
            m = URI.match(uri)
            if not m:
                errors.append(f"R4 {tag}: source_uri does not match abfss://...onelake.../Files/landing/<client>/video/<asset_id>.<ext>: {uri}")
            else:
                if m.group("client") != cid:
                    errors.append(f"R4 {tag}: uri client segment '{m.group('client')}' != client_id '{cid}'")
                if m.group("hash") != aid:
                    errors.append(f"R4 {tag}: uri hash segment {m.group('hash')[:12]}… != asset_id {aid[:12]}…")

            # R5 referential integrity
            if cid and cid not in clients:
                errors.append(f"R5 {tag}: client_id '{cid}' has no row in dim_client.csv (orphan tenant)")

            # R6 uniqueness
            if aid in seen:
                errors.append(f"R6 {tag}: duplicate asset_id (first seen row {seen[aid]})")
            else:
                seen[aid] = i

            # R7 placeholder
            if cid in PLACEHOLDER_DENYLIST:
                if cid in GRANDFATHERED:
                    grandfathered_hits[cid] = grandfathered_hits.get(cid, 0) + 1
                else:
                    errors.append(f"R7 {tag}: client_id '{cid}' is a placeholder — use a real client short code")

    for cid, count in sorted(grandfathered_hits.items()):
        warns.append(f"R7: client_id '{cid}' is a GRANDFATHERED placeholder on {count} row(s) — rename (ADR-006)")
    for w in warns:
        print(f"⚠️  WARN  {w}")
    return errors


def main(argv: list[str]) -> int:
    manifest = Path(argv[1]) if len(argv) > 1 else MANIFEST
    dim_client = Path(argv[2]) if len(argv) > 2 else DIM_CLIENT
    if not manifest.exists() or not dim_client.exists():
        print(f"❌ missing seed: {manifest} / {dim_client}", file=sys.stderr)
        return 1

    errors = check(manifest, dim_client)
    if errors:
        print(f"\n❌ LINEAGE CONTRACT FAILED — {len(errors)} violation(s):", file=sys.stderr)
        for e in errors:
            print(f"   • {e}", file=sys.stderr)
        print("\n   See architecture/LINEAGE_CONTRACT.md + ADR-006. Fix before proceeding.", file=sys.stderr)
        return 1
    print("✅ lineage contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
