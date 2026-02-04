"""
sap_ds.api.gateway - FastAPI OData Gateway
==========================================

Optional REST API gateway for exposing SAP OData services.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    # Look for .env in current dir or parent dirs
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        # gateway.py is at sap_ds/api/gateway.py, so .env is 3 parents up
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env from: {env_path}")
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Query, Path as PathParam, Header, Depends
from fastapi.middleware.cors import CORSMiddleware

from sap_ds.core.session import ODataAuth, ODataConfig, SAPODataSession, ODataUpstreamError
from sap_ds.odata.service import ODataService
from sap_ds.api.models import (
    QueryRequest,
    QueryResponse,
    ForceElementTreeRequest,
    ForceElementTreeResponse,
    ForceElementGraphRequest,
    ForceElementGraphResponse,
    ForceElementReadinessRequest,
    ForceElementReadinessResponse,
    ForceElementNode,
    EXAMPLE_FE_SERVICE,
    EXAMPLE_FE_ENTITY_SET,
    EXAMPLE_FE_ID,
    EXAMPLE_FE_SELECT,
)


class ODataGateway:
    """
    Configuration and session factory for the API gateway.
    
    Reads configuration from environment variables by default.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sap_client: Optional[str] = None,
        verify_tls: Optional[bool] = None,
        api_key: Optional[str] = None,
        max_top: int = 500,
        max_pages: int = 10,
        meta_cache_ttl: int = 900,
    ):
        # Load from env if not provided
        self.base_url = (base_url or os.environ.get("S4_BASE_URL", "")).rstrip("/") + "/"
        self.user = user or os.environ.get("S4_USER", "")
        self.password = password or os.environ.get("S4_PASS", "")
        self.bearer_token = bearer_token or os.environ.get("S4_BEARER_TOKEN", "")
        self.sap_client = sap_client or os.environ.get("S4_SAP_CLIENT")
        
        if verify_tls is not None:
            self.verify_tls = verify_tls
        else:
            self.verify_tls = os.environ.get("S4_VERIFY_TLS", "true").lower() != "false"
            
        self.api_key = api_key or os.environ.get("ODATA_API_KEY", "")
        self.max_top = max_top
        self.max_pages = max_pages
        self.meta_cache_ttl = meta_cache_ttl
        
        # Metadata cache
        self._meta_cache: Dict[str, Dict[str, Any]] = {}
        
    def validate(self) -> None:
        """Validate configuration. Raises RuntimeError if invalid."""
        if not self.base_url or self.base_url == "/":
            raise RuntimeError("Missing S4_BASE_URL environment variable")
        if not self.bearer_token and not (self.user and self.password):
            raise RuntimeError("Missing S4_USER/S4_PASS or S4_BEARER_TOKEN")
        if not self.api_key:
            raise RuntimeError("Missing ODATA_API_KEY - required for security")
    
    def build_session(self) -> SAPODataSession:
        """Create a new OData session."""
        if self.bearer_token:
            auth = ODataAuth("bearer", self.bearer_token)
        else:
            auth = ODataAuth("basic", (self.user, self.password))
            
        cfg = ODataConfig(
            base_url=self.base_url,
            auth=auth,
            default_sap_client=self.sap_client,
            verify=self.verify_tls,
            timeout=float(os.environ.get("ODATA_TIMEOUT", "60")),
            retries=int(os.environ.get("ODATA_RETRIES", "3")),
            backoff=float(os.environ.get("ODATA_BACKOFF", "0.5")),
        )
        return SAPODataSession(cfg)


# Global gateway instance (lazy init)
_gateway: Optional[ODataGateway] = None


def get_gateway() -> ODataGateway:
    """Get or create the global gateway instance."""
    global _gateway
    if _gateway is None:
        _gateway = ODataGateway()
    return _gateway


