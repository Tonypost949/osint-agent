"""
scan_drive.py — Google Drive Scanner for OSINTNeoAi
====================================================
Scans the authenticated user's Google Drive, catalogues every file,
and ingests the metadata into BigQuery for forensic cross-referencing.

Target table: noble-beanbag-497411-m4.national_audits.drive_file_index
"""

import os
import sys
import json
import datetime

sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.cloud import bigquery

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
GCP_PROJECT = os.environ.get("GOOGLE_PROJECT_ID", "noble-beanbag-497411-m4")
BQ_DATASET = "national_audits"
BQ_TABLE = "drive_file_index"
FULL_TABLE_ID = f"{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = os.path.join(SCRIPT_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token.json")

# Google Drive API scopes — read-only
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Fields to pull for each file
FILE_FIELDS = (
    "id, name, mimeType, size, createdTime, modifiedTime, "
    "owners, sharingUser, shared, webViewLink, parents, "
    "trashed, starred, description"
)

# ---------------------------------------------------------------------------
# AUTH — Custom OAuth Desktop Flow
# ---------------------------------------------------------------------------
def get_drive_service():
    """
    Build a Drive v3 service using a custom OAuth 2.0 Desktop client.
    Tokens are cached in token.json for reuse across runs.
    """
    creds = None

    # Load cached token if it exists
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid creds, run the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[AUTH] Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("[AUTH] Launching OAuth consent flow in browser...")
            print(f"[AUTH] Using client: {CLIENT_SECRET_FILE}")
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Cache the token for future runs
        with open(TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())
        print("[AUTH] Token saved for future use.\n")

    service = build("drive", "v3", credentials=creds)
    return service


