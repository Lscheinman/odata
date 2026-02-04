"""
sap_ds.core.connection - High-level connection management
==========================================================

Provides a hana_ml-style ConnectionContext for simplified usage.
"""

from __future__ import annotations

import os
from typing import Optional, Union, Tuple

from sap_ds.core.session import ODataAuth, ODataConfig, SAPODataSession
from service import ODataService


class ConnectionContext:
    """
    High-level connection manager for SAP OData services.
    
    Provides a simplified interface similar to hana_ml.ConnectionContext.
    Supports environment variable configuration and context manager usage.
    
    Parameters
    ----------
    base_url : str, optional
        OData base URL. Falls back to S4_BASE_URL env var.
    user : str, optional
        Username for basic auth. Falls back to S4_USER env var.
    password : str, optional
        Password for basic auth. Falls back to S4_PASS env var.
    bearer_token : str, optional
        Bearer token for OAuth. Falls back to S4_BEARER_TOKEN env var.
    sap_client : str, optional
        Default SAP client. Falls back to S4_SAP_CLIENT env var.
    verify : bool, optional
        SSL verification. Falls back to S4_VERIFY_TLS env var.
    timeout : float
        Request timeout in seconds.
        
    Examples
    --------
    >>> # Using explicit credentials
    >>> conn = ConnectionContext(
    ...     base_url="https://s4.example.com/sap/opu/odata/sap/",
    ...     user="USER",
    ...     password="PASS",
    ...     sap_client="100"
    ... )
    
    >>> # Using environment variables
    >>> conn = ConnectionContext()  # reads from S4_* env vars
    
    >>> # As context manager
    >>> with ConnectionContext() as conn:
    ...     service = conn.get_service("API_MAINTENANCEORDER_SRV")
    ...     orders = service.query("A_MaintenanceOrder", top=10)
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sap_client: Optional[str] = None,
        verify: Optional[bool] = None,
        timeout: float = 60.0,
    ) -> None:
        # Resolve from environment if not provided
        self._base_url = (base_url or os.environ.get("S4_BASE_URL", "")).rstrip("/") + "/"
        self._user = user or os.environ.get("S4_USER", "")
        self._password = password or os.environ.get("S4_PASS", "")
        self._bearer_token = bearer_token or os.environ.get("S4_BEARER_TOKEN", "")
        self._sap_client = sap_client or os.environ.get("S4_SAP_CLIENT")
        
        if verify is not None:
            self._verify = verify
        else:
            self._verify = os.environ.get("S4_VERIFY_TLS", "true").lower() != "false"
            
        self._timeout = timeout
        
        # Validate configuration
        if not self._base_url or self._base_url == "/":
            raise ValueError(
                "Missing base_url. Set S4_BASE_URL environment variable "
                "or pass base_url parameter."
            )
            
        if not self._bearer_token and not (self._user and self._password):
            raise ValueError(
                "Missing credentials. Set S4_USER/S4_PASS or S4_BEARER_TOKEN "
                "environment variables, or pass user/password or bearer_token parameters."
            )
        
        # Build session
        self._session: Optional[SAPODataSession] = None
        
    @property
    def session(self) -> SAPODataSession:
        """Get or create the underlying OData session."""
        if self._session is None:
            self._session = self._build_session()
        return self._session
    
    def _build_session(self) -> SAPODataSession:
        if self._bearer_token:
            auth = ODataAuth("bearer", self._bearer_token)
        else:
            auth = ODataAuth("basic", (self._user, self._password))
            
        cfg = ODataConfig(
            base_url=self._base_url,
            auth=auth,
            default_sap_client=self._sap_client,
            verify=self._verify,
            timeout=self._timeout,
        )
        return SAPODataSession(cfg)
    
    def close(self) -> None:
        """Close the connection."""
        if self._session is not None:
            self._session.close()
            self._session = None
            
    def __enter__(self) -> "ConnectionContext":
        return self
    
    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
        
    def get_service(self, service_name: str) -> "ODataService":
        """
        Get an ODataService instance for the given service name.
        
        Parameters
        ----------
        service_name : str
            Technical name of the OData service, e.g. "API_MAINTENANCEORDER_SRV"
            
        Returns
        -------
        ODataService
            Service client for querying entity sets
        """
        # Import here to avoid circular imports
        from sap_ds.odata.service import ODataService
        return ODataService(self.session, service_name, default_sap_client=self._sap_client)
    
    @property
    def base_url(self) -> str:
        """The configured base URL."""
        return self._base_url
    
    @property
    def sap_client(self) -> Optional[str]:
        """The configured SAP client."""
        return self._sap_client
