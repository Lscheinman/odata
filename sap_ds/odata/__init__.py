"""
sap_ds.odata - Generic OData Service Access
============================================

This module provides generic OData v2/v4 service access:

- ODataService: Query builder and entity set access
- ODataMetadata: $metadata parsing and field validation
- Helper utilities for OData query construction

"""

from sap_ds.odata.service import ODataService, escape_odata_literal
from sap_ds.odata.metadata import ODataMetadata, EntitySetInfo

__all__ = [
    "ODataService",
    "ODataMetadata",
    "EntitySetInfo",
    "escape_odata_literal",
]
