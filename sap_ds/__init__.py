"""
SAP Defense & Security Python SDK (sap_ds)
==========================================

A modular Python package for SAP S/4HANA integration, focusing on
Defense & Security domain functionality alongside generic OData access.

Usage
-----
>>> from sap_ds import ConnectionContext
>>> from sap_ds.defense import ForceElementClient
>>> 
>>> with ConnectionContext() as conn:
...     # Generic OData
...     service = conn.get_service("API_MAINTENANCEORDER_SRV")
...     orders = service.query("A_MaintenanceOrder", top=10)
...     
...     # Force Elements
...     fe_client = ForceElementClient(conn, deeplink_host="s4.example.com")
...     tree = fe_client.get_tree("FE-001", depth=3, include_readiness=True)

Subpackages
-----------
- sap_ds.core: Core session, authentication, and configuration
- sap_ds.odata: Generic OData service and metadata handling
- sap_ds.defense: SAP S/4HANA Defense & Security domain functions
- sap_ds.api: Optional FastAPI REST gateway

"""

__version__ = "0.2.0"
__author__ = "SAP Defense & Security Team"

# Core exports - available at package root
from sap_ds.core.session import (
    ODataAuth,
    ODataConfig,
    SAPODataSession,
    ODataUpstreamError,
)

from sap_ds.core.connection import ConnectionContext

# Convenience re-exports
from sap_ds.odata import ODataService, ODataMetadata

__all__ = [
    # Version
    "__version__",
    # Core
    "ODataAuth",
    "ODataConfig", 
    "SAPODataSession",
    "ODataUpstreamError",
    "ConnectionContext",
    # OData
    "ODataService",
    "ODataMetadata",
]
