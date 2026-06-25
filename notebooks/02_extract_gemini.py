# Fabric notebook (source .py form) — OneLake video -> Gemini (Flash, responseSchema) ->
# bronze_asset_raw (verbatim JSON). Ported from the sibling repo's scripts/run_gemini_extract.py
# (boto3/S3 + duckdb COPY -> OneLake via onelake_io, ADR-008). GEMINI LOGIC UNCHANGED.
#
# Path A's extraction step (STACK_AND_FLOW.md §2). One Gemini call per asset, structured output,
# written as Bronze parquet — ONE ROW PER ASSET, raw_response = the verbatim Gemini JSON
# envelope, completely untouched. The explosion into one row per chunk happens downstream in the
# Silver notebook (notebooks/03_silver_transform.py), per ADR-003 + @data-architect's ruling.
# Idempotent: re-running an already-extracted asset_id is a no-op (cost firewall #2).
#
# SDK: google-genai (the current SDK; google-generativeai is fully EOL).
#
# Bronze grain — @data-architect ruling (2026-06-22, VETOED chunk-grain-at-extraction as a
# re-litigation of ADR-003's already-rejected "chunk in the Python extraction step"). Bronze is
# asset-grain; the Silver notebook does the unnest/explode.
#
# Telemetry (tokens/cost/timing) logged per-run to
# Files/bronze/<client_id>/extraction_run_log/<asset_id>_<run_id>.json — append-only. api_cost
# left null on purpose (tokens_in/out are ground truth; priced downstream, never hardcoded).
#
# RUNTIME-UNVERIFIED against real Fabric (SESSION_LOG 2026-06-24): OneLake I/O via onelake_io.
from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import onelake_io  # noqa: E402  (OneLake I/O layer — replaces boto3 + duckdb COPY)
from env_guard import assert_safe  # noqa: E402

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "seeds" / "asset_manifest.csv"

# Must match great_expectations/expectations/silver_chunk.json's value_set exactly.
SENTIMENT_ENUM = ["energetic", "frustrated", "aspirational", "neutral", "urgent", "calm"]

EXTRACTION_PROMPT = """Watch this advertising video and segment it into semantic chunks —
meaning-bounded marketing beats (e.g. Hook, Problem, Solution, Social Proof, CTA), NOT
fixed-duration slices. Cut chunk boundaries where the message/intent changes, not on a
timer. For each chunk, return:
- start_sec / end_sec: the chunk's boundaries in the video, in seconds.
- transcript_segment: the spoken dialogue or voiceover for this chunk, verbatim.
- chunk_theme: what kind of beat this is (e.g. Hook, Problem, Solution, Social Proof, CTA).
- sentiment: the emotional tone — choose exactly one from this fixed set: """ + ", ".join(SENTIMENT_ENUM) + """.
- standalone_score: 1-5 — how safe is this chunk to reuse on its own, outside this ad
  (1 = makes no sense without context, 5 = a complete message by itself).
- next_compatible_themes: theme names that could validly follow this chunk in a DIFFERENT
  ad without breaking the message (mix-and-match compatibility).
- keywords: notable terms/product names/claims mentioned in this chunk.
If the video has no discernible ad content, return an empty chunks list — do not force
chunks onto unrelated footage."""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "chunks": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "start_sec": {"type": "NUMBER"},
                    "end_sec": {"type": "NUMBER"},
                    "transcript_segment": {"type": "STRING"},
                    "chunk_theme": {"type": "STRING"},
                    "sentiment": {"type": "STRING", "enum": SENTIMENT_ENUM},
                    "standalone_score": {"type": "INTEGER"},
                    "next_compatible_themes": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["start_sec", "end_sec", "transcript_segment", "chunk_theme",
                             "sentiment", "standalone_score"],
            },
        }
    },
    "required": ["chunks"],
}

_MIME_BY_EXT = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".avi": "video/x-msvideo"}


def _bronze_key(asset_id: str, client_id: str, suffix: str = "asset_raw", ext: str = "parquet") -> str:
    if client_id:
        return f"bronze/{client_id}/{suffix}/{asset_id}.{ext}"
    return f"bronze/{suffix}/{asset_id}.{ext}"


def _lookup_manifest_row(asset_id: str) -> dict | None:
    if not MANIFEST_PATH.exists():
        return None
    with MANIFEST_PATH.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["asset_id"] == asset_id:
                return row
    return None