# ---------------------------------------------------------------------------
# SCAN
# ---------------------------------------------------------------------------
def scan_drive(service, page_size=200):
    """
    Iterates through ALL files the authenticated user can see in Drive.
    Returns a list of dicts with file metadata.
    """
    all_files = []
    page_token = None
    page_num = 0

    print("[DRIVE SCAN] Starting full Google Drive enumeration...")

    while True:
        page_num += 1
        results = (
            service.files()
            .list(
                pageSize=page_size,
                fields=f"nextPageToken, files({FILE_FIELDS})",
                pageToken=page_token,
                orderBy="modifiedTime desc",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )

        files = results.get("files", [])
        all_files.extend(files)
        print(f"  Page {page_num}: fetched {len(files)} files (total: {len(all_files)})")

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    print(f"[DRIVE SCAN] Complete. {len(all_files)} files catalogued.\n")
    return all_files


# ---------------------------------------------------------------------------
# TRANSFORM
# ---------------------------------------------------------------------------
def transform_for_bq(raw_files):
    """
    Converts raw Drive API responses into BigQuery-friendly rows.
    """
    rows = []
    scan_ts = datetime.datetime.utcnow().isoformat() + "Z"

    for f in raw_files:
        owners = f.get("owners", [])
        owner_emails = [o.get("emailAddress", "") for o in owners]
        owner_names = [o.get("displayName", "") for o in owners]

        sharing_user = f.get("sharingUser", {})

        row = {
            "file_id": f.get("id"),
            "file_name": f.get("name"),
            "mime_type": f.get("mimeType"),
            "size_bytes": int(f["size"]) if f.get("size") else None,
            "created_time": f.get("createdTime"),
            "modified_time": f.get("modifiedTime"),
            "owner_emails": owner_emails,
            "owner_names": owner_names,
            "sharing_user_email": sharing_user.get("emailAddress"),
            "sharing_user_name": sharing_user.get("displayName"),
            "is_shared": f.get("shared", False),
            "web_view_link": f.get("webViewLink"),
            "parent_folder_ids": f.get("parents", []),
            "is_trashed": f.get("trashed", False),
            "is_starred": f.get("starred", False),
            "description": f.get("description"),
            "scan_timestamp": scan_ts,
        }
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# BIGQUERY INGEST
# ---------------------------------------------------------------------------
BQ_SCHEMA = [
    bigquery.SchemaField("file_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("file_name", "STRING"),
    bigquery.SchemaField("mime_type", "STRING"),
    bigquery.SchemaField("size_bytes", "INTEGER"),
    bigquery.SchemaField("created_time", "TIMESTAMP"),
    bigquery.SchemaField("modified_time", "TIMESTAMP"),
    bigquery.SchemaField("owner_emails", "STRING", mode="REPEATED"),
    bigquery.SchemaField("owner_names", "STRING", mode="REPEATED"),
    bigquery.SchemaField("sharing_user_email", "STRING"),
    bigquery.SchemaField("sharing_user_name", "STRING"),
    bigquery.SchemaField("is_shared", "BOOLEAN"),
    bigquery.SchemaField("web_view_link", "STRING"),
    bigquery.SchemaField("parent_folder_ids", "STRING", mode="REPEATED"),
    bigquery.SchemaField("is_trashed", "BOOLEAN"),
    bigquery.SchemaField("is_starred", "BOOLEAN"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("scan_timestamp", "TIMESTAMP"),
]


def ensure_table(bq_client):
    """Create the drive_file_index table if it doesn't exist."""
    table_ref = bigquery.Table(FULL_TABLE_ID, schema=BQ_SCHEMA)
    table_ref.description = "Google Drive file index — OSINTNeoAi forensic scan"

    try:
        bq_client.get_table(FULL_TABLE_ID)
        print(f"[BQ] Table {FULL_TABLE_ID} already exists.")
    except Exception:
        table = bq_client.create_table(table_ref)
        print(f"[BQ] Created table {table.full_table_id}")


def ingest_to_bq(rows):
    """Load scanned Drive metadata into BigQuery."""
    bq_client = bigquery.Client(project=GCP_PROJECT)

    ensure_table(bq_client)

    job_config = bigquery.LoadJobConfig(
        schema=BQ_SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,  # Full refresh each scan
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )

    print(f"[BQ] Ingesting {len(rows)} rows into {FULL_TABLE_ID}...")

    load_job = bq_client.load_table_from_json(rows, FULL_TABLE_ID, job_config=job_config)
    load_job.result()  # Wait for completion

    table = bq_client.get_table(FULL_TABLE_ID)
    print(f"[BQ] Done. Table now has {table.num_rows} rows.\n")


# ---------------------------------------------------------------------------
# SUMMARY REPORT
# ---------------------------------------------------------------------------
def print_summary(rows):
    """Print a quick forensic summary of what was found."""
    total = len(rows)
    total_size = sum(r["size_bytes"] or 0 for r in rows)
    shared_count = sum(1 for r in rows if r["is_shared"])
    trashed_count = sum(1 for r in rows if r["is_trashed"])

    # Group by mime type
    mime_counts = {}
    for r in rows:
        mt = r["mime_type"] or "unknown"
        # Simplify mime types
        if "spreadsheet" in mt or "excel" in mt:
            key = "Spreadsheets"
        elif "document" in mt or "word" in mt:
            key = "Documents"
        elif "pdf" in mt:
            key = "PDFs"
        elif "image" in mt:
            key = "Images"
        elif "video" in mt:
            key = "Videos"
        elif "folder" in mt:
            key = "Folders"
        elif "presentation" in mt or "powerpoint" in mt:
            key = "Presentations"
        else:
            key = "Other"
        mime_counts[key] = mime_counts.get(key, 0) + 1

    # Unique owners
    all_owners = set()
    for r in rows:
        for email in r["owner_emails"]:
            if email:
                all_owners.add(email)

    print("=" * 60)
    print("  OSINT DRIVE SCAN — FORENSIC SUMMARY")
    print("=" * 60)
    print(f"  Total files catalogued:  {total:,}")
    print(f"  Total size:              {total_size / (1024*1024):.1f} MB")
    print(f"  Shared files:            {shared_count:,}")
    print(f"  Trashed files:           {trashed_count:,}")
    print(f"  Unique owners:           {len(all_owners)}")
    print()
    print("  FILE TYPE BREAKDOWN:")
    for ftype, count in sorted(mime_counts.items(), key=lambda x: -x[1]):
        print(f"    {ftype:<20} {count:>6,}")
    print()
    if all_owners:
        print("  OWNER ACCOUNTS:")
        for owner in sorted(all_owners):
            print(f"    • {owner}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  OSINTNeoAi GOOGLE DRIVE SCANNER")
    print(f"  Target:  {FULL_TABLE_ID}")
    print("=" * 60 + "\n")

    # 1. Connect to Drive (custom OAuth flow)
    service = get_drive_service()

    # 2. Scan everything
    raw_files = scan_drive(service)

    if not raw_files:
        print("[!] No files found in Drive. Exiting.")
        return

    # 3. Transform
    rows = transform_for_bq(raw_files)

    # 4. Print summary
    print_summary(rows)

    # 5. Ingest into BigQuery
    ingest_to_bq(rows)

    print("[✓] Drive scan complete. Data is now queryable in BigQuery.")
    print(f"    SELECT * FROM `{FULL_TABLE_ID}` ORDER BY modified_time DESC")


if __name__ == "__main__":
    main()
