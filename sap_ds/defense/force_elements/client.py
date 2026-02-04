"""
sap_ds.defense.force_elements.client - High-level Force Element Client
========================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from sap_ds.core.connection import ConnectionContext
    from sap_ds.core.session import SAPODataSession

from sap_ds.defense.force_elements.graph import fetch_fe_edges_all
from sap_ds.defense.force_elements.tree import build_tree_table, build_tree_from_s4
from sap_ds.defense.force_elements.labels import fetch_names_for_ids, deep_link, fetch_single_fe
from sap_ds.defense.force_elements.readiness import fetch_readiness_bulk, apply_readiness_to_tree
from sap_ds.defense.force_elements.symbol import fetch_sidc_bulk, apply_sidc_to_tree, get_sidc_field
from sap_ds.defense.force_elements.hierarchy import (
    fetch_nodes_bulk, fetch_children_bulk, traverse_hierarchy
)
from sap_ds.defense.force_elements.subgraph import slice_subgraph, filter_edges_by_rel
from sap_ds.defense.force_elements.constants import REL_STRUCTURE

logger = logging.getLogger("sap_ds.defense.fe")

GraphSource = Literal["live", "cache"]


class ForceElementClient:
    """
    High-level client for Force Element operations.
    
    Provides methods for:
    - Graph traversal and building
    - Tree table generation
    - Readiness KPI enrichment
    - Military symbol handling
    
    Parameters
    ----------
    connection : ConnectionContext or SAPODataSession
        Active SAP connection
    sap_client : str, optional
        SAP client override
    deeplink_host : str, optional
        Host for generating Fiori deep links
        
    Examples
    --------
    >>> from sap_ds import ConnectionContext
    >>> from sap_ds.defense.force_elements import ForceElementClient
    >>>
    >>> with ConnectionContext() as conn:
    ...     client = ForceElementClient(conn, deeplink_host="s4.example.com")
    ...     
    ...     # Get tree structure
    ...     tree = client.get_tree("FE-001", depth=3)
    ...     
    ...     # Get full graph
    ...     graph = client.get_graph("FE-001", depth=5)
    ...     
    ...     # With readiness data
    ...     tree = client.get_tree("FE-001", depth=3, include_readiness=True)
    """
    
    def __init__(
        self,
        connection: "ConnectionContext | SAPODataSession",
        sap_client: Optional[str] = None,
        deeplink_host: str = "localhost",
    ) -> None:
        from sap_ds.core.connection import ConnectionContext
        from sap_ds.core.session import SAPODataSession
        
        if isinstance(connection, ConnectionContext):
            self._session = connection.session
            self._sap_client = sap_client or connection.sap_client
        elif isinstance(connection, SAPODataSession):
            self._session = connection
            self._sap_client = sap_client or connection.cfg.default_sap_client
        else:
            raise TypeError(
                f"Expected ConnectionContext or SAPODataSession, got {type(connection)}"
            )
            
        self._deeplink_host = deeplink_host
        
    @property
    def session(self) -> "SAPODataSession":
        """The underlying OData session."""
        return self._session
        
    @property
    def sap_client(self) -> Optional[str]:
        """The SAP client being used."""
        return self._sap_client
        
    # -------------------------------------------------------------------------
    # Graph Operations
    # -------------------------------------------------------------------------
    
    def get_graph(
        self,
        root_id: str,
        *,
        depth: int = 3,
        rel_types: Optional[List[str]] = None,
        include_names: bool = True,
    ) -> Dict[str, Any]:
        """
        Get force element graph via BFS traversal.
        
        Parameters
        ----------
        root_id : str
            Root force element ID
        depth : int
            Maximum traversal depth
        rel_types : list of str, optional
            Filter to specific relationship types (e.g., ["B002"])
        include_names : bool
            Whether to resolve names for nodes
            
        Returns
        -------
        dict
            Graph structure:
            {
                "root": str,
                "nodes": [{"id": ..., "name": ...}, ...],
                "edges": [{"source": ..., "target": ..., "rel": ...}, ...],
                "meta": {...}
            }
        """
        root_id = str(root_id).strip()
        
        # Fetch all edges
        edges = fetch_fe_edges_all(
            self._session, root_id,
            depth=depth,
            sap_client=self._sap_client,
        )
        
        # Filter by relationship types if specified
        if rel_types:
            edges = filter_edges_by_rel(edges, rel_types)
            
        # Collect node IDs
        node_ids = {root_id}
        for e in edges:
            node_ids.add(e["source"])
            node_ids.add(e["target"])
            
        # Build nodes
        if include_names:
            names = fetch_names_for_ids(
                self._session, node_ids,
                sap_client=self._sap_client,
            )
        else:
            names = {nid: nid for nid in node_ids}
            
        nodes = [
            {"id": nid, "name": names.get(nid, nid)}
            for nid in sorted(node_ids)
        ]
        
        return {
            "root": root_id,
            "nodes": nodes,
            "edges": edges,
            "meta": {
                "depth": depth,
                "node_count": len(nodes),
                "edge_count": len(edges),
            }
        }
        
    def get_subgraph(
        self,
        focus_id: str,
        edges: List[Dict[str, str]],
        *,
        depth: int = 2,
    ) -> Dict[str, Any]:
        """
        Extract subgraph around a focus node.
        
        Parameters
        ----------
        focus_id : str
            Center node ID
        edges : list of dict
            Full edge list (from get_graph)
        depth : int
            Hops from focus
            
        Returns
        -------
        dict
            Subgraph with node IDs and induced edges
        """
        node_ids, sub_edges = slice_subgraph(focus_id, edges, depth=depth)
        return {
            "focus": focus_id,
            "node_ids": sorted(node_ids),
            "edges": sub_edges,
        }
        
    # -------------------------------------------------------------------------
    # Tree Operations
    # -------------------------------------------------------------------------
    
    def get_tree(
        self,
        root_id: str,
        *,
        depth: int = 3,
        include_readiness: bool = False,
        include_sidc: bool = False,
    ) -> Dict[str, Any]:
        """
        Get force element tree structure.
        
        Uses structural (B002) relationships for parent-child.
        
        Parameters
        ----------
        root_id : str
            Root force element ID
        depth : int
            Maximum depth
        include_readiness : bool
            Whether to fetch and include readiness KPIs
        include_sidc : bool
            Whether to fetch and include military symbols
            
        Returns
        -------
        dict
            Tree structure with nested and flat representations
        """
        root_id = str(root_id).strip()
        
        # Build tree from S/4
        payload = build_tree_from_s4(
            self._session, root_id,
            depth=depth,
            deeplink_host=self._deeplink_host,
            sap_client=self._sap_client,
        )
        
        # Collect all node IDs
        tree = payload.get("tree", {})
        node_ids = {n["id"] for n in tree.get("nodes", [])}
        
        # Enrich with readiness
        if include_readiness and node_ids:
            readiness = fetch_readiness_bulk(
                self._session, node_ids,
                sap_client=self._sap_client,
            )
            apply_readiness_to_tree(payload, readiness)
            
        # Enrich with SIDC
        if include_sidc and node_ids:
            sidcs = fetch_sidc_bulk(
                self._session, node_ids,
                sap_client=self._sap_client,
            )
            apply_sidc_to_tree(payload, sidcs)
            
        return payload
        
    # -------------------------------------------------------------------------
    # Individual Node Operations
    # -------------------------------------------------------------------------
    
    def get_force_element(
        self,
        fe_id: str,
    ) -> Dict[str, str]:
        """
        Get minimal info for a single force element.
        
        Returns
        -------
        dict
            {"id": ..., "name": ..., "url": ...}
        """
        return fetch_single_fe(
            self._session, fe_id,
            sap_client=self._sap_client,
            host=self._deeplink_host,
        )
        
    def get_names(
        self,
        ids: List[str],
    ) -> Dict[str, str]:
        """
        Resolve names for multiple force element IDs.
        """
        return fetch_names_for_ids(
            self._session, ids,
            sap_client=self._sap_client,
        )
        
    def get_readiness(
        self,
        ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get readiness KPIs for multiple force elements.
        """
        return fetch_readiness_bulk(
            self._session, ids,
            sap_client=self._sap_client,
        )
        
    def get_sidcs(
        self,
        ids: List[str],
    ) -> Dict[str, str]:
        """
        Get military symbol codes for multiple force elements.
        """
        return fetch_sidc_bulk(
            self._session, ids,
            sap_client=self._sap_client,
        )
        
    # -------------------------------------------------------------------------
    # Hierarchy Operations
    # -------------------------------------------------------------------------
    
    def get_children(
        self,
        parent_ids: List[str],
        *,
        hierarchy_type: str = "structure",
    ) -> List[Dict[str, Any]]:
        """
        Get children of parent force elements.
        
        Parameters
        ----------
        parent_ids : list of str
            Parent force element IDs
        hierarchy_type : str
            One of: "structure", "peacetime", "wartime", "operation", "exercise"
        """
        return fetch_children_bulk(
            self._session, parent_ids,
            parent_mode=hierarchy_type,
            sap_client=self._sap_client,
        )
        
    def traverse(
        self,
        root_id: str,
        *,
        hierarchy_type: str = "structure",
        max_depth: int = 10,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Traverse hierarchy from root.
        
        Returns all discovered nodes.
        """
        return traverse_hierarchy(
            self._session, root_id,
            parent_mode=hierarchy_type,
            max_depth=max_depth,
            sap_client=self._sap_client,
        )
        
    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------
    
    def deep_link(self, fe_id: str) -> str:
        """Generate Fiori deep link URL for a force element."""
        return deep_link(self._deeplink_host, fe_id)
        
    def probe_sidc_field(self) -> Optional[str]:
        """
        Probe for available SIDC field name.
        
        Returns the field name if found, None otherwise.
        """
        return get_sidc_field(self._session, sap_client=self._sap_client)
