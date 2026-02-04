"""
sap_ds.defense - SAP S/4HANA Defense & Security Domain
=======================================================

This module provides specialized clients for SAP S/4HANA Defense & Security
functionality, including:

- Force Elements management (graph, tree, hierarchy)
- Readiness KPIs
- Military symbols (SIDC)
- Personnel management (planned)
- Equipment and assets (planned)

Usage
-----
>>> from sap_ds import ConnectionContext
>>> from sap_ds.defense import ForceElementClient
>>>
>>> with ConnectionContext() as conn:
...     client = ForceElementClient(conn, deeplink_host="s4.example.com")
...     tree = client.get_tree("FE-001", depth=3, include_readiness=True)
...     graph = client.get_graph("FE-001", depth=5)

Available Clients
-----------------
- ForceElementClient: Force structure, graphs, trees, readiness, symbols
- DefenseClient: Base class for domain clients (for extension)

"""

from sap_ds.defense.base import DefenseClient
from sap_ds.defense.force_elements import ForceElementClient

__all__ = [
    "DefenseClient",
    "ForceElementClient",
]
