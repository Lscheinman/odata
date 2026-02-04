"""
sap_ds.core - Core connectivity and authentication
===================================================

This module provides the foundational classes for connecting to SAP systems:

- ODataAuth: Authentication configuration (basic or bearer token)
- ODataConfig: Full connection configuration
- SAPODataSession: Low-level HTTP session with retry, CSRF handling
- ConnectionContext: High-level connection manager (hana_ml style)

"""

from sap_ds.core.session import (
    ODataAuth,
    ODataConfig,
    SAPODataSession,
    ODataUpstreamError,
)

from sap_ds.core.connection import ConnectionContext

__all__ = [
    "ODataAuth",
    "ODataConfig",
    "SAPODataSession",
    "ODataUpstreamError",
    "ConnectionContext",
]
