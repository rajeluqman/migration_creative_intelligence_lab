#!/usr/bin/env bash
# =============================================================================
# setup.sh — Creative Intelligence Pipeline (Microsoft Fabric build) local setup.
#
# Ported from the sibling repo's dbt-duckdb scaffold (ADR-008). There is NO local engine to
# build against here — Bronze/Silver run as PySpark notebooks IN the Fabric workspace and Gold
# is T-SQL views in a Fabric Warehouse. So this only: creates the venv, installs the local/dev
# deps (Drive + Gemini SDKs, GE, scipy), copies .env, and runs the static gates the CI also runs
# (lint + compile + lineage/boundary contracts). It does NOT scaffold dbt models or run dbt.
#
# Usage:
#   bash setup.sh              # venv + install + static gates
#   SKIP_INSTALL=1 bash setup.sh   # gates only (no venv/pip)
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
echo "==> Repo: $ROOT"

# Directory layout (created if missing; existing files untouched).
mkdir -p notebooks warehouse/core warehouse/performance pipelines scripts seeds \
         great_expectations/expectations analyses

echo "==> Fabric build layout:"
echo "    notebooks/   — Bronze/Silver PySpark + ingest/extract (run in the Fabric workspace)"
echo "    warehouse/   — Gold T-SQL VIEW definitions (deploy to the Fabric Warehouse)"
echo "    pipelines/   — Fabric Data Factory pipeline JSON"
echo "    scripts/     — env guard, OneLake I/O, TTL, significance post-step"

if [ "${SKIP_INSTALL:-0}" != "1" ] && command -v python3 >/dev/null 2>&1; then
  echo "==> Creating venv + installing requirements..."
  python3 -m venv venv
  # shellcheck disable=SC1091
  . venv/bin/activate
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
  [ -f .env ] || { [ -f .env.example ] && cp .env.example .env && echo "    created .env from .env.example (fill it in)"; }
else
  echo "==> SKIP_INSTALL set (or python3 missing); skipping venv/pip."
fi

echo "==> Static gates (same as CI):"
python3 -m py_compile scripts/*.py notebooks/*.py tests/*.py .claude/hooks/*.py && echo "    py_compile OK"
python3 tests/lineage_contract.py
python3 tests/boundary_contract.py
echo "==> Done. Next: open the Fabric workspace, attach the Lakehouse, run notebooks 00->03,"
echo "    then deploy warehouse/*.sql as Gold views and import pipelines/creative_intel_fabric.json."
