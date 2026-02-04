"""
sap_ds.odata.service - OData Service Client
=============================================

Service-scoped query client for SAP OData services.
"""

from __future__ import annotations

from typing import Any, Dict, Generator, List, Optional, Sequence

from sap_ds.core.session import SAPODataSession
from sap_ds.odata.metadata import ODataMetadata


def escape_odata_literal(value: str) -> str:
    """
    Escape a string value for use in OData $filter expressions.
    
    Parameters
    ----------
    value : str
        The value to escape
        
    Returns
    -------
    str
        Escaped value safe for OData filters
        
    Examples
    --------
    >>> escape_odata_literal("O'Brien")
    "O''Brien"
    """
    return value.replace("'", "''")


def _join_csv(items: Sequence[str]) -> str:
    """Join items as comma-separated values, stripping whitespace."""
    return ",".join([s.strip() for s in items if s and s.strip()])


class ODataService:
    """
    Service-scoped OData query client.
    
    Provides methods for querying entity sets with automatic paging,
    field validation, and query building.
    
    Parameters
    ----------
    sess : SAPODataSession
        Active OData session
    service : str
        Service technical name
    default_sap_client : str, optional
        Default SAP client override
        
    Examples
    --------
    >>> with SAPODataSession(cfg) as sess:
    ...     api = ODataService(sess, "API_MAINTENANCEORDER_SRV")
    ...     
    ...     # Discover available entity sets
    ...     print(api.list_entity_sets())
    ...     
    ...     # Query with field selection and filter
    ...     orders = api.query(
    ...         "A_MaintenanceOrder",
    ...         fields=["MaintenanceOrder", "OrderType"],
    ...         filter_expr="CompanyCode eq '1000'",
    ...         top=50
    ...     )
    """

    def __init__(
        self,
        sess: SAPODataSession,
        service: str,
        *,
        default_sap_client: Optional[str] = None,
    ) -> None:
        self.sess = sess
        self.service = service
        self.default_sap_client = default_sap_client
        self.meta = ODataMetadata(sess, service, sap_client=default_sap_client)

    # ---------------- core reads ----------------

    def read(
        self,
        entity_set: str,
        *,
        sap_client: Optional[str] = None,
        **query: str
    ) -> List[Dict[str, Any]]:
        """
        Read a single page of results from an entity set.
        
        Parameters
        ----------
        entity_set : str
            Entity set name
        sap_client : str, optional
            SAP client override
        **query
            Additional OData query parameters
            
        Returns
        -------
        list of dict
            List of entity records
        """
        payload = self.sess.get(
            self.service,
            entity_set,
            params=query,
            sap_client=sap_client or self.default_sap_client
        )
        return payload.get("d", {}).get("results") or payload.get("value") or []

    def iterate(
        self,
        entity_set: str,
        *,
        sap_client: Optional[str] = None,
        max_pages: Optional[int] = None,
        **query: str,
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Iterate through pages of results.
        
        Yields each page as a list of records, following OData __next links.
        
        Parameters
        ----------
        entity_set : str
            Entity set name
        sap_client : str, optional
            SAP client override
        max_pages : int, optional
            Maximum number of pages to fetch
        **query
            Additional OData query parameters
            
        Yields
        ------
        list of dict
            Each page of entity records
        """
        sap = sap_client or self.default_sap_client
        p = self.sess.get(self.service, entity_set, params=query, sap_client=sap)

        yielded = 0
        first = p.get("d", {}).get("results") or p.get("value") or []
        if first:
            yield first
            yielded += 1
            if max_pages is not None and yielded >= int(max_pages):
                return

        next_link = p.get("d", {}).get("__next") or p.get("@odata.nextLink")
        seen = set()

        while next_link:
            if next_link in seen:
                return
            seen.add(next_link)

            r = self.sess.session.get(
                next_link,
                timeout=self.sess.timeout,
                verify=self.sess.verify
            )
            self.sess._raise_for_error(r, next_link)
            p = r.json()

            chunk = p.get("d", {}).get("results") or p.get("value") or []
            if chunk:
                yield chunk
                yielded += 1
                if max_pages is not None and yielded >= int(max_pages):
                    return

            next_link = p.get("d", {}).get("__next") or p.get("@odata.nextLink")

    def read_all(
        self,
        entity_set: str,
        *,
        sap_client: Optional[str] = None,
        max_pages: Optional[int] = None,
        **query: str,
    ) -> List[Dict[str, Any]]:
        """
        Read all pages of results into a single list.
        
        Parameters
        ----------
        entity_set : str
            Entity set name
        sap_client : str, optional
            SAP client override
        max_pages : int, optional
            Maximum number of pages to fetch
        **query
            Additional OData query parameters
            
        Returns
        -------
        list of dict
            All entity records across pages
        """
        out: List[Dict[str, Any]] = []
        for page in self.iterate(
            entity_set,
            sap_client=sap_client,
            max_pages=max_pages,
            **query
        ):
            out.extend(page)
        return out

    # ---------------- generic query builder ----------------

    def query(
        self,
        entity_set: str,
        *,
        fields: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        orderby: Optional[str] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        expand: Optional[str] = None,
        sap_client: Optional[str] = None,
        max_pages: Optional[int] = None,
        validate_fields: bool = True,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a flexible query against an entity set.
        
        Supports field selection, filtering, sorting, paging, and
        optional field validation against $metadata.
        
        Parameters
        ----------
        entity_set : str
            Entity set name
        fields : list of str, optional
            Fields for $select
        filter_expr : str, optional
            Raw $filter expression
        orderby : str, optional
            $orderby expression
        top : int, optional
            Maximum records per page ($top)
        skip : int, optional
            Records to skip ($skip)
        expand : str, optional
            $expand for related entities
        sap_client : str, optional
            SAP client override
        max_pages : int, optional
            Maximum pages to follow
        validate_fields : bool
            If True, validate fields against $metadata
        extra_params : dict, optional
            Additional OData parameters
            
        Returns
        -------
        list of dict
            Query results
            
        Examples
        --------
        >>> orders = service.query(
        ...     "A_MaintenanceOrder",
        ...     fields=["MaintenanceOrder", "OrderType", "CompanyCode"],
        ...     filter_expr="CompanyCode eq '1000'",
        ...     orderby="MaintenanceOrder desc",
        ...     top=100,
        ...     max_pages=5,
        ... )
        """
        params: Dict[str, str] = {}
        if extra_params:
            params.update(extra_params)

        if fields:
            use_fields = fields
            if validate_fields:
                valid, unknown = self.meta.validate_select(entity_set, fields)
                use_fields = valid
                # Unknown fields are silently dropped (can be logged if needed)
            if use_fields:
                params["$select"] = _join_csv(use_fields)

        if filter_expr:
            params["$filter"] = filter_expr
        if orderby:
            params["$orderby"] = orderby
        if expand:
            params["$expand"] = expand
        if top is not None:
            params["$top"] = str(int(top))
        if skip is not None:
            params["$skip"] = str(int(skip))

        return self.read_all(
            entity_set,
            sap_client=sap_client,
            max_pages=max_pages,
            **params
        )

    # ---------------- discovery helpers ----------------

    def list_entity_sets(self) -> List[str]:
        """
        List all entity sets available in this service.
        
        Returns
        -------
        list of str
            Entity set names
        """
        return self.meta.entity_sets()

    def list_fields(self, entity_set: str) -> List[str]:
        """
        List all fields/properties for an entity set.
        
        Parameters
        ----------
        entity_set : str
            Entity set name
            
        Returns
        -------
        list of str
            Field/property names
        """
        return self.meta.properties(entity_set)
