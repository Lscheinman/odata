from __future__ import annotations

import os
import time
import uvicorn
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Header
from pydantic import BaseModel, Field

from session import ODataAuth, ODataConfig, SAPODataSession, ODataUpstreamError
from service import ODataService


# -----------------------------------------------------------------------------
# Configuration (env-driven)
# -----------------------------------------------------------------------------

S4_BASE_URL = os.environ.get("S4_BASE_URL", "").rstrip("/") + "/"
S4_USER = os.environ.get("S4_USER", "")
S4_PASS = os.environ.get("S4_PASS", "")
S4_BEARER = os.environ.get("S4_BEARER_TOKEN", "")
DEFAULT_SAP_CLIENT = os.environ.get("S4_SAP_CLIENT")  # optional
VERIFY_TLS = os.environ.get("S4_VERIFY_TLS", "true").lower() != "false"

# FastAPI protection
API_KEY = os.environ.get("ODATA_API_KEY", "")  # set this
# Comma-separated allowlist of service technical names (e.g. API_MAINTENANCEORDER_SRV,API_MATERIAL_DOCUMENT_SRV)
ALLOWED_SERVICES = {
    s.strip()
    for s in (os.environ.get("ODATA_ALLOWED_SERVICES", "")).split(",")
    if s.strip()
}
# Hard caps
MAX_TOP = int(os.environ.get("ODATA_MAX_TOP", "500"))
MAX_PAGES = int(os.environ.get("ODATA_MAX_PAGES", "10"))
META_CACHE_TTL_SEC = int(os.environ.get("ODATA_META_TTL", "900"))


if not S4_BASE_URL:
    # Fail early: misconfigured deployment should be obvious
    raise RuntimeError("Missing S4_BASE_URL and/or credentials (S4_USER/S4_PASS or S4_BEARER_TOKEN).")

if not API_KEY:
    raise RuntimeError("Missing ODATA_API_KEY env var. Do not run this without an API key.")


# -----------------------------------------------------------------------------
# Simple metadata cache (per service) to avoid hitting $metadata constantly
# -----------------------------------------------------------------------------

_meta_cache: Dict[str, Dict[str, Any]] = {}
# structure:
# _meta_cache[service] = {"ts": epoch, "entity_sets": [...], "fields": {entity_set:[...]}}
# very simple on purpose (boring correctness)


def _build_session() -> SAPODataSession:
    if S4_BEARER:
        auth = ODataAuth("bearer", S4_BEARER)
    else:
        auth = ODataAuth("basic", (S4_USER, S4_PASS))

    cfg = ODataConfig(
        base_url=S4_BASE_URL,
        auth=auth,
        default_sap_client=DEFAULT_SAP_CLIENT,
        verify=VERIFY_TLS,
        timeout=float(os.environ.get("ODATA_TIMEOUT", "60")),
        retries=int(os.environ.get("ODATA_RETRIES", "3")),
        backoff=float(os.environ.get("ODATA_BACKOFF", "0.5")),
    )
    return SAPODataSession(cfg)


def require_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def enforce_service_allowlist(service: str) -> None:
    # If allowlist is empty -> block by default (safer)
    if not ALLOWED_SERVICES:
        raise HTTPException(status_code=403, detail="No services are allowed (ODATA_ALLOWED_SERVICES is empty).")

    # Normalize some common forms: allow passing "SAP/XYZ" etc? keep strict.
    svc = service.strip().strip("/")
    # Allow both "X;v=2" and "X" if allowlisted as "X" (optional)
    base = svc.split(";v=")[0]
    if svc not in ALLOWED_SERVICES and base not in ALLOWED_SERVICES:
        raise HTTPException(status_code=403, detail=f"Service not allowed: {service}")


# -----------------------------------------------------------------------------
# Request models
# -----------------------------------------------------------------------------

