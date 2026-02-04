"""
sap_ds.defense.base - Base class for Defense & Security clients
================================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sap_ds.core.connection import ConnectionContext
    from sap_ds.core.session import SAPODataSession

from sap_ds.odata.service import ODataService


class DefenseClient:
    """
    Base class for Defense & Security domain clients.
    
    Provides common functionality for domain-specific clients:
    - Connection management
    - Service caching
    - Common query patterns
    
    Parameters
    ----------
    connection : ConnectionContext or SAPODataSession
        Active connection to SAP
    sap_client : str, optional
        SAP client override
        
    Subclasses should define:
    - SERVICE_NAME: str - The OData service name
    - ENTITY_SETS: dict - Mapping of logical names to entity set names
    """
    
    SERVICE_NAME: str = ""
    ENTITY_SETS: Dict[str, str] = {}
    
    def __init__(
        self,
        connection: "ConnectionContext | SAPODataSession",
        sap_client: Optional[str] = None,
    ) -> None:
        # Handle both ConnectionContext and raw session
        from sap_ds.core.connection import ConnectionContext
        from sap_ds.core.session import SAPODataSession
        
        if isinstance(connection, ConnectionContext):
            self._conn = connection
            self._session = connection.session
            self._sap_client = sap_client or connection.sap_client
        elif isinstance(connection, SAPODataSession):
            self._conn = None
            self._session = connection
            self._sap_client = sap_client or connection.cfg.default_sap_client
        else:
            raise TypeError(
                f"Expected ConnectionContext or SAPODataSession, got {type(connection)}"
            )
        
        self._service: Optional[ODataService] = None
    
    @property
    def service(self) -> ODataService:
        """Get the OData service client (lazy initialization)."""
        if self._service is None:
            if not self.SERVICE_NAME:
                raise NotImplementedError(
                    f"{self.__class__.__name__} must define SERVICE_NAME"
                )
            self._service = ODataService(
                self._session,
                self.SERVICE_NAME,
                default_sap_client=self._sap_client,
            )
        return self._service
    
    def _get_entity_set(self, logical_name: str) -> str:
        """
        Get actual entity set name from logical name.
        
        Parameters
        ----------
        logical_name : str
            Logical name defined in ENTITY_SETS
            
        Returns
        -------
        str
            Actual OData entity set name
        """
        if logical_name in self.ENTITY_SETS:
            return self.ENTITY_SETS[logical_name]
        # If not in mapping, assume it's the actual name
        return logical_name
    
    def list_available_entity_sets(self) -> List[str]:
        """List all entity sets available in the service."""
        return self.service.list_entity_sets()
    
    def list_fields(self, entity_set: str) -> List[str]:
        """List fields for an entity set."""
        return self.service.list_fields(self._get_entity_set(entity_set))
    
    def query(
        self,
        entity_set: str,
        *,
        fields: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        top: Optional[int] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Execute a query against an entity set.
        
        Parameters
        ----------
        entity_set : str
            Entity set name (can be logical name from ENTITY_SETS)
        fields : list of str, optional
            Fields to select
        filter_expr : str, optional
            OData filter expression
        top : int, optional
            Maximum records
        **kwargs
            Additional query parameters
            
        Returns
        -------
        list of dict
            Query results
        """
        return self.service.query(
            self._get_entity_set(entity_set),
            fields=fields,
            filter_expr=filter_expr,
            top=top,
            **kwargs,
        )
