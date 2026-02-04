"""
sap_ds.api.models - Pydantic models for API requests/responses
===============================================================
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Example defaults for SAP D&S Force Elements
# ---------------------------------------------------------------------------

# Real SAP D&S services
EXAMPLE_FE_SERVICE = "DFS_FE_FRCELMNTORG_SRV"
EXAMPLE_FE_GRAPH_SERVICE = "DFS_FE_FRCELMNTORGNTWKGRAPH_SRV"
EXAMPLE_FE_ENTITY_SET = "C_FrcElmntOrgTP"
EXAMPLE_FE_GRAPH_ENTITY_SET = "C_FrcElmntOrgNtwkGraphRelshp"

# Example Force Element IDs (commonly used in testing)
EXAMPLE_FE_ID = "50000027"
EXAMPLE_FE_IDS = ["50000026", "50000027", "50000028"]

# Common fields
EXAMPLE_FE_SELECT = [
    "ForceElementOrgID",
    "FrcElmntOrgName",
    "FrcElmntOrgShortName",
    "FrcElmntOrgStrucParentID",
    "FrcElmntOrgMatlRdnssPct",
    "FrcElmntOrgPrsnlRdnssPct",
    "FrcElmntOrgTrngRdnssPct",
]


class QueryRequest(BaseModel):
    """Request model for generic OData queries."""
    
    service: str = Field(
        default=EXAMPLE_FE_SERVICE,
        description="Technical service name, e.g. DFS_FE_FRCELMNTORG_SRV",
        json_schema_extra={"example": EXAMPLE_FE_SERVICE}
    )
    entity_set: str = Field(
        default=EXAMPLE_FE_ENTITY_SET,
        description="Entity set name, e.g. C_FrcElmntOrgTP",
        json_schema_extra={"example": EXAMPLE_FE_ENTITY_SET}
    )
    sap_client: Optional[str] = Field(
        default=None,
        description="Overrides default sap-client",
        json_schema_extra={"example": "600"}
    )
    select: Optional[List[str]] = Field(
        default=None,
        description="Fields for $select",
        json_schema_extra={"example": EXAMPLE_FE_SELECT}
    )
    filter: Optional[str] = Field(
        default=None,
        description="Raw $filter expression",
        json_schema_extra={"example": f"ForceElementOrgID eq '{EXAMPLE_FE_ID}'"}
    )
    orderby: Optional[str] = Field(
        default=None,
        description="Raw $orderby",
        json_schema_extra={"example": "FrcElmntOrgName asc"}
    )
    expand: Optional[str] = Field(
        default=None,
        description="Raw $expand",
        json_schema_extra={"example": "to_FrcElmntOrgHierarchy"}
    )
    top: Optional[int] = Field(
        default=100,
        description="Top rows per request",
        json_schema_extra={"example": 100}
    )
    skip: Optional[int] = Field(
        default=None,
        description="$skip",
        json_schema_extra={"example": 0}
    )
    max_pages: Optional[int] = Field(
        default=1,
        description="Max pages to follow (paging)",
        json_schema_extra={"example": 1}
    )
    validate_fields: bool = Field(
        default=True,
        description="Validate $select fields against $metadata"
    )
    extra_params: Optional[Dict[str, str]] = Field(
        default=None,
        description="Any additional OData params"
    )


class QueryResponse(BaseModel):
    """Response model for OData queries."""
    
    service: str
    entity_set: str
    count: int
    items: List[Dict[str, Any]]


class ServiceInfo(BaseModel):
    """Information about a discovered service."""
    
    technical_name: str
    version: Optional[str] = None
    external_name: Optional[str] = None
    url: Optional[str] = None


class EntitySetInfo(BaseModel):
    """Information about an entity set."""
    
    name: str
    fields: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Force Element specific models
# ---------------------------------------------------------------------------

class ForceElementTreeRequest(BaseModel):
    """Request to fetch a force element tree."""
    
    root_id: str = Field(
        default=EXAMPLE_FE_ID,
        description="Root Force Element Org ID to start traversal from",
        json_schema_extra={"example": EXAMPLE_FE_ID}
    )
    depth: int = Field(
        default=3,
        description="Max depth to traverse (1-10)",
        ge=1,
        le=10,
        json_schema_extra={"example": 3}
    )
    hierarchy_type: str = Field(
        default="structure",
        description="Hierarchy type: structure, peacetime, wartime, operation, exercise",
        json_schema_extra={"example": "structure"}
    )
    include_readiness: bool = Field(
        default=True,
        description="Include readiness KPIs (material, personnel, training)",
        json_schema_extra={"example": True}
    )
    include_sidc: bool = Field(
        default=False,
        description="Include military symbol codes (SIDC)",
        json_schema_extra={"example": False}
    )


class ForceElementGraphRequest(BaseModel):
    """Request to fetch force element graph edges."""
    
    root_id: str = Field(
        default=EXAMPLE_FE_ID,
        description="Root Force Element Org ID to start BFS from",
        json_schema_extra={"example": EXAMPLE_FE_ID}
    )
    depth: int = Field(
        default=5,
        description="Max BFS depth (1-20)",
        ge=1,
        le=20,
        json_schema_extra={"example": 5}
    )
    relation_type: str = Field(
        default="B002",
        description="Relation type filter (B002 = structural)",
        json_schema_extra={"example": "B002"}
    )


class ForceElementReadinessRequest(BaseModel):
    """Request to fetch readiness KPIs for force elements."""
    
    force_element_ids: List[str] = Field(
        default=EXAMPLE_FE_IDS,
        description="List of Force Element Org IDs",
        json_schema_extra={"example": EXAMPLE_FE_IDS}
    )


class ForceElementNode(BaseModel):
    """A single force element node."""
    
    id: str = Field(description="Force Element Org ID")
    name: Optional[str] = Field(default=None, description="Display name")
    short_name: Optional[str] = Field(default=None, description="Short name")
    parent_id: Optional[str] = Field(default=None, description="Parent ID in hierarchy")
    level: int = Field(default=0, description="Depth level from root")
    material_readiness: Optional[float] = Field(default=None, description="Material readiness %")
    personnel_readiness: Optional[float] = Field(default=None, description="Personnel readiness %")
    training_readiness: Optional[float] = Field(default=None, description="Training readiness %")
    sidc: Optional[str] = Field(default=None, description="Military symbol code")
    deep_link: Optional[str] = Field(default=None, description="Link to S/4HANA Fiori app")


class ForceElementTreeResponse(BaseModel):
    """Response containing a force element tree."""
    
    root_id: str
    hierarchy_type: str
    depth: int
    node_count: int
    nodes: List[ForceElementNode]


class ForceElementGraphResponse(BaseModel):
    """Response containing graph edges."""
    
    root_id: str
    depth: int
    edge_count: int
    edges: List[Dict[str, str]]


class ForceElementReadinessResponse(BaseModel):
    """Response containing readiness KPIs."""
    
    count: int
    items: List[Dict[str, Any]]
