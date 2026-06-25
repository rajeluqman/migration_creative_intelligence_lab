# Fabric notebook (source .py form) — Silver: Bronze (verbatim Gemini JSON, Files/) -> Delta
# Tables. Ported from the sibling repo's dbt Silver models (stg_gemini_raw, stg_meta_perf,
# stg_tiktok_perf, int_chunk_cleaned, int_ad_perf_unioned) — DuckDB SQL -> PySpark, ADR-008.
# GRAIN + LOGIC UNCHANGED; only the engine moved (DuckDB unnest(json_extract) -> Spark
# explode(from_json); chunking lives HERE at the Bronze->Silver hop, ADR-003).
#
# Array handling: Fabric Warehouse T-SQL over OneLake does NOT read Delta complex (array/struct)
# columns cleanly, so the array fan-outs that were Gold `unnest()` views in the sibling repo are
# exploded HERE in Spark into their own scalar-only Delta tables (silver_chunk_compatibility,
# silver_chunk_keyword). The Gold Warehouse bridge views are then plain passthrough SELECTs.
# silver_chunk itself is kept scalar-only so every Delta table the Warehouse reads is complex-free.
#
# Writes Delta tables to OneLake Tables/: silver_chunk, silver_chunk_compatibility,
# silver_chunk_keyword, int_ad_perf_unioned (v1.5).
# RUNTIME-UNVERIFIED against real Fabric (SESSION_LOG 2026-06-24): PySpark API + abfss paths
# correct by construction, not yet run on a real Spark pool.
from __future__ import annotations

import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

spark = SparkSession.builder.getOrCreate()  # Fabric-injected session

WORKSPACE = os.environ["FABRIC_WORKSPACE"]
LAKEHOUSE = os.environ["FABRIC_LAKEHOUSE"]
CLIENT_ID = os.environ["CLIENT_ID"]  # no default — multi-client misroute guard (matches _sources.yml)
_BASE = f"abfss://{WORKSPACE}@onelake.dfs.fabric.microsoft.com/{LAKEHOUSE}.Lakehouse"


def _files(key: str) -> str:
    return f"{_BASE}/Files/{key}"


# Schema of one Gemini chunk (matches RESPONSE_SCHEMA in notebooks/02_extract_gemini.py).
_CHUNK_SCHEMA = ArrayType(StructType([
    StructField("start_sec", DoubleType()),
    StructField("end_sec", DoubleType()),
    StructField("transcript_segment", StringType()),
    StructField("chunk_theme", StringType()),
    StructField("sentiment", StringType()),
    StructField("standalone_score", IntegerType()),
    StructField("next_compatible_themes", ArrayType(StringType())),
    StructField("keywords", ArrayType(StringType())),
]))


def build_silver_chunk():
    """stg_gemini_raw + int_chunk_cleaned + the two array bridges. Flatten verbatim asset-grain
    Bronze JSON -> one row per semantic chunk. DuckDB `unnest(json_extract(...)) with ordinality`
    -> Spark `from_json` + `posexplode`. chunk_id generated deterministically (asset_id + position)
    so re-parsing the same frozen Bronze row is reproducible (ADR-003)."""
    bronze = spark.read.parquet(_files(f"bronze/{CLIENT_ID}/asset_raw/"))

    envelope_schema = StructType([StructField("chunks", _CHUNK_SCHEMA)])
    exploded = (
        bronze
        .withColumn("chunks", F.from_json(F.col("raw_response"), envelope_schema).getField("chunks"))
        .select("asset_id", F.posexplode("chunks").alias("pos", "chunk"))
        .withColumn("chunk_sequence", F.col("pos") + F.lit(1))  # 1-based, matches DuckDB ordinality
        .withColumn("chunk_id", F.concat_ws("_", F.col("asset_id"),
                                            F.lpad(F.col("chunk_sequence").cast("string"), 3, "0")))
    )

    # silver_chunk — scalar columns only (no arrays; Warehouse-readable). int_chunk_cleaned's
    # filler-removal is a TODO in the source too (passthrough for now).
    silver_chunk = exploded.select(
        "chunk_id", "asset_id", "chunk_sequence",
        F.col("chunk.start_sec").alias("start_sec"),
        F.col("chunk.end_sec").alias("end_sec"),
        F.col("chunk.transcript_segment").alias("transcript_segment"),
        F.col("chunk.chunk_theme").alias("chunk_theme"),
        F.col("chunk.sentiment").alias("sentiment"),
        F.col("chunk.standalone_score").alias("standalone_score"),
    ).orderBy("asset_id", "chunk_sequence")
    silver_chunk.write.format("delta").mode("overwrite").saveAsTable("silver_chunk")

    # Array fan-outs exploded here (were Gold unnest() views in the sibling repo).
    compat = (exploded
              .select("chunk_id", F.explode(F.col("chunk.next_compatible_themes")).alias("compatible_theme")))
    compat.write.format("delta").mode("overwrite").saveAsTable("silver_chunk_compatibility")

    keyword = (exploded
               .select("chunk_id", F.explode(F.col("chunk.keywords")).alias("keyword")))
    keyword.write.format("delta").mode("overwrite").saveAsTable("silver_chunk_keyword")


def build_int_ad_perf_unioned():
    """stg_meta_perf + stg_tiktok_perf + int_ad_perf_unioned (v1.5): conform each platform's
    funnel columns to the canonical schema, then union with a platform tag."""
    cols = ["ad_id", "perf_date", "impressions", "plays_3s", "plays_25", "plays_50",
            "plays_75", "plays_100", "sum_watch_time_sec", "play_count", "link_clicks",
            "results", "spend"]
    raw = spark.read.parquet(_files(f"bronze/{CLIENT_ID}/ad_performance_raw/"))

    meta = raw.filter(F.col("platform_native") == "meta").select(*cols).withColumn("platform_name", F.lit("meta"))
    tiktok = raw.filter(F.col("platform_native") == "tiktok").select(*cols).withColumn("platform_name", F.lit("tiktok"))

    unioned = meta.unionByName(tiktok)
    unioned.write.format("delta").mode("overwrite").saveAsTable("int_ad_perf_unioned")


if __name__ == "__main__":
    build_silver_chunk()
    # build_int_ad_perf_unioned()  # v1.5 — enable once bronze_ad_performance_raw is fed
