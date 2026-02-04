"""
sap_ds.defense.force_elements.readiness - Readiness KPI fetching
==================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from sap_ds.odata.service import ODataService, escape_odata_literal
from sap_ds.core.session import SAPODataSession, ODataUpstreamError
from sap_ds.defense.force_elements.constants import (
    SVC_FORCE_ELEMENT, ES_FORCE_ELEMENT_TP, ID_FIELD, READINESS_FIELDS
)

logger = logging.getLogger("sap_ds.defense.fe")


def _chunks(items: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _filter_or(ids: List[str]) -> str:
    return " or ".join([
        f"{ID_FIELD} eq '{escape_odata_literal(i)}'" 
        for i in ids
    ])


def _to_int_pct(v: Any) -> Optional[int]:
    """Normalize readiness percent fields to 0..100 int."""
    if v is None:
        return None
    if isinstance(v, int):
        return max(0, min(100, v))
    s = str(v).strip()
    if not s:
        return None
    try:
        return max(0, min(100, int(s)))
    except Exception:
        return None


def _derive_score(
    material: Optional[int],
    personnel: Optional[int],
    training: Optional[int]
) -> int:
    """Conservative aggregate score using min of available KPIs."""
    vals = [x for x in (material, personnel, training) if isinstance(x, int)]
    return int(min(vals)) if vals else 0


def _score_to_status(score: int) -> str:
    """Map score to status label."""
    if score >= 85:
        return "FMC"  # Fully Mission Capable
    if score >= 60:
        return "PMC"  # Partially Mission Capable
    return "NMC"  # Not Mission Capable


def fetch_readiness_bulk(
    session: SAPODataSession,
    ids: Iterable[str],
    *,
    sap_client: Optional[str] = None,
    chunk_size: int = 40,
    timeout: Optional[float] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Bulk-read readiness KPI percentages for Force Elements.
    
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
        Mapping of ID -> readiness info:
        {
            "status": "FMC|PMC|NMC|UNK",
            "score": int,
            "kpis": {"materialPct": ..., "personnelPct": ..., "trainingPct": ...}
        }
    """
    id_list = sorted({str(x).strip() for x in ids if str(x).strip()})
    if not id_list:
        return {}
        
    out: Dict[str, Dict[str, Any]] = {}
    
    select = ",".join([ID_FIELD] + READINESS_FIELDS)
    svc = ODataService(session, SVC_FORCE_ELEMENT, default_sap_client=sap_client)
    
    for group in _chunks(id_list, int(chunk_size)):
        flt = _filter_or(group)
        
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
            logger.warning(f"fetch_readiness_bulk: error status={e.status}")
            continue
            
        for r in rows or []:
            fe_id = str(r.get(ID_FIELD) or "").strip()
            if not fe_id:
                continue
                
            material = _to_int_pct(r.get("FrcElmntOrgMatlRdnssPct"))
            personnel = _to_int_pct(r.get("FrcElmntOrgPrsnlRdnssPct"))
            training = _to_int_pct(r.get("FrcElmntOrgTrngRdnssPct"))
            
            score = _derive_score(material, personnel, training)
            status = _score_to_status(score)
            
            out[fe_id] = {
                "status": status,
                "score": score,
                "kpis": {
                    "materialPct": material,
                    "personnelPct": personnel,
                    "trainingPct": training,
                }
            }
            
    return out


def apply_readiness_to_tree(
    payload: Dict[str, Any],
    readiness_by_id: Dict[str, Dict[str, Any]],
) -> None:
    """
    Apply readiness data to a tree payload in-place.
    
    Parameters
    ----------
    payload : dict
        Tree payload from build_tree_table
    readiness_by_id : dict
        Mapping of ID -> readiness info
    """
    tree = payload.get("tree", {})
    nodes = tree.get("nodes", [])
    
    for node in nodes:
        nid = str(node.get("id") or "")
        if nid and nid in readiness_by_id:
            node["readiness"] = readiness_by_id[nid]
            
    # Also apply to nested roots
    def apply_nested(items: List[Dict]) -> None:
        for item in items:
            nid = str(item.get("id") or "")
            if nid and nid in readiness_by_id:
                item["readiness"] = readiness_by_id[nid]
            children = item.get("children", [])
            if children and isinstance(children[0], dict):
                apply_nested(children)
                
    roots = tree.get("roots", [])
    if roots:
        apply_nested(roots)
