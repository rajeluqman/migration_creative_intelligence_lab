"""OneLake I/O layer (ADR-008) — the ecosystem replacement for the sibling repo's inline
`boto3` S3 calls. Centralizes every OneLake `Files/` read/write/list/delete so the ingest,
extract, and TTL runners stay focused on logic, not storage plumbing (the same role
`boto3.client("s3")` played in the original).

⚠️ RUNTIME-UNVERIFIED against a real Fabric workspace (SESSION_LOG 2026-06-24): these wrap the
Fabric `notebookutils.fs` API + Spark, which only exist inside the Fabric runtime. Statically
valid (py_compile + ruff clean) but the exact `notebookutils.fs` signatures must be confirmed
on the first real notebook run. Identity/path GRAMMAR follows ADR-008 + LINEAGE_CONTRACT.md.

Path grammar (ADR-008, replaces s3://<bucket>/...):
  abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/Files/<key>
"""
from __future__ import annotations

import os


def _ws_lh() -> tuple[str, str]:
    return os.environ["FABRIC_WORKSPACE"], os.environ["FABRIC_LAKEHOUSE"]


def abfss(key: str) -> str:
    """Build the canonical abfss OneLake Files URI for a relative key (e.g. 'landing/<c>/video/x.mp4')."""
    workspace, lakehouse = _ws_lh()
    return (
        f"abfss://{workspace}@onelake.dfs.fabric.microsoft.com/"
        f"{lakehouse}.Lakehouse/Files/{key}"
    )


def _fs():
    """The Fabric-injected filesystem util (notebookutils.fs). Imported lazily so this module
    imports cleanly outside the Fabric runtime (CI py_compile/ruff)."""
    import notebookutils  # provided by the Fabric runtime; not pip-installable

    return notebookutils.fs


def exists(key: str) -> bool:
    try:
        _fs().ls(abfss(key))
        return True
    except Exception:
        return False


def put_bytes(key: str, data: bytes) -> None:
    """Write raw bytes (e.g. a video) to OneLake Files, write-once. Replaces s3.put_object."""
    _fs().put(abfss(key), data, True)  # (path, content, overwrite)


def get_bytes(key: str) -> bytes:
    """Read raw bytes back from OneLake Files. Replaces s3.get_object(...)['Body'].read()."""
    import notebookutils  # noqa: F401  (handle = notebookutils.fs.head/open per runtime)

    return _fs().head(abfss(key), 1024 * 1024 * 1024)  # whole-file read; KB-MB scale


def put_text(key: str, text: str) -> None:
    _fs().put(abfss(key), text, True)


def list_prefix(prefix: str):
    """Yield (key, last_modified_epoch_ms) under a Files prefix. Replaces the S3 paginator."""
    for entry in _fs().ls(abfss(prefix)):
        # notebookutils FileInfo: .path, .name, .size, .modifyTime (epoch ms)
        yield entry.path, getattr(entry, "modifyTime", 0)


def delete(key: str) -> None:
    _fs().rm(abfss(key), False)  # (path, recurse=False)


def write_parquet(key: str, rows: list[dict]) -> None:
    """Write rows as a Parquet file to OneLake Files via Spark. Replaces the DuckDB COPY ... TO
    s3 pattern. `spark` is the Fabric-injected session."""
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()  # the Fabric runtime provides this session
    spark.createDataFrame(rows).coalesce(1).write.mode("overwrite").parquet(abfss(key))
