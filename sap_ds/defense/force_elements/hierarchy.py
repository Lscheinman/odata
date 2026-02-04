"""
sap_ds.defense.force_elements.hierarchy - Hierarchy traversal via TP entity
=============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from sap_ds.odata.service import ODataService, escape_odata_literal
from sap_ds.core.session import SAPODataSession, ODataUpstreamError
from sap_ds.defense.force_elements.constants import (
    SVC_FORCE_ELEMENT, ES_FORCE_ELEMENT_TP, PARENT_FIELDS
)

logger = logging.getLogger("sap_ds.defense.fe")


def _chunks(items: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _filter_or(field: str, vals: List[str]) -> str:
    """Build OR filter expression."""
    return " or ".join([
        f"{field} eq '{escape_odata_literal(v)}'" 
        for v in vals
    ])


def fetch_nodes_bulk(
    session: SAPODataSession,
    ids: Iterable[str],
    *,
    sap_client: Optional[str] = None,
    timeout: Optional[float] = 10.0,
    chunk_size: int = 40,
) -> Dict[str, Dict[str, Any]]:
    """
    Fetch basic node fields for a set of Force Element IDs.
    
    Parameters
    ----------
    session : SAPODataSession
        Active OData session
    ids : iterable of str
        Force Element IDs
    sap_client : str, optional
        SAP client override
    chunk_size : int
        Batch size
        
    Returns
    -------
    dict
        Mapping of ID -> node info dict
    """
    id_list = sorted({str(x).strip() for x in ids if str(x).strip()})
    if not id_list:
        return {}
        
    select = ",".join([
        "ForceElementOrgID",
        "FrcElmntOrgName",
        "FrcElmntOrgSymbol",
        "FrcElmntOrgStrucParentID",
        "FrcElmntOrgPeaceTimeParentID",
        "FrcElmntOrgWarTimeParentID",
    ])
    
    out: Dict[str, Dict[str, Any]] = {}
    svc = ODataService(session, SVC_FORCE_ELEMENT, default_sap_client=sap_client)
    
    for group in _chunks(id_list, int(chunk_size)):
        flt = _filter_or("ForceElementOrgID", group)
        flt = f"({flt}) and (IsActiveEntity eq true)"
        
        try:
            rows = svc.read(
                ES_FORCE_ELEMENT_TP,
                sap_client=sap_client,
                **{
                    "$select": select,
                    "$filter": flt,
                }
            )
        except ODataUpstreamError as e:
            logger.warning(f"fetch_nodes_bulk: error status={e.status}")
            continue
            
        for r in rows or []:
            fe_id = str(r.get("ForceElementOrgID") or "").strip()
            if not fe_id:
                continue
            out[fe_id] = {
                "id": fe_id,
                "name": str(r.get("FrcElmntOrgName") or fe_id),
                "symbol": (str(r.get("FrcElmntOrgSymbol") or "").strip() or None),
                "parent_structure": (str(r.get("FrcElmntOrgStrucParentID") or "").strip() or None),
                "parent_peacetime": (str(r.get("FrcElmntOrgPeaceTimeParentID") or "").strip() or None),
                "parent_wartime": (str(r.get("FrcElmntOrgWarTimeParentID") or "").strip() or None),
            }
            
    return out


def fetch_children_bulk(
    session: SAPODataSession,
    parent_ids: Iterable[str],
    *,
    parent_mode: str = "structure",
    sap_client: Optional[str] = None,
    timeout: Optional[float] = 10.0,
    chunk_size: int = 25,
) -> List[Dict[str, Any]]:
    """
    Fetch child nodes for many parents using OR filter on parent field.
    
    Parameters
    ----------
    session : SAPODataSession
        Active OData session
    parent_ids : iterable of str
        Parent Force Element IDs
    parent_mode : str
        Hierarchy type: "structure", "peacetime", "wartime", "operation", "exercise"
    sap_client : str, optional
        SAP client override
    chunk_size : int
        Batch size
        
    Returns
    -------
    list of dict
        Child node records
    """
    pfield = PARENT_FIELDS.get(parent_mode) or PARENT_FIELDS["structure"]
    
    parents = sorted({str(x).strip() for x in parent_ids if str(x).strip()})
    if not parents:
        return []
        
    select = ",".join([
        "ForceElementOrgID",
        "FrcElmntOrgName",
        "FrcElmntOrgSymbol",
        pfield,
    ])
    
    rows_all: List[Dict[str, Any]] = []
    svc = ODataService(session, SVC_FORCE_ELEMENT, default_sap_client=sap_client)
    
    for group in _chunks(parents, int(chunk_size)):
        flt = _filter_or(pfield, group)
        flt = f"({flt}) and (IsActiveEntity eq true)"
        
        try:
            rows = svc.read(
                ES_FORCE_ELEMENT_TP,
                sap_client=sap_client,
                **{
                    "$select": select,
                    "$filter": flt,
                }
            )
            rows_all.extend(rows or [])
        except ODataUpstreamError as e:
            logger.warning(f"fetch_children_bulk: error status={e.status}")
            continue
            
    return rows_all


def traverse_hierarchy(
    session: SAPODataSession,
    root_id: str,
    *,
    parent_mode: str = "structure",
    max_depth: int = 10,
    sap_client: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Traverse hierarchy from root using specified parent mode.
    
    Parameters
    ----------
    session : SAPODataSession
        Active OData session
    root_id : str
        Root Force Element ID
    parent_mode : str
        Hierarchy type
    max_depth : int
        Maximum traversal depth
    sap_client : str, optional
        SAP client override
        
    Returns
    -------
    dict
        Mapping of ID -> node info for all discovered nodes
    """
    all_nodes: Dict[str, Dict[str, Any]] = {}
    
    # Fetch root
    root_nodes = fetch_nodes_bulk(session, [root_id], sap_client=sap_client)
    if not root_nodes:
        return {}
    all_nodes.update(root_nodes)
    
    frontier = [root_id]
    
    for _depth in range(max_depth):
        if not frontier:
            break
            
        children = fetch_children_bulk(
            session, frontier,
            parent_mode=parent_mode,
            sap_client=sap_client,
        )
        
        next_frontier = []
        for child in children:
            cid = str(child.get("ForceElementOrgID") or "").strip()
            if cid and cid not in all_nodes:
                all_nodes[cid] = {
                    "id": cid,
                    "name": str(child.get("FrcElmntOrgName") or cid),
                    "symbol": (str(child.get("FrcElmntOrgSymbol") or "").strip() or None),
                }
                next_frontier.append(cid)
                
        frontier = next_frontier
        
    return all_nodes
