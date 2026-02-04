"""
sap_ds.defense.force_elements.labels - Name resolution for Force Elements
==========================================================================
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional

from sap_ds.odata.service import ODataService, escape_odata_literal
from sap_ds.core.session import SAPODataSession, ODataUpstreamError
from sap_ds.defense.force_elements.constants import (
    SVC_FORCE_ELEMENT, ES_FORCE_ELEMENT_TP, ID_FIELD, NAME_FIELDS
)

logger = logging.getLogger("sap_ds.defense.fe")


def _chunks(lst: List[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def deep_link(host: str, fe_id: str) -> str:
    """
    Generate Fiori Launchpad deep link for a Force Element.
    
    Parameters
    ----------
    host : str
        SAP host (without protocol)
    fe_id : str
        Force Element ID
        
    Returns
    -------
    str
        Full deep link URL
    """
    return (
        f"https://{host}/sap/bc/ui2/flp#ForceElement-manageFE?sap-keep-alive=true"
        f"&/C_FrcElmntOrgTP(ForceElementOrgID='{escape_odata_literal(fe_id)}',"
        f"DraftUUID=guid'00000000-0000-0000-0000-000000000000',IsActiveEntity=true)/"
    )


def fetch_names_for_ids(
    session: SAPODataSession,
    ids: Iterable[str],
    *,
    sap_client: Optional[str] = None,
    chunk_size: int = 20,
) -> Dict[str, str]:
    """
    Fetch Force Element names from C_FrcElmntOrgTP.
    
    Falls back to ID if name fetch fails for any reason.
    
    Parameters
    ----------
    session : SAPODataSession
        Active OData session
    ids : iterable of str
        Force Element IDs to look up
    sap_client : str, optional
        SAP client override
    chunk_size : int
        Batch size for queries
        
    Returns
    -------
    dict
        Mapping of ID -> name
    """
    ids_list = sorted({str(x).strip() for x in ids if str(x).strip()})
    if not ids_list:
        return {}
        
    svc = ODataService(session, SVC_FORCE_ELEMENT, default_sap_client=sap_client)
    out: Dict[str, str] = {}
    
    select_fields = ",".join([ID_FIELD] + NAME_FIELDS[:3])  # Limit to top 3
    
    for batch in _chunks(ids_list, chunk_size):
        flt = " or ".join([
            f"{ID_FIELD} eq '{escape_odata_literal(x)}'" 
            for x in batch
        ])
        
        try:
            rows = svc.read(
                ES_FORCE_ELEMENT_TP,
                sap_client=sap_client,
                **{
                    "$select": select_fields,
                    "$filter": flt,
                    "$top": str(len(batch)),
                }
            )
            
            for r in rows:
                fe_id = str(r.get(ID_FIELD, "")).strip()
                if not fe_id:
                    continue
                    
                name = ""
                for f in NAME_FIELDS:
                    v = r.get(f)
                    if v is not None and str(v).strip():
                        name = str(v).strip()
                        break
                        
                out[fe_id] = name or fe_id
                
        except ODataUpstreamError as e:
            logger.warning(f"fetch_names_for_ids: batch failed status={e.status}")
            # Fill with IDs on failure
            for x in batch:
                out.setdefault(x, x)
                
    # Ensure all requested IDs exist
    for x in ids_list:
        out.setdefault(x, x)
        
    return out


def fetch_single_fe(
    session: SAPODataSession,
    fe_id: str,
    *,
    sap_client: Optional[str] = None,
    host: str = "localhost",
) -> Dict[str, str]:
    """
    Fetch minimal info for a single Force Element.
    
    Returns
    -------
    dict
        {"id": ..., "name": ..., "url": ...}
    """
    names = fetch_names_for_ids(session, [fe_id], sap_client=sap_client)
    return {
        "id": fe_id,
        "name": names.get(fe_id, fe_id),
        "url": deep_link(host, fe_id),
    }
