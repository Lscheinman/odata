"""
sap_ds.defense.force_elements.graph - Graph edge fetching via BFS
==================================================================
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from sap_ds.odata.service import ODataService, escape_odata_literal
from sap_ds.core.session import SAPODataSession, ODataUpstreamError
from sap_ds.defense.force_elements.constants import (
    SVC_GRAPH, ES_GRAPH_EDGE, SRC_FIELD, DST_FIELD, REL_FIELD
)

logger = logging.getLogger("sap_ds.defense.fe")


def _chunks(lst: List[str], n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def fetch_fe_edges_all(
    session: SAPODataSession,
    root_id: str,
    *,
    depth: int = 3,
    sap_client: Optional[str] = None,
    batch_size: int = 20,
    max_pages: Optional[int] = None,
) -> List[Dict[str, str]]:
    """
    BFS traversal from root_id up to `depth` hops, returning ALL relationship types.
    
    Parameters
    ----------
    session : SAPODataSession
        Active OData session
    root_id : str
        Starting force element ID
    depth : int
        Maximum traversal depth
    sap_client : str, optional
        SAP client override
    batch_size : int
        Number of IDs per OData query
    max_pages : int, optional
        Max pages per query
        
    Returns
    -------
    list of dict
        Edges as {"source": ..., "target": ..., "rel": ...}
    """
    svc = ODataService(session, SVC_GRAPH, default_sap_client=sap_client)
    
    logger.info(f"fetch_fe_edges_all: root_id={root_id}, depth={depth}")
    
    discovered: Set[str] = {root_id}
    frontier: List[str] = [root_id]
    
    edge_seen: Set[tuple] = set()
    edges: List[Dict[str, str]] = []
    
    for _lvl in range(max(0, int(depth))):
        if not frontier:
            break
            
        next_frontier: List[str] = []
        
        for batch in _chunks(frontier, batch_size):
            flt = " or ".join([
                f"{SRC_FIELD} eq '{escape_odata_literal(x)}'" 
                for x in batch
            ])
            
            query = {
                "$select": f"{SRC_FIELD},{DST_FIELD},{REL_FIELD}",
                "$filter": flt,
                "$top": "5000",
            }
            
            try:
                logger.debug(f"fetch_fe_edges_all: querying batch size={len(batch)}")
                rows = svc.read_all(
                    ES_GRAPH_EDGE,
                    sap_client=sap_client,
                    max_pages=max_pages,
                    **query
                )
            except ODataUpstreamError:
                raise
                
            logger.debug(f"fetch_fe_edges_all: retrieved rows={len(rows)}")
            
            for r in rows:
                src = str(r.get(SRC_FIELD, "")).strip()
                dst = str(r.get(DST_FIELD, "")).strip()
                rel = str(r.get(REL_FIELD, "")).strip()
                
                if not src or not dst:
                    continue
                    
                k = (src, dst, rel)
                if k not in edge_seen:
                    edge_seen.add(k)
                    edges.append({"source": src, "target": dst, "rel": rel})
                    
                if dst not in discovered:
                    discovered.add(dst)
                    next_frontier.append(dst)
                    
        frontier = next_frontier
        
    logger.info(f"fetch_fe_edges_all: completed, total edges={len(edges)}")
    return edges