class QueryRequest(BaseModel):
    service: str = Field(..., description="Technical service name, e.g. API_MAINTENANCEORDER_SRV or IWFND/CATALOGSERVICE;v=2")
    entity_set: str = Field(..., description="Entity set name, e.g. A_MaintenanceOrder")
    sap_client: Optional[str] = Field(None, description="Overrides default sap-client")

    # OData options (pass as strings; this endpoint does not parse/validate filter grammar)
    select: Optional[List[str]] = Field(None, description="Fields for $select")
    filter: Optional[str] = Field(None, description="Raw $filter expression")
    orderby: Optional[str] = Field(None, description="Raw $orderby")
    expand: Optional[str] = Field(None, description="Raw $expand")

    top: Optional[int] = Field(100, description="Top rows per request")
    skip: Optional[int] = Field(None, description="$skip")
    max_pages: Optional[int] = Field(1, description="Max pages to follow (paging)")

    validate_fields: bool = Field(True, description="Validate $select fields against $metadata (drops unknown)")
    extra_params: Optional[Dict[str, str]] = Field(None, description="Any additional OData params (e.g. $count=true)")


class QueryResponse(BaseModel):
    service: str
    entity_set: str
    count: int
    items: List[Dict[str, Any]]


app = FastAPI(title="Generic SAP OData Gateway", version="1.0.0")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}


@app.get("/services", dependencies=[Depends(require_api_key)])
def list_allowed_services() -> Dict[str, Any]:
    # You can replace this with a real Gateway catalog discovery later.
    return {"allowed_services": sorted(ALLOWED_SERVICES)}


@app.get("/discover/services")
def discover_services(sap_client: Optional[str] = None) -> Dict[str, Any]:
    """
    Try SAP Gateway catalog under common base paths.
    Some systems expose it at /sap/opu/odata/IWFND/... (no /sap after odata),
    while application services are often under /sap/opu/odata/sap/...
    """
    roots_to_try = [
        "IWFND/CATALOGSERVICE;v=2",        # expects base_url like .../sap/opu/odata/
        "IWFND/CATALOGSERVICE",            # sometimes no ;v=2
    ]

    # If your configured base_url ends with /sap/opu/odata/sap/, also try sibling /sap/opu/odata/
    # (We do this without hardcoding secrets: just rewrite the base at runtime.)
    candidates = []
    candidates.append(("configured", None))  # use current base_url
    if S4_BASE_URL.rstrip("/").endswith("/sap/opu/odata/sap"):
        candidates.append(("sibling_no_sap", S4_BASE_URL.replace("/sap/opu/odata/sap/", "/sap/opu/odata/")))

    last_error = None
    for label, alt_base in candidates:
        with _build_session() as sess:
            if alt_base:
                sess.base = alt_base.rstrip("/") + "/"  # override base for this attempt
            for svc in roots_to_try:
                try:
                    cat = ODataService(sess, svc, default_sap_client=sap_client or DEFAULT_SAP_CLIENT)
                    rows = cat.read("ServiceCollection", **{"$format": "json"})
                    services = [{
                        "TechnicalServiceName": r.get("TechnicalServiceName") or r.get("ServiceName"),
                        "TechnicalServiceVersion": r.get("TechnicalServiceVersion") or r.get("ServiceVersion"),
                        "ExternalServiceName": r.get("ExternalServiceName"),
                        "ExternalServiceVersion": r.get("ExternalServiceVersion"),
                        "ServiceUrl": r.get("ServiceUrl"),
                    } for r in rows]
                    return {"root": label, "base_url_used": sess.base, "count": len(services), "services": services}
                except Exception as e:
                    last_error = str(e)

    raise HTTPException(status_code=502, detail={"message": "No Gateway catalog found on tried roots.", "last_error": last_error})


@app.get("/discover/entity-sets")
def discover_entity_sets(service: str, sap_client: Optional[str] = None) -> Dict[str, Any]:
    """
    Lists entity sets inside a service using $metadata.
    Works even if catalog is blocked.
    """
    try:
        with _build_session() as sess:
            s = ODataService(sess, service, default_sap_client=sap_client or DEFAULT_SAP_CLIENT)
            return {"service": service, "entity_sets": s.list_entity_sets()}
    except ODataUpstreamError as e:
        raise HTTPException(status_code=502, detail={"upstream_status": e.status, "url": e.url, "error": str(e)})


