"""
sap_ds.defense.force_elements.subgraph - Subgraph slicing utilities
=====================================================================
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple


def slice_subgraph(
    focus_id: str,
    edges: List[Dict[str, str]],
    *,
    depth: int = 2,
) -> Tuple[Set[str], List[Dict[str, str]]]:
    """
    Extract a subgraph centered on focus_id within depth hops.
    
    Uses undirected adjacency for "neighborhood" slicing.
    
    Parameters
    ----------
    focus_id : str
        Center node ID
    edges : list of dict
        All edges with "source" and "target" keys
    depth : int
        Number of hops from focus
        
    Returns
    -------
    tuple of (set, list)
        (node IDs in subgraph, induced edges)
    """
    # Build undirected adjacency
    neigh: Dict[str, Set[str]] = {}
    for e in edges:
        a = e["source"]
        b = e["target"]
        neigh.setdefault(a, set()).add(b)
        neigh.setdefault(b, set()).add(a)
        
    visited: Set[str] = {focus_id}
    frontier: Set[str] = {focus_id}
    
    for _ in range(depth):
        nxt: Set[str] = set()
        for n in frontier:
            for m in neigh.get(n, set()):
                if m not in visited:
                    visited.add(m)
                    nxt.add(m)
        frontier = nxt
        if not frontier:
            break
            
    # Induced edges
    sub_edges = [
        e for e in edges 
        if e["source"] in visited and e["target"] in visited
    ]
    
    return visited, sub_edges


def filter_edges_by_rel(
    edges: List[Dict[str, str]],
    rel_types: List[str],
) -> List[Dict[str, str]]:
    """
    Filter edges to only include specified relationship types.
    
    Parameters
    ----------
    edges : list of dict
        Edges with "rel" key
    rel_types : list of str
        Allowed relationship type codes
        
    Returns
    -------
    list of dict
        Filtered edges
    """
    allowed = {r.upper() for r in rel_types}
    return [
        e for e in edges 
        if (e.get("rel") or "").upper() in allowed
    ]
