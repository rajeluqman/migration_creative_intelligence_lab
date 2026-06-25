# Fabric notebook (source .py form) — Drive -> OneLake landing.
# Ported from the sibling repo's scripts/ingest_drive_to_s3.py (boto3/S3 -> OneLake, ADR-008).
# LOGIC UNCHANGED: tenant-scoped content-hash naming, skip-existing (idempotent). Path A of the
# pipeline (architecture/STACK_AND_FLOW.md §2). Pulls every video out of a client's Google Drive
# folder and lands it write-once in the OneLake Lakehouse `Files/`, identified by a tenant-scoped
# content hash: asset_id = SHA-256(client_id ':' content_sha256) where content_sha256 is the raw
# SHA-256 of the video bytes (ADR-006). A re-delivered/near-duplicate video FROM THE SAME CLIENT
# hashes to the same asset_id and is never re-uploaded — the first cost firewall (DRD.md §5.1).
# Two DIFFERENT clients delivering byte-identical footage get DIFFERENT asset_ids (ADR-006).
#
# Auth: a Google service account, with the client's Drive folder shared to its client_email.
# Set GOOGLE_APPLICATION_CREDENTIALS to the service-account JSON path (see .env.example).
#
# Path convention (ADR-006 + ADR-008): landing is client-partitioned —
# Files/landing/<client_id>/video/<asset_id>.<ext> (Bronze likewise,
# Files/bronze/<client_id>/asset_raw/<asset_id>.parquet). client_id is REQUIRED for tenant runs.
#
# parent_asset_id (RAW->EDITED discovery lineage) is never inferred here (STTM.md "Exceptions").
# asset_type is sniffed from the immediate Drive parent-folder name (winning -> EDITED ruling,
# @data-architect 2026-06-22); only the RAW|EDITED enum is settled, not the detection mechanism.
#
# RUNTIME-UNVERIFIED against real Fabric (SESSION_LOG 2026-06-24): OneLake writes go through
# scripts/onelake_io.py (notebookutils.fs) — confirm the API on the first real notebook run.
from __future__ import annotations

import csv
import hashlib
import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import onelake_io  # noqa: E402  (OneLake I/O layer — replaces boto3)
from env_guard import assert_safe  # noqa: E402

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
MANIFEST_PATH = Path(__file__).resolve().parent.parent / "seeds" / "asset_manifest.csv"
MANIFEST_COLUMNS = ["asset_id", "client_id", "content_sha256", "asset_name", "asset_type",
                    "parent_asset_id", "duration_sec", "source_uri", "ingested_at"]


def _drive_client():
    creds_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=DRIVE_SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _list_subfolders(drive, folder_id: str) -> list[dict]:
    """Immediate child folders of folder_id. Paginated."""
    folders, page_token = [], None
    while True:
        resp = (
            drive.files()
            .list(
                q=f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
                pageSize=100,
            )
            .execute()
        )
        folders.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            return folders


def _list_videos_in_folder(drive, folder_id: str) -> list[dict]:
    """Video files directly under folder_id (this folder only). Paginated."""
    files, page_token = [], None
    while True:
        resp = (
            drive.files()
            .list(
                q=f"'{folder_id}' in parents and mimeType contains 'video/' and trashed = false",
                fields="nextPageToken, files(id, name, mimeType, videoMediaMetadata, parents)",
                pageToken=page_token,
                pageSize=100,
            )
            .execute()
        )
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            return files


def _list_videos(drive, folder_id: str) -> list[dict]:
    """Video files under folder_id, recursing into subfolders (the onboarding convention of
    edited_video/winning_video/raw_video category subfolders). Walks the whole tree."""
    videos = list(_list_videos_in_folder(drive, folder_id))
    for sub in _list_subfolders(drive, folder_id):
        videos.extend(_list_videos(drive, sub["id"]))
    return videos


def _infer_asset_type(drive, file_meta: dict) -> str:
    """Pragmatic v1 convention — EDITED if the immediate parent Drive folder name contains
    "edited"/"winning"/"winners" (case-insensitive); else RAW. parent_asset_id never inferred.
    "Winning" collapses into EDITED (a winning ad IS a finished/edited cut; "which one won" is a
    performance signal, OUT of v1 — @data-architect 2026-06-22, Clean-ERD axis-2)."""
    parent_ids = file_meta.get("parents") or []
    for parent_id in parent_ids:
        try:
            parent = drive.files().get(fileId=parent_id, fields="name").execute()
        except Exception:
            continue
        name = parent.get("name", "").lower()
        if "edited" in name or "winning" in name or "winners" in name:
            return "EDITED"
    return "RAW"


