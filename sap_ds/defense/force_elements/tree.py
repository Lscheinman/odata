"""
sap_ds.defense.force_elements.tree - Tree table building
=========================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sap_ds.odata.service import escape_odata_literal
from sap_ds.core.session import SAPODataSession
from sap_ds.defense.force_elements.constants import REL_STRUCTURE
from sap_ds.defense.force_elements.graph import fetch_fe_edges_all
from sap_ds.defense.force_elements.labels import fetch_names_for_ids, deep_link

logger = logging.getLogger("sap_ds.defense.fe")


def build_tree_table(
    root_id: str,
    edges_all: List[Dict[str, str]],
    names: Dict[str, str],
    *,
    depth: int,
    deeplink_host: str,
) -> Dict[str, Any]:
    """
    Build tree table structure from edges.
    
    Uses B002 (structural) relationships only for parent-child.
    
    Parameters
    ----------
    root_id : str
        Root force element ID
    edges_all : list of dict
        All edges from graph traversal
    names : dict
        ID -> name mapping
    depth : int
        Maximum depth
    deeplink_host : str
        Host for generating deep links
        
    Returns
    -------
    dict
        Tree structure with flat nodes and nested roots
    """
    logger.info(f"build_tree_table: root_id={root_id}, depth={depth}, edges={len(edges_all)}")
    
    # 1) Build adjacency from B002 only (structural hierarchy)
    adj: Dict[str, List[str]] = {}
    for e in edges_all:
        if (e.get("rel") or "").upper() != REL_STRUCTURE:
            continue
        src = (e.get("source") or "").strip()
        dst = (e.get("target") or "").strip()
        if not src or not dst:
            continue
        adj.setdefault(src, []).append(dst)
        
    # 2) BFS to compute parent/level within depth
    parent: Dict[str, Optional[str]] = {root_id: None}
    level: Dict[str, int] = {root_id: 0}
    q: List[str] = [root_id]
    
    while q:
        cur = q.pop(0)
        cur_lvl = level[cur]
        if cur_lvl >= int(depth):
            continue
        for ch in adj.get(cur, []):
            if ch not in level:
                parent[ch] = cur
                level[ch] = cur_lvl + 1
                q.append(ch)
                
    # 3) Build children lists
    children_ids: Dict[str, List[str]] = {nid: [] for nid in level.keys()}
    for nid, p in parent.items():
        if p is not None:
            children_ids.setdefault(p, []).append(nid)
            
    # Stable ordering
    for k in list(children_ids.keys()):
        children_ids[k] = sorted(children_ids[k])
        
    # 4) Build flat nodes list
    nodes_flat: List[Dict[str, Any]] = []
    for nid in sorted(level.keys(), key=lambda x: (level[x], x)):
        nodes_flat.append({
            "id": nid,
            "name": names.get(nid) or nid,
            "short": "",
            "type": "ORG",
            "parentId": parent.get(nid),
            "level": level[nid],
            "children": children_ids.get(nid, []),
            "s4Url": deep_link(deeplink_host, nid),
            "readiness": {"status": "UNK", "score": 0},
            "iconUrl": "/icons/cache/unit-default.svg",
        })
        
    # Flat lookup
    flat_by_id = {n["id"]: dict(n) for n in nodes_flat}
    
    # Build nested view
    def nest(nid: str) -> Dict[str, Any]:
        n = flat_by_id.get(nid)
        if not n:
            return {"id": nid, "name": names.get(nid) or nid, "type": "ORG", "children": []}
        kids = list(n.get("children") or [])
        out = dict(n)
        out["children"] = [nest(k) for k in kids if k in flat_by_id]
        return out
        
    roots_nested = [nest(root_id)] if root_id in flat_by_id else []
    
    meta = {
        "depth_requested": int(depth),
        "depth_reached": max(level.values()) if level else 0,
        "node_count": len(nodes_flat),
        "struct_rel": REL_STRUCTURE,
        "edge_count_total": len(edges_all),
        "edge_count_struct": sum(
            1 for e in edges_all 
            if (e.get("rel") or "").upper() == REL_STRUCTURE
        ),
    }
    
    return {
        "root": root_id,
        "tree": {
            "roots_ids": [root_id],
            "roots": roots_nested,
            "nodes": nodes_flat,
            "meta": meta,
        },
    }


def build_tree_from_s4(
    session: SAPODataSession,
    root_id: str,
    *,
    depth: int,
    deeplink_host: str,
    sap_client: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build tree by fetching from S/4HANA.
    
    Fetches edges via graph service, resolves names, builds tree.
    
    Parameters
    ----------
    session : SAPODataSession
        Active OData session
    root_id : str
        Root force element ID
    depth : int
        Maximum depth
    deeplink_host : str
        Host for deep links
    sap_client : str, optional
        SAP client override
        
    Returns
    -------
    dict
        Complete tree payload with edges
    """
    logger.info(f"build_tree_from_s4: root_id={root_id}, depth={depth}")
    
    edges_all = fetch_fe_edges_all(
        session, root_id, 
        depth=depth, 
        sap_client=sap_client
    )
    
    # Collect all IDs
    ids = {root_id}
    for e in edges_all:
        ids.add(e["source"])
        ids.add(e["target"])
        
    names = fetch_names_for_ids(session, ids, sap_client=sap_client)
    logger.info(f"build_tree_from_s4: fetched names count={len(names)}")
    
    payload = build_tree_table(
        root_id=root_id,
        edges_all=edges_all,
        names=names,
        depth=depth,
        deeplink_host=deeplink_host,
    )
    
    # Include edges for callers
    payload["edges_all"] = edges_all
    return payload
