"""
sap_ds.defense.force_elements - Force Elements Client
======================================================

Comprehensive client for SAP S/4HANA Defense & Security Force Elements.

Features:
- Graph traversal (BFS) for organizational relationships
- Tree building with multiple hierarchy types
- Readiness KPIs (material, personnel, training)
- Military symbol (SIDC) support
- Optional HANA caching

Usage:
    from sap_ds import ConnectionContext
    from sap_ds.defense.force_elements import ForceElementClient

    with ConnectionContext() as conn:
        client = ForceElementClient(conn)
        tree = client.get_tree(root_id="FE-001", depth=3)
        graph = client.get_graph(root_id="FE-001", depth=5)
"""

from sap_ds.defense.force_elements.client import ForceElementClient
from sap_ds.defense.force_elements.graph import fetch_fe_edges_all
from sap_ds.defense.force_elements.tree import build_tree_table, build_tree_from_s4
from sap_ds.defense.force_elements.labels import fetch_names_for_ids, deep_link
from sap_ds.defense.force_elements.readiness import fetch_readiness_bulk, apply_readiness_to_tree
from sap_ds.defense.force_elements.symbol import fetch_sidc_bulk, apply_sidc_to_tree
from sap_ds.defense.force_elements.hierarchy import fetch_nodes_bulk, fetch_children_bulk
from sap_ds.defense.force_elements.subgraph import slice_subgraph

# Convenience aliases for common use cases
get_descendants_bfs = fetch_fe_edges_all  # BFS traversal via graph service
build_tree = build_tree_table  # Build tree from edges
collect_readiness = fetch_readiness_bulk  # Fetch readiness KPIs
fetch_sidcs = fetch_sidc_bulk  # Fetch military symbols

__all__ = [
    # Main client
    "ForceElementClient",
    # Graph traversal
    "fetch_fe_edges_all",
    "get_descendants_bfs",  # alias
    # Tree building
    "build_tree_table",
    "build_tree",  # alias
    "build_tree_from_s4",
    # Labels & names
    "fetch_names_for_ids",
    "deep_link",
    # Readiness KPIs
    "fetch_readiness_bulk",
    "collect_readiness",  # alias
    "apply_readiness_to_tree",
    # Military symbols
    "fetch_sidc_bulk",
    "fetch_sidcs",  # alias
    "apply_sidc_to_tree",
    # Hierarchy traversal
    "fetch_nodes_bulk",
    "fetch_children_bulk",
    # Subgraph utilities
    "slice_subgraph",
]
