from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import bigquery
from google.cloud import storage
from google.oauth2.credentials import Credentials
import os

app = FastAPI(
    title="OSINT Evidence Copilot API",
    description="Connects local Copilots and Open WebUI to the OSINT BigQuery Database and GCS Vault.",
    version="1.0.0"
)

# Load OAuth Credentials (assuming token.json is in the same dir)
TOKEN_PATH = os.path.join(os.path.dirname(__file__), 'token.json')
if not os.path.exists(TOKEN_PATH):
    raise RuntimeError("token.json not found! Please run the scan scripts to authenticate first.")

creds = Credentials.from_authorized_user_file(TOKEN_PATH)
bq_client = bigquery.Client(project="noble-beanbag-497411-m4")
gcs_client = storage.Client(project="noble-beanbag-497411-m4")

class SearchRequest(BaseModel):
    search_term: str
    evidence_type: str = "gmail"  # 'gmail' or 'drive'

class FindingRequest(BaseModel):
    title: str
    description: str
    evidence_links: list[str] = []

class SyncCodeRequest(BaseModel):
    filename: str
    code_content: str
    language: str
    description: str

@app.post("/api/search")
async def search_evidence(request: SearchRequest):
    """Search across the OSINT evidence database."""
    term = request.search_term.replace("'", "\\'")
    
    if request.evidence_type == "gmail":
        query = f"""
            SELECT date, sender, subject, snippet 
            FROM `noble-beanbag-497411-m4.national_audits.gmail_index`
            WHERE LOWER(subject) LIKE LOWER('%{term}%') 
               OR LOWER(snippet) LIKE LOWER('%{term}%')
            LIMIT 20
        """
    else:
        query = f"""
            SELECT name, mimeType, webViewLink, createdTime 
            FROM `noble-beanbag-497411-m4.national_audits.drive_file_index`
            WHERE LOWER(name) LIKE LOWER('%{term}%')
            LIMIT 20
        """

    try:
        query_job = bq_client.query(query)
        results = [dict(row) for row in query_job]
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/finding")
async def record_finding(request: FindingRequest):
    """Write a finding securely into the BigQuery AI Sandbox."""
    # Ensure the sandbox table exists
    table_id = "noble-beanbag-497411-m4.ai_sandbox.findings"
    
    # Normally you'd define a schema and use insert_rows_json, but we'll do a simple insert via SQL
    links = ", ".join(request.evidence_links)
    query = f"""
        INSERT INTO `{table_id}` (title, description, evidence_links, timestamp)
        VALUES (
            '{request.title.replace("'", "\\'")}', 
            '{request.description.replace("'", "\\'")}', 
            '{links.replace("'", "\\'")}', 
            CURRENT_TIMESTAMP()
        )
    """
    try:
        # Check if table exists, create if not
        try:
            bq_client.get_table(table_id)
        except Exception:
            schema = [
                bigquery.SchemaField("title", "STRING"),
                bigquery.SchemaField("description", "STRING"),
                bigquery.SchemaField("evidence_links", "STRING"),
                bigquery.SchemaField("timestamp", "TIMESTAMP"),
            ]
            table = bigquery.Table(table_id, schema=schema)
            bq_client.create_table(table)
            
        bq_client.query(query).result()
        return {"status": "success", "message": "Finding saved to cloud Sandbox."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync_code")
async def sync_code(request: SyncCodeRequest):
    """Save AI generated code locally and upload to GCS."""
    sync_dir = os.path.join(os.path.dirname(__file__), 'ai_sync_vault')
    os.makedirs(sync_dir, exist_ok=True)
    
    local_path = os.path.join(sync_dir, request.filename)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(request.code_content)
        
    try:
        bucket = gcs_client.bucket("osint-ai-evidence-vault-m4")
        blob = bucket.blob(f"ai_generated_code/{request.filename}")
        blob.upload_from_filename(local_path)
        
        # Log to BigQuery
        table_id = "noble-beanbag-497411-m4.ai_sandbox.findings"
        link = f"gs://osint-ai-evidence-vault-m4/ai_generated_code/{request.filename}"
        query = f"""
            INSERT INTO `{table_id}` (title, description, evidence_links, timestamp)
            VALUES (
                'Synced Code: {request.filename.replace("'", "\\\\'")}', 
                '{request.description.replace("'", "\\\\'")}', 
                '{link.replace("'", "\\\\'")}', 
                CURRENT_TIMESTAMP()
            )
        """
        try:
            bq_client.get_table(table_id)
        except Exception:
            schema = [
                bigquery.SchemaField("title", "STRING"),
                bigquery.SchemaField("description", "STRING"),
                bigquery.SchemaField("evidence_links", "STRING"),
                bigquery.SchemaField("timestamp", "TIMESTAMP"),
            ]
            table = bigquery.Table(table_id, schema=schema)
            bq_client.create_table(table)

        bq_client.query(query).result()
        
        return {"status": "success", "message": f"Code synchronized to {link}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GisQueryRequest(BaseModel):
    layer_url: str
    where: str = "1=1"
    out_fields: str = "*"
    return_geometry: bool = True

@app.post("/api/gis/query")
async def query_gis(request: GisQueryRequest):
    """Proxy queries to Huntington Beach ArcGIS REST API."""
    import requests
    query_url = f"{request.layer_url}/query"
    params = {
        "where": request.where,
        "outFields": request.out_fields,
        "returnGeometry": "true" if request.return_geometry else "false",
        "f": "json"
    }
    
    try:
        res = requests.get(query_url, params=params)
        res.raise_for_status()
        data = res.json()
        
        # Log to BigQuery
        table_id = "noble-beanbag-497411-m4.ai_sandbox.findings"
        feature_count = len(data.get("features", []))
        query = f"""
            INSERT INTO `{table_id}` (title, description, evidence_links, timestamp)
            VALUES (
                'GIS Spatial Query Execution', 
                'Queried Huntington Beach GIS: returned {feature_count} features. WHERE: {request.where.replace("'", "\\\\'")}', 
                '{query_url.replace("'", "\\\\'")}', 
                CURRENT_TIMESTAMP()
            )
        """
        try:
            bq_client.get_table(table_id)
            bq_client.query(query).result()
        except Exception:
            pass # Ignore log fail if table doesn't exist
            
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Starts a local server on port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
