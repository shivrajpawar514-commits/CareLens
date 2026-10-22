"""
CareLens FastAPI Application Server.
Provides edge-native clinical visual safety auditing endpoints and static UI dashboard serving.
"""

import os
import base64
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Request, Response, Body, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import ollama

from app.schema.contract import CareLensResponse
from app.protocol_engine.protocols import CLINICAL_PROTOCOLS, get_protocol
from app.inference.edge_engine import EdgeClinicalEngine
from app.audit.logger import global_audit_logger
from app.presets import PRESET_SCENARIOS


app = FastAPI(
    title="CareLens Clinical Safety Auditor",
    version="1.0.0",
    description="Edge-Native Clinical Visual Safety Auditor powered by Gemma 4",
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

engine = EdgeClinicalEngine(gemma_model_name="gemma4:e2b")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")


# --- Static Files & Root Routes ---

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse("<h1>CareLens UI Initializing...</h1>")


@app.get("/styles.css")
async def serve_styles():
    css_file = os.path.join(FRONTEND_DIR, "styles.css")
    if os.path.exists(css_file):
        return FileResponse(css_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="styles.css not found")


@app.get("/app.js")
async def serve_js():
    js_file = os.path.join(FRONTEND_DIR, "app.js")
    if os.path.exists(js_file):
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")


@app.get("/privacy", response_class=HTMLResponse)
async def serve_privacy():
    privacy_file = os.path.join(FRONTEND_DIR, "privacy.html")
    if os.path.exists(privacy_file):
        return FileResponse(privacy_file, media_type="text/html")
    raise HTTPException(status_code=404, detail="privacy.html not found")


@app.get("/terms", response_class=HTMLResponse)
async def serve_terms():
    terms_file = os.path.join(FRONTEND_DIR, "terms.html")
    if os.path.exists(terms_file):
        return FileResponse(terms_file, media_type="text/html")
    raise HTTPException(status_code=404, detail="terms.html not found")


# Mount assets directory for SVG equipment illustrations
if os.path.exists(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


# --- API Endpoints ---

@app.get("/api/health")
async def health_check():
    """Returns runtime readiness and local Gemma 4 model status."""
    gemma_available = False
    available_models = []
    try:
        client = ollama.Client()
        model_list = client.list()
        available_models = [m.model for m in model_list.models]
        gemma_available = any("gemma4" in m for m in available_models)
    except Exception:
        pass

    return {
        "status": "healthy",
        "service": "CareLens Edge-Native Auditor",
        "gemma_model": "gemma4:e2b",
        "gemma_available": gemma_available,
        "available_models": available_models,
        "edge_runtime": "macOS_AppleSilicon_Metal",
        "protocols_loaded": list(CLINICAL_PROTOCOLS.keys()),
    }


@app.get("/api/protocols")
async def list_protocols():
    """Returns all active, versioned clinical reference protocols."""
    return {
        "count": len(CLINICAL_PROTOCOLS),
        "protocols": [p.model_dump() for p in CLINICAL_PROTOCOLS.values()],
    }


@app.get("/api/presets")
async def list_presets():
    """Returns clinical preset scenarios for interactive demonstration and evaluation."""
    return PRESET_SCENARIOS


@app.post("/api/audit")
async def audit_image(
    request: Request,
    response: Response,
    payload: Optional[Dict[str, Any]] = Body(None),
):
    """
    Main visual safety audit endpoint.
    Returns the exact canonical CareLens JSON contract with zero extra keys.
    Telemetry and audit IDs are conveyed via HTTP response headers.
    """
    if not payload or "image" not in payload:
        raise HTTPException(status_code=400, detail="Missing required 'image' base64 field.")

    image_b64 = payload["image"]
    protocol_id = payload.get("protocol_id", "adult_icu_v1.0")
    patient_context = payload.get("patient_context", "adult")
    backend = payload.get("backend", "auto")
    preset_hint = payload.get("preset_hint")

    # Run edge audit
    carelens_response, metadata = engine.audit(
        image_b64=image_b64,
        protocol_id=protocol_id,
        patient_context=patient_context,
        preferred_backend=backend,
        preset_hint=preset_hint,
    )

    # Record tamper-evident audit trail
    resp_dict = carelens_response.model_dump()
    global_audit_logger.record_audit(metadata, resp_dict)

    # Attach audit telemetry to response headers for the web UI
    response.headers["X-CareLens-Audit-Id"] = metadata.get("audit_id", "")
    response.headers["X-CareLens-Latency-Ms"] = str(metadata.get("latency_ms", 0.0))
    response.headers["X-CareLens-Provider"] = metadata.get("provider", "")
    response.headers["X-CareLens-Protocol"] = metadata.get("protocol_id", "")

    return resp_dict


@app.post("/api/audit/upload")
async def audit_image_upload(
    response: Response,
    file: UploadFile = File(...),
    protocol_id: str = Form("adult_icu_v1.0"),
    patient_context: str = Form("adult"),
    backend: str = Form("auto"),
    preset_hint: Optional[str] = Form(None),
):
    """Multipart file upload route for direct camera or file-drop audits."""
    contents = await file.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")

    carelens_response, metadata = engine.audit(
        image_b64=image_b64,
        protocol_id=protocol_id,
        patient_context=patient_context,
        preferred_backend=backend,
        preset_hint=preset_hint,
    )

    resp_dict = carelens_response.model_dump()
    global_audit_logger.record_audit(metadata, resp_dict)

    response.headers["X-CareLens-Audit-Id"] = metadata.get("audit_id", "")
    response.headers["X-CareLens-Latency-Ms"] = str(metadata.get("latency_ms", 0.0))
    response.headers["X-CareLens-Provider"] = metadata.get("provider", "")
    response.headers["X-CareLens-Protocol"] = metadata.get("protocol_id", "")

    return resp_dict


@app.get("/api/audit-log")
async def get_audit_log(limit: int = 50):
    """Returns recent audit logs with clinician verification status."""
    return global_audit_logger.get_recent_records(limit=limit)


@app.post("/api/acknowledge")
async def acknowledge_audit(payload: Dict[str, Any] = Body(...)):
    """Records human clinician verification of an audit finding."""
    audit_id = payload.get("audit_id")
    clinician_id = payload.get("clinician_id", "Attending Clinician")
    action_taken = payload.get("action_taken", "Verified finding and performed clinical assessment.")
    notes = payload.get("notes")

    if not audit_id:
        raise HTTPException(status_code=400, detail="Missing audit_id")

    rec = global_audit_logger.acknowledge_audit(
        audit_id=audit_id,
        clinician_id=clinician_id,
        action_taken=action_taken,
        notes=notes,
    )
    if not rec:
        raise HTTPException(status_code=404, detail=f"Audit record '{audit_id}' not found")

    return {"status": "acknowledged", "record": rec.model_dump()}