def _download_bytes(drive, file_id: str) -> bytes:
    """Stream into memory — no temp files on disk (KB-MB scale)."""
    request = drive.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def _extension(name: str) -> str:
    suffix = Path(name).suffix
    return suffix if suffix else ".mp4"  # fallback; Drive video uploads are near-always .mp4/.mov


def _landing_key(asset_id: str, ext: str, client_id: str) -> str:
    if client_id:
        return f"landing/{client_id}/video/{asset_id}{ext}"
    return f"landing/video/{asset_id}{ext}"  # non-tenant/dev smoke only


def _existing_manifest_ids() -> set[str]:
    if not MANIFEST_PATH.exists():
        return set()
    with MANIFEST_PATH.open(newline="") as f:
        return {row["asset_id"] for row in csv.DictReader(f)}


def _append_manifest_row(row: dict) -> None:
    is_new_file = not MANIFEST_PATH.exists()
    # lineterminator="\n": csv.writer defaults to "\r\n" (RFC 4180); an LF-only header then
    # mismatches and broke the sibling repo's CSV sniffer — keep the LF fix (PROJECT_STATUS bug #1).
    with MANIFEST_PATH.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS, lineterminator="\n")
        if is_new_file:
            writer.writeheader()
        writer.writerow(row)


def sync_drive_to_landing(folder_id: str, client_id: str = "") -> int:
    """Returns the count of NEW videos landed this run (matches the Data Factory pipeline's
    sync_drive_to_landing activity contract). Re-delivered/near-duplicate videos hash to an
    asset_id already in OneLake or the manifest and are skipped — never re-uploaded."""
    assert_safe()
    if not folder_id:
        return 0  # "blank = re-scan existing" — nothing to pull from Drive
    if not client_id:
        raise ValueError(
            "client_id is required (ADR-006 tenant-scoped identity). Set CLIENT_ID and ensure a "
            "matching row exists in seeds/dim_client.csv."
        )

    drive = _drive_client()
    known_ids = _existing_manifest_ids()
    landed = 0
    ingested_at = datetime.now(timezone.utc).isoformat()  # one run = one ingestion event

    for file_meta in tqdm(_list_videos(drive, folder_id), desc="Drive -> OneLake landing"):
        raw_bytes = _download_bytes(drive, file_meta["id"])
        content_sha256 = hashlib.sha256(raw_bytes).hexdigest()                            # raw byte hash
        asset_id = hashlib.sha256(f"{client_id}:{content_sha256}".encode()).hexdigest()   # tenant-scoped (ADR-006)
        ext = _extension(file_meta["name"])
        key = _landing_key(asset_id, ext, client_id)
        source_uri = onelake_io.abfss(key)  # abfss OneLake URI (ADR-008; LINEAGE_CONTRACT R4)

        if not onelake_io.exists(key):
            onelake_io.put_bytes(key, raw_bytes)

        # Skip-existing is client-scoped transitively: asset_id folds in client_id.
        if asset_id not in known_ids:
            duration_ms = (file_meta.get("videoMediaMetadata") or {}).get("durationMillis")
            _append_manifest_row(
                {
                    "asset_id": asset_id,
                    "client_id": client_id,
                    "content_sha256": content_sha256,
                    "asset_name": file_meta["name"],
                    "asset_type": _infer_asset_type(drive, file_meta),
                    "parent_asset_id": "",  # never inferred — see header
                    "duration_sec": int(duration_ms) // 1000 if duration_ms else "",
                    "source_uri": source_uri,
                    "ingested_at": ingested_at,
                }
            )
            known_ids.add(asset_id)
            landed += 1

    return landed


if __name__ == "__main__":
    n = sync_drive_to_landing(
        folder_id=os.environ.get("DRIVE_FOLDER_ID", ""),
        client_id=os.environ.get("CLIENT_ID", ""),
    )
    print(f"landed {n} new asset(s)")