@app.get("/discover/fields")
def discover_fields(service: str, entity_set: str, sap_client: Optional[str] = None) -> Dict[str, Any]:
    """
    Lists properties/fields for an entity set using $metadata.
    """
    try:
        with _build_session() as sess:
            s = ODataService(sess, service, default_sap_client=sap_client or DEFAULT_SAP_CLIENT)
            return {"service": service, "entity_set": entity_set, "fields": s.list_fields(entity_set)}
    except ODataUpstreamError as e:
        raise HTTPException(status_code=502, detail={"upstream_status": e.status, "url": e.url, "error": str(e)})


@app.get("/metadata/entity-sets", dependencies=[Depends(require_api_key)])
def list_entity_sets(service: str = Query(...)) -> Dict[str, Any]:
    enforce_service_allowlist(service)
    now = time.time()

    cached = _meta_cache.get(service)
    if cached and (now - cached["ts"]) < META_CACHE_TTL_SEC:
        return {"service": service, "entity_sets": cached["entity_sets"], "cached": True}

    with _build_session() as sess:
        s = ODataService(sess, service, default_sap_client=DEFAULT_SAP_CLIENT)
        es = s.list_entity_sets()

        # cache only entity set list (cheap)
        _meta_cache[service] = {"ts": now, "entity_sets": es, "fields": {}}
        return {"service": service, "entity_sets": es, "cached": False}


@app.get("/metadata/fields", dependencies=[Depends(require_api_key)])
def list_fields(service: str = Query(...), entity_set: str = Query(...)) -> Dict[str, Any]:
    enforce_service_allowlist(service)
    now = time.time()

    cached = _meta_cache.get(service)
    if not cached or (now - cached["ts"]) >= META_CACHE_TTL_SEC:
        cached = {"ts": now, "entity_sets": [], "fields": {}}
        _meta_cache[service] = cached

    fields_map = cached["fields"]
    if entity_set in fields_map:
        return {"service": service, "entity_set": entity_set, "fields": fields_map[entity_set], "cached": True}

    with _build_session() as sess:
        s = ODataService(sess, service, default_sap_client=DEFAULT_SAP_CLIENT)
        fields = s.list_fields(entity_set)
        fields_map[entity_set] = fields
        cached["ts"] = now
        return {"service": service, "entity_set": entity_set, "fields": fields, "cached": False}


@app.post("/query", response_model=QueryResponse, dependencies=[Depends(require_api_key)])
def query_any(req: QueryRequest) -> QueryResponse:
    enforce_service_allowlist(req.service)

    # Caps (boring but necessary)
    top = min(int(req.top or 0), MAX_TOP) if req.top is not None else MAX_TOP
    max_pages = min(int(req.max_pages or 1), MAX_PAGES)

    try:
        with _build_session() as sess:
            s = ODataService(sess, req.service, default_sap_client=req.sap_client or DEFAULT_SAP_CLIENT)

            items = s.query(
                req.entity_set,
                fields=req.select,
                filter_expr=req.filter,
                orderby=req.orderby,
                top=top,
                skip=req.skip,
                expand=req.expand,
                sap_client=req.sap_client,
                max_pages=max_pages,
                validate_fields=req.validate_fields,
                extra_params=req.extra_params,
            )

            return QueryResponse(
                service=req.service,
                entity_set=req.entity_set,
                count=len(items),
                items=items,
            )

    except ODataUpstreamError as e:
        # preserve useful upstream debugging without leaking credentials
        raise HTTPException(
            status_code=502,
            detail={"upstream_status": e.status, "message": str(e), "url": e.url},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5050,
        reload=True,          # auto-reload on code changes (safe for debug)
        log_level="debug",
    )
