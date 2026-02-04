"""
sap_ds.defense.force_elements.symbol - Military symbol (SIDC) handling
========================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from sap_ds.odata.service import ODataService, escape_odata_literal
from sap_ds.core.session import SAPODataSession, ODataUpstreamError
from sap_ds.defense.force_elements.constants import (
    SVC_FORCE_ELEMENT, ES_FORCE_ELEMENT_TP, ID_FIELD, SIDC_FIELD_CANDIDATES
)

logger = logging.getLogger("sap_ds.defense.fe")

# Runtime cache for discovered SIDC field
_SIDC_FIELD: Optional[str] = None
_SIDC_PROBE_COMPLETE: bool = False


def _chunks(items: List[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _filter_or(ids: List[str]) -> str:
    return " or ".join([
        f"{ID_FIELD} eq '{escape_odata_literal(i)}'" 
        for i in ids
    ])


def _normalize_sidc(v: Any) -> Optional[str]:
    """Normalize SIDC value."""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _probe_sidc_field(
    session: SAPODataSession,
    *,
    sap_client: Optional[str] = None,
) -> Optional[str]:
    """
    Discover which property contains SIDC/military symbol code.
    
    Tries candidate field names until one works.
    Result is cached for process lifetime.
    """
    global _SIDC_FIELD, _SIDC_PROBE_COMPLETE
    
    if _SIDC_PROBE_COMPLETE:
        return _SIDC_FIELD
        
    svc = ODataService(session, SVC_FORCE_ELEMENT, default_sap_client=sap_client)
    
    for field in SIDC_FIELD_CANDIDATES:
        try:
            rows = svc.read(
                ES_FORCE_ELEMENT_TP,
                sap_client=sap_client,
                **{
                    "$top": "1",
                    "$select": f"{ID_FIELD},{field}",
                }
            )
            # If we get here, field exists
            _SIDC_FIELD = field
            _SIDC_PROBE_COMPLETE = True
            logger.info(f"symbol: discovered SIDC field '{field}'")
            return _SIDC_FIELD
            
        except ODataUpstreamError as e:
            logger.debug(f"symbol: SIDC probe failed for field='{field}'")
            continue
            
    _SIDC_PROBE_COMPLETE = True
    logger.warning("symbol: no SIDC field found")
    return None


def get_sidc_field(
    session: SAPODataSession,
    *,
    sap_client: Optional[str] = None,
) -> Optional[str]:
    """
    Get the SIDC field name (probing if necessary).
    
    Returns None if SIDC is not available on this system.
    """
    return _probe_sidc_field(session, sap_client=sap_client)


def fetch_sidc_bulk(
    session: SAPODataSession,
    ids: Iterable[str],
    *,
    sap_client: Optional[str] = None,
    chunk_size: int = 40,
) -> Dict[str, str]:
    """
    Bulk-fetch SIDC codes for Force Elements.
    
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
        Mapping of ID -> SIDC string
    """
    sidc_field = _probe_sidc_field(session, sap_client=sap_client)
    if not sidc_field:
        return {}
        
    id_list = sorted({str(x).strip() for x in ids if str(x).strip()})
    if not id_list:
        return {}
        
    out: Dict[str, str] = {}
    svc = ODataService(session, SVC_FORCE_ELEMENT, default_sap_client=sap_client)
    
    select = f"{ID_FIELD},{sidc_field}"
    
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
            logger.warning(f"fetch_sidc_bulk: error status={e.status}")
            continue
            
        for r in rows or []:
            fe_id = str(r.get(ID_FIELD) or "").strip()
            sidc = _normalize_sidc(r.get(sidc_field))
            if fe_id and sidc:
                out[fe_id] = sidc
                
    return out


def apply_sidc_to_tree(
    payload: Dict[str, Any],
    sidc_by_id: Dict[str, str],
    *,
    icon_base_url: str = "/icons/cache",
) -> None:
    """
    Apply SIDC data to a tree payload in-place.
    
    Updates iconUrl based on SIDC.
    
    Parameters
    ----------
    payload : dict
        Tree payload from build_tree_table
    sidc_by_id : dict
        Mapping of ID -> SIDC string
    icon_base_url : str
        Base URL for icon assets
    """
    tree = payload.get("tree", {})
    nodes = tree.get("nodes", [])
    
    for node in nodes:
        nid = str(node.get("id") or "")
        if nid and nid in sidc_by_id:
            sidc = sidc_by_id[nid]
            node["sidc"] = sidc
            # Generate icon URL from SIDC (simplified)
            node["iconUrl"] = f"{icon_base_url}/{sidc}.svg"
            
    # Also apply to nested roots
    def apply_nested(items: List[Dict]) -> None:
        for item in items:
            nid = str(item.get("id") or "")
            if nid and nid in sidc_by_id:
                sidc = sidc_by_id[nid]
                item["sidc"] = sidc
                item["iconUrl"] = f"{icon_base_url}/{sidc}.svg"
            children = item.get("children", [])
            if children and isinstance(children[0], dict):
                apply_nested(children)
                
    roots = tree.get("roots", [])
    if roots:
        apply_nested(roots)
