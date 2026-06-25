# Fabric notebook (source .py form) — load seed CSVs into OneLake Delta tables.
# The Fabric equivalent of `dbt seed` (dbt dropped, ADR-008). The Gold Warehouse views and the
# Silver join logic reference these as Delta tables: dim_client, dim_platform, asset_manifest,
# map_ad_asset, edit_decision_list. Idempotent (overwrite). Run once before the Gold views build.
# RUNTIME-UNVERIFIED against real Fabric (SESSION_LOG 2026-06-24).
from __future__ import annotations

import os
from pathlib import Path

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()  # Fabric-injected session

SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"
SEED_TABLES = ["dim_client", "dim_platform", "asset_manifest", "map_ad_asset", "edit_decision_list"]
# Local path to the repo's seeds when the repo is synced into the Lakehouse Files area; adjust to
# the workspace's actual seeds location at run time. abfss form also valid via env.
_BASE = (
    f"abfss://{os.environ['FABRIC_WORKSPACE']}@onelake.dfs.fabric.microsoft.com/"
    f"{os.environ['FABRIC_LAKEHOUSE']}.Lakehouse"
)


def load_seed(name: str) -> None:
    csv_path = str(SEEDS_DIR / f"{name}.csv")
    df = spark.read.option("header", True).option("inferSchema", True).csv(csv_path)
    df.write.format("delta").mode("overwrite").saveAsTable(name)


if __name__ == "__main__":
    for table in SEED_TABLES:
        load_seed(table)
    print(f"loaded {len(SEED_TABLES)} seed tables into {_BASE}/Tables/")
