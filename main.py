from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from typing import List, Optional
import logging
import os
import uuid
import json
from datetime import datetime, timezone

# Existing logic imports
from config import COHERE_API_KEY
from pdf_extractor import extract_and_clean
from signal_extractor import extract_signals_with_ai, fallback_extract
from scorer import calculate_priority_score, get_tag

# Azure Table Storage imports
from azure.data.tables import TableServiceClient

logger = logging.getLogger(__name__)

# =========================
# CONFIG & AZURE INIT
# =========================
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
TABLE_NAME = "CasePriorityMetadata"

app = FastAPI(
    title="Case Priority Tagger API",
    description="API for processing and prioritizing case PDFs with Azure Storage",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Replicating Table Client initialization from main.py
try:
    table_service_client = TableServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    table_client = table_service_client.get_table_client(TABLE_NAME)
    # Ensure table exists
    try:
        table_service_client.create_table_if_not_exists(TABLE_NAME)
    except Exception:
        pass
except Exception as e:
    logger.error(f"Azure Table setup error: {e}")

# =========================
# HELPERS
# =========================

def save_case_to_table(case_data: dict, file_id: str):
    """Save prioritized case data to Azure Table Storage"""
    try:
        entity = {
            "PartitionKey": "prioritized_cases",
            "RowKey": file_id,
            "filename": case_data["filename"],
            "title": case_data["title"],
            "score": case_data["score"],
            "tag": case_data["tag"],
            # Convert dicts to JSON strings as per main.py logic
            "signals": json.dumps(case_data["signals"]),
            "breakdown": json.dumps(case_data["breakdown"]),
            "upload_date": datetime.now(timezone.utc).isoformat(),
        }
        table_client.upsert_entity(entity)
    except Exception as e:
        logger.error(f"Failed to save {file_id} to Azure: {e}")

# =========================
# ROUTES
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/process")
async def process_cases(files: List[UploadFile] = File(...)):
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    if len(files) > 10:
        raise HTTPException(status_code=413, detail="Maximum 10 files allowed.")

    results = []
    errors = []

    for idx, f in enumerate(files):
        try:
            if not f.filename or not f.filename.lower().endswith(".pdf"):
                errors.append(f"File {idx + 1}: Invalid file type")
                continue

            pdf_bytes = await f.read()
            text = extract_and_clean(pdf_bytes)

            if not text or len(text.strip()) < 50:
                errors.append(f"File {idx + 1}: Insufficient text")
                continue

            # Signal extraction and Scoring
            try:
                signals = extract_signals_with_ai(text)
            except:
                signals = fallback_extract(text)

            score, breakdown = calculate_priority_score(signals)
            tag = get_tag(score)

            file_id = str(uuid.uuid4())
            title = signals.get("case_title") or f.filename.replace(".pdf", "")

            case_result = {
                "id": file_id,
                "filename": f.filename,
                "title": title,
                "signals": signals,
                "score": score,
                "tag": tag,
                "breakdown": breakdown,
            }

            # Replicate main.py persistence logic
            save_case_to_table(case_result, file_id)
            results.append(case_result)

        except Exception as e:
            errors.append(f"File {idx + 1}: {str(e)}")

    results.sort(key=lambda x: x["score"], reverse=True)

    return JSONResponse(
        status_code=200,
        content={
            "success": len(results) > 0,
            "cases": results,
            "total_processed": len(results),
            "errors": errors if errors else None,
        }
    )

@app.get("/cases")
def list_cases():
    """Retrieve history from Azure Table"""
    try:
        entities = table_client.query_entities(query_filter="PartitionKey eq 'prioritized_cases'")
        cases = []
        for e in entities:
            cases.append({
                "id": e["RowKey"],
                "filename": e["filename"],
                "title": e["title"],
                "score": e["score"],
                "tag": e["tag"],
                "signals": json.loads(e["signals"]),
                "breakdown": json.loads(e["breakdown"]),
                "upload_date": e.get("upload_date")
            })
        cases.sort(key=lambda x: x["score"], reverse=True)
        return cases
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/cases/{file_id}")
def delete_case(file_id: str):
    """Delete from Azure Table"""
    try:
        table_client.delete_entity(partition_key="prioritized_cases", row_key=file_id)
        return {"message": "Deleted successfully", "file_id": file_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema: return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    if "/process" in openapi_schema["paths"]:
        openapi_schema["paths"]["/process"]["post"]["requestBody"] = {
            "content": {"multipart/form-data": {"schema": {"type": "object", "properties": {"files": {"type": "array", "items": {"type": "string", "format": "binary"}}}, "required": ["files"]}}}}
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)