def create_app(
    gateway: Optional[ODataGateway] = None,
    validate_on_startup: bool = True,
) -> FastAPI:
    """
    Create the FastAPI application.
    
    Parameters
    ----------
    gateway : ODataGateway, optional
        Custom gateway configuration. If None, reads from environment.
    validate_on_startup : bool
        If True, validate configuration on startup.
        
    Returns
    -------
    FastAPI
        Configured FastAPI application
    """
    global _gateway
    
    if gateway:
        _gateway = gateway
    else:
        _gateway = ODataGateway()
        
    if validate_on_startup:
        try:
            _gateway.validate()
        except RuntimeError:
            # Allow app creation without validation for testing
            pass
    
    app = FastAPI(
        title="SAP Defense & Security OData Gateway",
        description="""
## SAP S/4HANA Defense & Security API Gateway

A REST API gateway for SAP OData services with **built-in Force Element support**.

### Quick Start
All endpoints have sensible defaults - just click **Execute** in Swagger to test!

### Force Element Examples
- **ID:** `50000026`, `50000027`, `50000028`
- **Service:** `DFS_FE_FRCELMNTORG_SRV`
- **Entity Set:** `C_FrcElmntOrgTP`

### Authentication
Include your API key in the `x-api-key` header.
        """,
        version="1.0.0",
        openapi_tags=[
            {
                "name": "Force Elements",
                "description": "SAP D&S Force Element operations - tree, graph, readiness KPIs",
            },
            {
                "name": "Discovery",
                "description": "Discover available services, entity sets, and fields",
            },
            {
                "name": "Generic OData",
                "description": "Generic OData query operations",
            },
        ],
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # -------------------------------------------------------------------------
    # Dependencies
    # -------------------------------------------------------------------------
    
    def require_api_key(x_api_key: str = Header(...)) -> None:
        gw = get_gateway()
        if gw.api_key and x_api_key != gw.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    
    # -------------------------------------------------------------------------
    # Endpoints
    # -------------------------------------------------------------------------
    
    @app.get("/health")
    def health() -> Dict[str, Any]:
        """Health check endpoint."""
        return {"ok": True, "version": "1.0.0"}
    
    @app.get("/discover/services", tags=["Discovery"])
    def discover_services(
        sap_client: Optional[str] = Query(default=None, examples=["600"]),
        _: None = Depends(require_api_key),
    ) -> Dict[str, Any]:
        """
        Discover available OData services via Gateway catalog.
        """
        gw = get_gateway()
        roots_to_try = [
            "IWFND/CATALOGSERVICE;v=2",
            "IWFND/CATALOGSERVICE",
        ]
        
        candidates = [("configured", None)]
        if gw.base_url.rstrip("/").endswith("/sap/opu/odata/sap"):
            sibling = gw.base_url.replace("/sap/opu/odata/sap/", "/sap/opu/odata/")
            candidates.append(("sibling_no_sap", sibling))
        
        last_error = None
        for label, alt_base in candidates:
            with gw.build_session() as sess:
                if alt_base:
                    sess.base = alt_base.rstrip("/") + "/"
                for svc in roots_to_try:
                    try:
                        cat = ODataService(
                            sess, svc,
                            default_sap_client=sap_client or gw.sap_client
                        )
                        rows = cat.read("ServiceCollection", **{"$format": "json"})
                        services = [{
                            "TechnicalServiceName": r.get("TechnicalServiceName") or r.get("ServiceName"),
                            "TechnicalServiceVersion": r.get("TechnicalServiceVersion") or r.get("ServiceVersion"),
                            "ServiceUrl": r.get("ServiceUrl"),
                        } for r in rows]
                        return {
                            "root": label,
                            "base_url_used": sess.base,
                            "count": len(services),
                            "services": services
                        }
                    except Exception as e:
                        last_error = str(e)
        
        raise HTTPException(
            status_code=502,
            detail={"message": "No Gateway catalog found", "last_error": last_error}
        )
    
    @app.get("/discover/entity-sets", tags=["Discovery"])
    def discover_entity_sets(
        service: str = Query(default=EXAMPLE_FE_SERVICE, examples=[EXAMPLE_FE_SERVICE]),
        sap_client: Optional[str] = Query(default=None, examples=["600"]),
        _: None = Depends(require_api_key),
    ) -> Dict[str, Any]:
        """List entity sets for a service."""
        gw = get_gateway()
        try:
            with gw.build_session() as sess:
                s = ODataService(
                    sess, service,
                    default_sap_client=sap_client or gw.sap_client
                )
                return {"service": service, "entity_sets": s.list_entity_sets()}
        except ODataUpstreamError as e:
            raise HTTPException(
                status_code=502,
                detail={"upstream_status": e.status, "url": e.url, "error": str(e)}
            )
    
    @app.get("/discover/fields", tags=["Discovery"])
    def discover_fields(
        service: str = Query(default=EXAMPLE_FE_SERVICE, examples=[EXAMPLE_FE_SERVICE]),
        entity_set: str = Query(default=EXAMPLE_FE_ENTITY_SET, examples=[EXAMPLE_FE_ENTITY_SET]),
        sap_client: Optional[str] = Query(default=None, examples=["600"]),
        _: None = Depends(require_api_key),
    ) -> Dict[str, Any]:
        """List fields for an entity set."""
        gw = get_gateway()
        try:
            with gw.build_session() as sess:
                s = ODataService(
                    sess, service,
                    default_sap_client=sap_client or gw.sap_client
                )
                return {
                    "service": service,
                    "entity_set": entity_set,
                    "fields": s.list_fields(entity_set)
                }
        except ODataUpstreamError as e:
            raise HTTPException(
                status_code=502,
                detail={"upstream_status": e.status, "url": e.url, "error": str(e)}
            )
    
    @app.get("/metadata/entity-sets", tags=["Discovery"])
    def list_entity_sets(
        service: str = Query(default=EXAMPLE_FE_SERVICE, examples=[EXAMPLE_FE_SERVICE]),
        _: None = Depends(require_api_key),
    ) -> Dict[str, Any]:
        """List entity sets with caching."""
        gw = get_gateway()
        now = time.time()
        
        cached = gw._meta_cache.get(service)
        if cached and (now - cached["ts"]) < gw.meta_cache_ttl:
            return {"service": service, "entity_sets": cached["entity_sets"], "cached": True}
        
        with gw.build_session() as sess:
            s = ODataService(sess, service, default_sap_client=gw.sap_client)
            es = s.list_entity_sets()
            gw._meta_cache[service] = {"ts": now, "entity_sets": es, "fields": {}}
            return {"service": service, "entity_sets": es, "cached": False}
    
    @app.get("/metadata/fields", tags=["Discovery"])
    def list_fields(
        service: str = Query(default=EXAMPLE_FE_SERVICE, examples=[EXAMPLE_FE_SERVICE]),
        entity_set: str = Query(default=EXAMPLE_FE_ENTITY_SET, examples=[EXAMPLE_FE_ENTITY_SET]),
        _: None = Depends(require_api_key),
    ) -> Dict[str, Any]:
        """List fields with caching."""
        gw = get_gateway()
        now = time.time()
        
        cached = gw._meta_cache.get(service)
        if not cached or (now - cached["ts"]) >= gw.meta_cache_ttl:
            cached = {"ts": now, "entity_sets": [], "fields": {}}
            gw._meta_cache[service] = cached
        
        fields_map = cached["fields"]
        if entity_set in fields_map:
            return {
                "service": service,
                "entity_set": entity_set,
                "fields": fields_map[entity_set],
                "cached": True
            }
        
        with gw.build_session() as sess:
            s = ODataService(sess, service, default_sap_client=gw.sap_client)
            fields = s.list_fields(entity_set)
            fields_map[entity_set] = fields
            cached["ts"] = now
            return {
                "service": service,
                "entity_set": entity_set,
                "fields": fields,
                "cached": False
            }
    
    @app.post(
        "/query",
        response_model=QueryResponse,
        tags=["Generic OData"],
        summary="Execute OData Query",
        description="Execute a generic OData query with sensible defaults for Force Elements.",
    )
    def query_any(
        req: QueryRequest,
        _: None = Depends(require_api_key),
    ) -> QueryResponse:
        """Execute a generic OData query. Just click Execute to test with Force Element defaults!"""
        gw = get_gateway()
        
        top = min(int(req.top or 0), gw.max_top) if req.top is not None else gw.max_top
        max_pages = min(int(req.max_pages or 1), gw.max_pages)
        
        try:
            with gw.build_session() as sess:
                s = ODataService(
                    sess, req.service,
                    default_sap_client=req.sap_client or gw.sap_client
                )
                
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
            raise HTTPException(
                status_code=502,
                detail={"upstream_status": e.status, "message": str(e), "url": e.url}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # -------------------------------------------------------------------------
    # Force Element Endpoints (SAP D&S)
    # -------------------------------------------------------------------------
    
    @app.get(
        "/force-elements",
        tags=["Force Elements"],
        summary="List Force Elements",
        description="Query force elements with sensible defaults. Just click Execute to test!",
    )
    def list_force_elements(
        top: int = Query(
            default=20,
            description="Max results to return",
            ge=1,
            le=500,
            examples=[20]
        ),
        filter: Optional[str] = Query(
            default=None,
            description="OData $filter expression",
            examples=[f"ForceElementOrgID eq '{EXAMPLE_FE_ID}'"]
        ),
        select: Optional[str] = Query(
            default=None,
            description="Comma-separated fields for $select",
            examples=["ForceElementOrgID,FrcElmntOrgName,FrcElmntOrgShortName"]
        ),
        orderby: Optional[str] = Query(
            default=None,
            description="OData $orderby expression (note: some entities don't support ordering)",
            examples=["ForceElementOrgID asc"]
        ),
        _: None = Depends(require_api_key),
    ) -> Dict[str, Any]:
        """
        Query Force Elements from DFS_FE_FRCELMNTORG_SRV.
        
        **Example Force Element IDs:**
        - 50000027, 50000028, 50000029, 50000030
        
        **Common filter examples:**
        - `ForceElementOrgID eq '50000027'`
        - `startswith(FrcElmntOrgName, 'SandBox')`
        
        Note: This entity is draft-enabled, so IsActiveEntity eq true is automatically added.
        """
        gw = get_gateway()
        
        fields = select.split(",") if select else EXAMPLE_FE_SELECT
        
        # For draft-enabled entities, we need IsActiveEntity filter
        draft_filter = "IsActiveEntity eq true"
        if filter:
            combined_filter = f"({filter}) and {draft_filter}"
        else:
            combined_filter = draft_filter
        
        try:
            with gw.build_session() as sess:
                s = ODataService(
                    sess, EXAMPLE_FE_SERVICE,
                    default_sap_client=gw.sap_client
                )
                items = s.query(
                    EXAMPLE_FE_ENTITY_SET,
                    fields=fields,
                    filter_expr=combined_filter,
                    orderby=orderby,
                    top=min(top, gw.max_top),
                    validate_fields=False,  # Skip validation for draft-enabled entities
                )
                return {
                    "service": EXAMPLE_FE_SERVICE,
                    "entity_set": EXAMPLE_FE_ENTITY_SET,
                    "count": len(items),
                    "items": items
                }
        except ODataUpstreamError as e:
            raise HTTPException(
                status_code=502,
                detail={"upstream_status": e.status, "url": e.url, "error": str(e)}
            )
    
    @app.get(
        "/force-elements/{force_element_id}",
        tags=["Force Elements"],
        summary="Get Force Element by ID",
        description="Fetch a single force element by its ID.",
    )
    def get_force_element(
        force_element_id: str = PathParam(
            default=...,
            description="Force Element Org ID",
            examples=[EXAMPLE_FE_ID]
        ),
        _: None = Depends(require_api_key),
    ) -> Dict[str, Any]:
        """
        Get a single Force Element by ID.
        
        **Example IDs:** 50000026, 50000027, 50000028
        """
        gw = get_gateway()
        
        try:
            with gw.build_session() as sess:
                s = ODataService(
                    sess, EXAMPLE_FE_SERVICE,
                    default_sap_client=gw.sap_client
                )
                # Add IsActiveEntity filter for draft-enabled entity
                items = s.query(
                    EXAMPLE_FE_ENTITY_SET,
                    filter_expr=f"ForceElementOrgID eq '{force_element_id}' and IsActiveEntity eq true",
                    top=1,
                    validate_fields=False,
                )
                if not items:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Force Element '{force_element_id}' not found"
                    )
                return {
                    "force_element_id": force_element_id,
                    "data": items[0]
                }
        except ODataUpstreamError as e:
            raise HTTPException(
                status_code=502,
                detail={"upstream_status": e.status, "url": e.url, "error": str(e)}
            )
    
    @app.post(
        "/force-elements/tree",
        tags=["Force Elements"],
        summary="Get Force Element Tree",
        description="Fetch organizational hierarchy tree starting from a root element.",
        response_model=ForceElementTreeResponse,
    )
    def get_force_element_tree(
        req: ForceElementTreeRequest,
        _: None = Depends(require_api_key),
    ) -> ForceElementTreeResponse:
        """
        Build a hierarchical tree of force elements.
        
        **Hierarchy Types:**
        - `structure` - Structural hierarchy (default)
        - `peacetime` - Peacetime assignment
        - `wartime` - Wartime assignment  
        - `operation` - Operational assignment
        - `exercise` - Exercise assignment
        
        **Try it:** Just click Execute with defaults!
        """
        from sap_ds.defense.force_elements.constants import PARENT_FIELDS
        
        gw = get_gateway()
        parent_field = PARENT_FIELDS.get(req.hierarchy_type, PARENT_FIELDS["structure"])
        
        # Build select fields
        fields = [
            "ForceElementOrgID",
            "FrcElmntOrgName",
            "FrcElmntOrgShortName",
            parent_field,
        ]
        if req.include_readiness:
            fields.extend([
                "FrcElmntOrgMatlRdnssPct",
                "FrcElmntOrgPrsnlRdnssPct", 
                "FrcElmntOrgTrngRdnssPct",
            ])
        if req.include_sidc:
            fields.append("FrcElmntOrgMilSymbCode")
        
        try:
            with gw.build_session() as sess:
                s = ODataService(
                    sess, EXAMPLE_FE_SERVICE,
                    default_sap_client=gw.sap_client
                )
                
                # BFS to collect nodes up to depth
                visited = set()
                queue = [(req.root_id, 0)]
                nodes = []
                
                while queue:
                    current_id, level = queue.pop(0)
                    if current_id in visited or level > req.depth:
                        continue
                    visited.add(current_id)
                    
                    # Fetch current node (add IsActiveEntity for draft-enabled entity)
                    items = s.query(
                        EXAMPLE_FE_ENTITY_SET,
                        fields=fields,
                        filter_expr=f"ForceElementOrgID eq '{current_id}' and IsActiveEntity eq true",
                        top=1,
                        validate_fields=False,
                    )
                    
                    if items:
                        item = items[0]
                        node = ForceElementNode(
                            id=item.get("ForceElementOrgID", current_id),
                            name=item.get("FrcElmntOrgName"),
                            short_name=item.get("FrcElmntOrgShortName"),
                            parent_id=item.get(parent_field),
                            level=level,
                            material_readiness=item.get("FrcElmntOrgMatlRdnssPct"),
                            personnel_readiness=item.get("FrcElmntOrgPrsnlRdnssPct"),
                            training_readiness=item.get("FrcElmntOrgTrngRdnssPct"),
                            sidc=item.get("FrcElmntOrgMilSymbCode") if req.include_sidc else None,
                        )
                        nodes.append(node)
                        
                        # Find children (where parent_field equals current_id)
                        if level < req.depth:
                            children = s.query(
                                EXAMPLE_FE_ENTITY_SET,
                                fields=["ForceElementOrgID"],
                                filter_expr=f"{parent_field} eq '{current_id}' and IsActiveEntity eq true",
                                top=100,
                                validate_fields=False,
                            )
                            for child in children:
                                child_id = child.get("ForceElementOrgID")
                                if child_id and child_id not in visited:
                                    queue.append((child_id, level + 1))
                
                return ForceElementTreeResponse(
                    root_id=req.root_id,
                    hierarchy_type=req.hierarchy_type,
                    depth=req.depth,
                    node_count=len(nodes),
                    nodes=nodes,
                )
                
        except ODataUpstreamError as e:
            raise HTTPException(
                status_code=502,
                detail={"upstream_status": e.status, "url": e.url, "error": str(e)}
            )
    
    @app.post(
        "/force-elements/graph",
        tags=["Force Elements"],
        summary="Get Force Element Graph",
        description="Fetch graph edges via BFS traversal from root element.",
        response_model=ForceElementGraphResponse,
    )
    def get_force_element_graph(
        req: ForceElementGraphRequest,
        _: None = Depends(require_api_key),
    ) -> ForceElementGraphResponse:
        """
        Fetch organizational graph edges using BFS.
        
        Uses the graph service `DFS_FE_FRCELMNTORGNTWKGRAPH_SRV`.
        
        **Relation Types:**
        - `B002` - Structural hierarchy (default)
        
        **Try it:** Just click Execute with defaults!
        """
        from sap_ds.defense.force_elements.constants import (
            SVC_GRAPH,
            ES_GRAPH_EDGE,
            SRC_FIELD,
            DST_FIELD,
            REL_FIELD,
        )
        
        gw = get_gateway()
        
        try:
            with gw.build_session() as sess:
                s = ODataService(
                    sess, SVC_GRAPH,
                    default_sap_client=gw.sap_client
                )
                
                visited = set()
                queue = [req.root_id]
                edges = []
                current_depth = 0
                
                while queue and current_depth < req.depth:
                    current_depth += 1
                    next_queue = []
                    
                    for node_id in queue:
                        if node_id in visited:
                            continue
                        visited.add(node_id)
                        
                        # Fetch edges from this node
                        filter_expr = f"{SRC_FIELD} eq '{node_id}'"
                        if req.relation_type:
                            filter_expr += f" and {REL_FIELD} eq '{req.relation_type}'"
                        
                        items = s.query(
                            ES_GRAPH_EDGE,
                            fields=[SRC_FIELD, DST_FIELD, REL_FIELD],
                            filter_expr=filter_expr,
                            top=500,
                        )
                        
                        for item in items:
                            dst = item.get(DST_FIELD)
                            edges.append({
                                "source": item.get(SRC_FIELD),
                                "target": dst,
                                "relation_type": item.get(REL_FIELD),
                            })
                            if dst and dst not in visited:
                                next_queue.append(dst)
                    
                    queue = next_queue
                
                return ForceElementGraphResponse(
                    root_id=req.root_id,
                    depth=req.depth,
                    edge_count=len(edges),
                    edges=edges,
                )
                
        except ODataUpstreamError as e:
            raise HTTPException(
                status_code=502,
                detail={"upstream_status": e.status, "url": e.url, "error": str(e)}
            )
    
    @app.post(
        "/force-elements/readiness",
        tags=["Force Elements"],
        summary="Get Readiness KPIs",
        description="Fetch readiness KPIs for multiple force elements.",
        response_model=ForceElementReadinessResponse,
    )
    def get_force_element_readiness(
        req: ForceElementReadinessRequest,
        _: None = Depends(require_api_key),
    ) -> ForceElementReadinessResponse:
        """
        Fetch readiness KPIs (material, personnel, training) for force elements.
        
        **Default IDs:** 50000026, 50000027, 50000028
        
        **Try it:** Just click Execute with defaults!
        """
        gw = get_gateway()
        
        fields = [
            "ForceElementOrgID",
            "FrcElmntOrgName",
            "FrcElmntOrgMatlRdnssPct",
            "FrcElmntOrgPrsnlRdnssPct",
            "FrcElmntOrgTrngRdnssPct",
        ]
        
        # Build filter for multiple IDs
        id_filters = [f"ForceElementOrgID eq '{fid}'" for fid in req.force_element_ids]
        filter_expr = " or ".join(id_filters)
        
        try:
            with gw.build_session() as sess:
                s = ODataService(
                    sess, EXAMPLE_FE_SERVICE,
                    default_sap_client=gw.sap_client
                )
                items = s.query(
                    EXAMPLE_FE_ENTITY_SET,
                    fields=fields,
                    filter_expr=filter_expr,
                    top=len(req.force_element_ids),
                )
                
                return ForceElementReadinessResponse(
                    count=len(items),
                    items=items,
                )
                
        except ODataUpstreamError as e:
            raise HTTPException(
                status_code=502,
                detail={"upstream_status": e.status, "url": e.url, "error": str(e)}
            )
    
    @app.get(
        "/force-elements/metadata",
        tags=["Force Elements"],
        summary="Get Force Element Metadata",
        description="Get available entity sets and fields for force element services.",
    )
    def get_force_element_metadata(
        _: None = Depends(require_api_key),
    ) -> Dict[str, Any]:
        """
        Discover force element service metadata.
        
        Returns entity sets and fields available in the Force Element OData services.
        """
        from sap_ds.defense.force_elements.constants import (
            SVC_FORCE_ELEMENT,
            SVC_GRAPH,
            ES_FORCE_ELEMENT_TP,
            ES_GRAPH_EDGE,
            PARENT_FIELDS,
            READINESS_FIELDS,
            SIDC_FIELDS,
        )
        
        gw = get_gateway()
        result = {
            "services": {
                "force_element": {
                    "name": SVC_FORCE_ELEMENT,
                    "entity_sets": [],
                    "example_fields": None,
                },
                "graph": {
                    "name": SVC_GRAPH,
                    "entity_sets": [],
                    "example_fields": None,
                }
            },
            "hierarchy_types": list(PARENT_FIELDS.keys()),
            "readiness_fields": READINESS_FIELDS,
            "sidc_fields": SIDC_FIELDS,
            "example_ids": ["50000026", "50000027", "50000028"],
        }
        
        try:
            with gw.build_session() as sess:
                # Get FE service metadata
                fe_svc = ODataService(sess, SVC_FORCE_ELEMENT, default_sap_client=gw.sap_client)
                result["services"]["force_element"]["entity_sets"] = fe_svc.list_entity_sets()
                try:
                    result["services"]["force_element"]["example_fields"] = fe_svc.list_fields(ES_FORCE_ELEMENT_TP)
                except Exception:
                    pass
                
                # Get Graph service metadata
                graph_svc = ODataService(sess, SVC_GRAPH, default_sap_client=gw.sap_client)
                result["services"]["graph"]["entity_sets"] = graph_svc.list_entity_sets()
                try:
                    result["services"]["graph"]["example_fields"] = graph_svc.list_fields(ES_GRAPH_EDGE)
                except Exception:
                    pass
                    
        except ODataUpstreamError as e:
            result["error"] = {"upstream_status": e.status, "message": str(e)}
        except Exception as e:
            result["error"] = {"message": str(e)}
        
        return result
    
    return app


# Default app for direct uvicorn usage
def _get_default_app() -> FastAPI:
    """Get the default app, validating configuration."""
    return create_app(validate_on_startup=True)
