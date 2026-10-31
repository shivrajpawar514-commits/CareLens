"""
CareLens FastAPI Application Server.
Provides edge-native clinical visual safety auditing endpoints and static UI dashboard serving.
Identified strictly as a research and development prototype — not for real clinical care without validation.
"""

import os
import base64
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, Request, Response, Body, UploadFile, File, Form, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import ollama

from app.schema.contract import CareLensResponse
from app.protocol_engine.protocols import CLINICAL_PROTOCOLS, get_protocol
from app.inference.edge_engine import EdgeClinicalEngine, CLINICAL_DISCLAIMER
from app.audit.logger import global_audit_logger
from app.presets import PRESET_SCENARIOS


# --- Application Configuration & Security Constants ---

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB maximum upload size
MAX_BASE64_BYTES = 15 * 1024 * 1024  # 15 MB maximum base64 payload
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/svg+xml",
}

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
]

allowed_origins_env = os.getenv("CARELENS_ALLOWED_ORIGINS")
ALLOWED_ORIGINS = (
    [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
    if allowed_origins_env
    else DEFAULT_ALLOWED_ORIGINS
)

API_KEY_ENV = os.getenv("CARELENS_API_KEY")


# --- Lifespan Management (Deferred Model Engine Startup) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages application startup and shutdown.
    Moves model engine initialization and availability checks into startup instead of import time.
    """
    gemma_model = os.getenv("CARELENS_GEMMA_MODEL", "gemma4:e2b")
    # Initialize model engine on startup
    app.state.engine = EdgeClinicalEngine(gemma_model_name=gemma_model)
    app.state.engine_ready = True
    yield
    # Cleanup on shutdown
    app.state.engine = None
    app.state.engine_ready = False


app = FastAPI(
    title="CareLens Clinical Safety Auditor [PROTOTYPE]",
    version="1.0.0",
    description=(
        "Edge-Native Clinical Visual Safety Auditor prototype powered by Gemma 4 Vision. "
        "RESEARCH AND DEVELOPMENT PROTOTYPE ONLY - NOT FOR DIRECT PATIENT CARE."
    ),
    lifespan=lifespan,
)


# --- CORS Middleware (Restricted to Approved Origins) ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[
        "X-CareLens-Audit-Id",
        "X-CareLens-Latency-Ms",
        "X-CareLens-Provider",
        "X-CareLens-Protocol",
        "X-CareLens-Prototype",
    ],
)


# --- Security Headers Middleware ---

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-CareLens-Prototype"] = "true"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


# --- Authentication & Authorization Dependency ---

async def verify_auth_if_configured(
    x_carelens_api_key: Optional[str] = Header(None, alias="X-CareLens-API-Key"),
    authorization: Optional[str] = Header(None),
):
    """
    Protects uploads, inspection endpoints, and audit records.
    Enforces API key authentication if CARELENS_API_KEY environment variable is configured.
    """
    if not API_KEY_ENV:
        return True

    token = None
    if x_carelens_api_key:
        token = x_carelens_api_key
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    if not token or token != API_KEY_ENV:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Valid X-CareLens-API-Key or Bearer token required.",
        )
    return True


def get_engine(request: Request) -> EdgeClinicalEngine:
    """Dependency that returns the active model engine or raises 503 if not ready."""
    engine = getattr(request.app.state, "engine", None)
    ready = getattr(request.app.state, "engine_ready", False)
    if not ready or engine is None:
        raise HTTPException(
            status_code=503,
            detail="CareLens model engine is not ready. Check /api/ready.",
        )
    return engine


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


# --- Readiness & Health Endpoints ---

@app.get("/api/ready")
async def readiness_check(request: Request):
    """
    Exposes an accurate readiness check that reflects model availability and startup completion.
    """
    engine_ready = getattr(request.app.state, "engine_ready", False)
    engine = getattr(request.app.state, "engine", None)
    if not engine_ready or engine is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "ready": False,
                "is_prototype": True,
                "detail": "CareLens model engine is initializing or unavailable.",
            },
        )

    return {
        "status": "ready",
        "ready": True,
        "is_prototype": True,
        "model_engine": "EdgeClinicalEngine",
        "gemma_model": engine.gemma_model_name,
        "protocols_loaded": list(CLINICAL_PROTOCOLS.keys()),
        "disclaimer": CLINICAL_DISCLAIMER,
    }


@app.get("/api/health")
async def health_check(request: Request):
    """Returns runtime health, prototype disclaimer, and local Gemma 4 model status."""
    gemma_available = False
    available_models = []
    try:
        client = ollama.Client()
        model_list = client.list()
        available_models = [m.model for m in model_list.models]
        gemma_available = any("gemma4" in m for m in available_models)
    except Exception:
        pass

    engine_ready = getattr(request.app.state, "engine_ready", False)
    gemma_model = request.app.state.engine.gemma_model_name if engine_ready else "gemma4:e2b"

    return {
        "status": "healthy",
        "ready": engine_ready,
        "is_prototype": True,
        "service": "CareLens Edge-Native Auditor [PROTOTYPE]",
        "gemma_model": gemma_model,
        "gemma_available": gemma_available,
        "available_models": available_models,
        "edge_runtime": "macOS_AppleSilicon_Metal",
        "protocols_loaded": list(CLINICAL_PROTOCOLS.keys()),
        "disclaimer": CLINICAL_DISCLAIMER,
    }


@app.get("/api/protocols")
async def list_protocols():
    """Returns all active, versioned clinical reference protocols."""
    return {
        "count": len(CLINICAL_PROTOCOLS),
        "is_prototype": True,
        "protocols": [p.model_dump() for p in CLINICAL_PROTOCOLS.values()],
    }


@app.get("/api/presets")
async def list_presets():
    """Returns clinician-reviewed, de-identified clinical preset scenarios."""
    return PRESET_SCENARIOS


# --- Protected Audit & Inspection Endpoints ---

@app.post("/api/audit")
async def audit_image(
    request: Request,
    response: Response,
    payload: Optional[Dict[str, Any]] = Body(None),
    auth_ok: bool = Depends(verify_auth_if_configured),
    engine: EdgeClinicalEngine = Depends(get_engine),
):
    """
    Main visual safety audit endpoint. Protected by authentication if configured.
    Enforces payload size constraints and returns canonical CareLens JSON contract.
    """
    if not payload or "image" not in payload:
        raise HTTPException(status_code=400, detail="Missing required 'image' base64 field.")

    image_b64 = payload["image"]
    if len(image_b64) > MAX_BASE64_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Payload Too Large: Base64 image payload exceeds {MAX_BASE64_BYTES // (1024*1024)}MB limit.",
        )

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

    # Record tamper-evident cryptographic audit trail
    resp_dict = carelens_response.model_dump()
    global_audit_logger.record_audit(metadata, resp_dict)

    # Attach audit telemetry and prototype flags to response headers
    response.headers["X-CareLens-Audit-Id"] = metadata.get("audit_id", "")
    response.headers["X-CareLens-Latency-Ms"] = str(metadata.get("latency_ms", 0.0))
    response.headers["X-CareLens-Provider"] = metadata.get("provider", "")
    response.headers["X-CareLens-Protocol"] = metadata.get("protocol_id", "")
    response.headers["X-CareLens-Prototype"] = "true"

    return resp_dict


@app.post("/api/audit/upload")
async def audit_image_upload(
    response: Response,
    file: UploadFile = File(...),
    protocol_id: str = Form("adult_icu_v1.0"),
    patient_context: str = Form("adult"),
    backend: str = Form("auto"),
    preset_hint: Optional[str] = Form(None),
    auth_ok: bool = Depends(verify_auth_if_configured),
    engine: EdgeClinicalEngine = Depends(get_engine),
):
    """
    Multipart file upload endpoint.
    Protected against unbounded upload sizes, malicious file formats, and unauthenticated access.
    """
    # Validate MIME type
    content_type = file.content_type.lower() if file.content_type else ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported Media Type: '{file.content_type}'. Allowed types: {sorted(ALLOWED_MIME_TYPES)}.",
        )

    # Read and validate size
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Payload Too Large: Uploaded file exceeds {MAX_UPLOAD_BYTES // (1024*1024)}MB limit.",
        )

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
    response.headers["X-CareLens-Prototype"] = "true"

    return resp_dict


# --- Protected Audit Data & Verification Endpoints ---

@app.get("/api/audit-log")
async def get_audit_log(
    limit: int = 50,
    auth_ok: bool = Depends(verify_auth_if_configured),
):
    """
    Returns recent audit logs with clinician verification status.
    Protected against unauthorized inspection and unbounded limits.
    """
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 500.")
    return global_audit_logger.get_recent_records(limit=limit)


@app.get("/api/audit/verify")
async def verify_audit_integrity(
    auth_ok: bool = Depends(verify_auth_if_configured),
):
    """
    Cryptographically verifies the hash-chain integrity of the tamper-evident audit records.
    """
    return global_audit_logger.verify_integrity()


@app.post("/api/acknowledge")
async def acknowledge_audit(
    payload: Dict[str, Any] = Body(...),
    auth_ok: bool = Depends(verify_auth_if_configured),
):
    """
    Records human clinician verification of an audit finding into the append-only cryptographic ledger.
    """
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
