#!/usr/bin/env python3
"""Governance hook — makes Claude check governed docs/ADRs BEFORE and AFTER touching governed files.

Wired in .claude/settings.json for Edit|Write|MultiEdit:
  • PreToolUse  → inject a "STOP, read these docs first" reminder when the target file is
                  under governance (non-blocking context nudge).
  • PostToolUse → auto-run the matching contract test(s) after the edit; exit 2 with the
                  failure so Claude is FORCED to see and fix it (hard block).

Two contracts, two owners (CLAUDE.md governance axes):
  - tests/lineage_contract.py   — @data-architect, ADR-006 manifest/identity fidelity
  - tests/boundary_contract.py  — @data-architect (stack, ADR-001/004/005/008) +
                                   @scope-guardian (v1 Scope LOCKED)

A path can match more than one rule (e.g. an ingest notebook/script is both
lineage-governed AND under the stack boundary) — all matching contracts run.

Reads the hook JSON from stdin. Stdlib only. Never crashes the tool call on its own bug
(any internal error → exit 0).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

LINEAGE_MSG = (
    "(1) client_id resolves in dim_client.csv, "
    "(2) asset_id == sha256('client_id:content_sha256') [ADR-006], "
    "(3) source_uri path segments match the client_id + asset_id columns "
    "[abfss://...onelake..., ADR-008]."
)
BOUNDARY_MSG = (
    "no Databricks/Glue/boto3-S3-SDK/vector-DB/RAG-framework/dashboard-framework/live-ad-connector "
    "imports or deps (ADR-001/004/005/008 + v1 Scope LOCKED). PySpark itself is ALLOWED (ADR-008)."
)
ERD_MSG = "Clean-ERD Doctrine: 1 table = 1 grain = 1 entity, bridge tables (not CTEs) for N:N, serving = view never a duplicated physical table."

# (path substring, docs to cite, reminder message, contract scripts to run post-edit)
RULES: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("seeds/asset_manifest.csv", "ADR-006 + ADR-008 (OneLake path grammar) + architecture/LINEAGE_CONTRACT.md, DATA_DICTIONARY.md", LINEAGE_MSG, ("lineage_contract.py",)),
    ("seeds/dim_client.csv", "ADR-006 (tenant identity) + architecture/STTM.md", LINEAGE_MSG, ("lineage_contract.py",)),
    ("ingest_drive", "ADR-006 (path/identity) + ADR-008 (OneLake) + architecture/LINEAGE_CONTRACT.md", LINEAGE_MSG, ("lineage_contract.py",)),
    ("warehouse/", "Clean-ERD Doctrine + architecture/DATA_MODEL.md (.claude/agents/data-architect.md)", ERD_MSG, ()),
    ("warehouse/", "ADR-001/004/005/008 stack boundary + architecture/BOUNDARY_CONTRACT.md", BOUNDARY_MSG, ("boundary_contract.py",)),
    ("notebooks/", "ADR-001/004/005/008 stack boundary + v1 Scope LOCKED + architecture/BOUNDARY_CONTRACT.md", BOUNDARY_MSG, ("boundary_contract.py",)),
    ("scripts/", "ADR-001/004/005/008 stack boundary + v1 Scope LOCKED + architecture/BOUNDARY_CONTRACT.md", BOUNDARY_MSG, ("boundary_contract.py",)),
    ("requirements.txt", "ADR-001/004/005/008 + v1 Scope LOCKED + architecture/BOUNDARY_CONTRACT.md", BOUNDARY_MSG, ("boundary_contract.py",)),
    ("setup.sh", "ADR-008 (OneLake, no MinIO/S3 escape hatch) + architecture/BOUNDARY_CONTRACT.md — keep generated files in sync with the real ones", BOUNDARY_MSG, ("boundary_contract.py",)),
]


def _rel(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO))
    except (ValueError, OSError):
        return path or ""


def _matches(rel: str) -> list[tuple[str, str, str, tuple[str, ...]]]:
    return [r for r in RULES if r[0] in rel]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    event = data.get("hook_event_name", "")
    rel = _rel((data.get("tool_input") or {}).get("file_path", ""))
    matches = _matches(rel)
    if not matches:
        return 0

    if event == "PreToolUse":
        lines = [f"⚠️ GOVERNED FILE: {rel} is under governance. Before editing, confirm against:"]
        for _, docs, msg, _ in matches:
            lines.append(f"  - {docs}: {msg}")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "\n".join(lines)}}))
        return 0

    if event == "PostToolUse":
        contracts: list[str] = []
        for _, _, _, scripts in matches:
            for s in scripts:
                if s not in contracts:
                    contracts.append(s)

        failures = []
        for script in contracts:
            proc = subprocess.run(
                [sys.executable, str(REPO / "tests" / script)],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                failures.append(f"--- {script} ---\n{proc.stdout}{proc.stderr}")

        if failures:
            sys.stderr.write("Contract check FAILED after your edit — fix before continuing:\n" + "\n".join(failures))
            return 2  # feeds stderr back to Claude as a blocking error
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # never let a hook bug break the user's tool call
        raise SystemExit(0)