def _relative_key(abfss_uri: str) -> str:
    """abfss://...Lakehouse/Files/<key> -> <key> (for the OneLake I/O helpers)."""
    marker = ".Lakehouse/Files/"
    return abfss_uri.split(marker, 1)[1] if marker in abfss_uri else abfss_uri


def _upload_and_wait_active(client, video_bytes: bytes, mime_type: str,
                            display_name: str, timeout_sec: int = 120, poll_sec: int = 3):
    uploaded = client.files.upload(
        file=io.BytesIO(video_bytes),
        config=types.UploadFileConfig(mime_type=mime_type, display_name=display_name),
    )
    deadline = time.monotonic() + timeout_sec
    while uploaded.state == types.FileState.PROCESSING:
        if time.monotonic() > deadline:
            raise TimeoutError(f"Gemini file processing timed out for asset {display_name}")
        time.sleep(poll_sec)
        uploaded = client.files.get(name=uploaded.name)
    if uploaded.state == types.FileState.FAILED:
        raise RuntimeError(f"Gemini file processing failed for asset {display_name}: {uploaded.error}")
    return uploaded


def _log_extraction_run(client_id: str, asset_id: str, **fields) -> None:
    run_id = str(uuid.uuid4())
    key = _bronze_key(asset_id, client_id, suffix="extraction_run_log", ext=f"{run_id}.json")
    onelake_io.put_text(key, json.dumps({"run_id": run_id, "asset_id": asset_id, **fields}))


def extract_chunks(asset_id: str, client_id: str = "") -> str:
    """Matches the Data Factory pipeline's extract_chunks activity contract. Idempotent — if
    Bronze already has this asset_id, returns immediately with zero Gemini calls (firewall #2)."""
    assert_safe()
    bronze_key = _bronze_key(asset_id, client_id)

    if onelake_io.exists(bronze_key):
        return asset_id  # already extracted — no-op, no API spend

    manifest_row = _lookup_manifest_row(asset_id)
    if not manifest_row:
        raise ValueError(f"asset_id {asset_id!r} not found in {MANIFEST_PATH} — run notebook 01 first")
    content_sha256 = manifest_row["content_sha256"]  # raw byte hash, distinct from asset_id (ADR-006)
    landing_key = _relative_key(manifest_row["source_uri"])
    ext = Path(landing_key).suffix or ".mp4"
    video_bytes = onelake_io.get_bytes(landing_key)

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    prompt_version = os.environ.get("PROMPT_VERSION", "v1")
    gclient = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    started = time.monotonic()
    uploaded = _upload_and_wait_active(gclient, video_bytes, _MIME_BY_EXT.get(ext.lower(), "video/mp4"), asset_id)
    try:
        response = gclient.models.generate_content(
            model=model_name,
            contents=[uploaded, EXTRACTION_PROMPT],
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RESPONSE_SCHEMA),
        )
    finally:
        gclient.files.delete(name=uploaded.name)  # don't leave video on Gemini's file store
    processing_time_sec = round(time.monotonic() - started, 2)

    # Asset-grain Bronze (@data-architect VETO, 2026-06-22): raw_response is response.text
    # UNTOUCHED — the verbatim envelope. chunk_count satisfies the bronze_asset_raw GE gate.
    chunk_count = len(json.loads(response.text).get("chunks", []))
    load_ts = datetime.now(timezone.utc).isoformat()
    rows = [{
        "asset_id": asset_id,
        "raw_response": response.text,
        "model_version": model_name,
        "prompt_version": prompt_version,
        "content_sha256": content_sha256,
        "chunk_count": chunk_count,  # great_expectations/expectations/bronze_asset_raw.json CRITICAL gate
        "load_ts": load_ts,
    }]

    onelake_io.write_parquet(bronze_key, rows)

    usage = response.usage_metadata
    _log_extraction_run(
        client_id, asset_id,
        model_version=model_name, prompt_version=prompt_version,
        tokens_in=usage.prompt_token_count if usage else None,
        tokens_out=usage.candidates_token_count if usage else None,
        api_cost=None,  # priced downstream, never hardcoded
        processing_time_sec=processing_time_sec, retry_count=0,
        extraction_confidence=None,
        load_ts=load_ts,
    )
    return asset_id


if __name__ == "__main__":
    aid = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DEMO_ASSET_ID", "")
    if not aid:
        sys.exit("usage: 02_extract_gemini.py <asset_id>  (or set DEMO_ASSET_ID)")
    print(extract_chunks(aid, client_id=os.environ.get("CLIENT_ID", "")))
