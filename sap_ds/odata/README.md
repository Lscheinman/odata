# sap_ds.odata

Generic OData service access and metadata handling.

## Overview

This module provides flexible OData operations for any SAP OData service:

- **Service Access** - Query any entity set with filtering, sorting, and paging
- **Metadata Parsing** - Parse and cache $metadata for field validation
- **Field Validation** - Validate $select fields against schema
- **Automatic Paging** - Follow `__next` links for large result sets

## Components

### `service.py`

Main OData service client.

```python
from sap_ds.odata import ODataService

# Create service (requires session from core module)
service = ODataService(session, "API_MAINTENANCEORDER_SRV")

# Discover available data
entity_sets = service.list_entity_sets()
fields = service.list_fields("A_MaintenanceOrder")

# Query with all options
orders = service.query(
    "A_MaintenanceOrder",
    fields=["MaintenanceOrder", "OrderType", "CompanyCode"],
    filter_expr="CompanyCode eq '1000'",
    orderby="MaintenanceOrder desc",
    top=100,
    skip=0,
    expand="to_WorkOrder",
    max_pages=5,
    validate_fields=True,
)
```

### `metadata.py`

Metadata parsing and caching.

```python
from sap_ds.odata import ODataMetadata

# Parse metadata XML
meta = ODataMetadata(metadata_xml_string)

# Get entity sets
entity_sets = meta.entity_sets()

# Get properties for an entity
properties = meta.properties("A_MaintenanceOrder")

# Validate fields
valid_fields, unknown_fields = meta.validate_select(
    "A_MaintenanceOrder",
    ["MaintenanceOrder", "InvalidField"]
)
```

## ODataService Methods

### Query Methods

| Method | Description |
|--------|-------------|
| `query(entity_set, **kwargs)` | Flexible query with all OData options |
| `read_all(entity_set, **params)` | Raw query with automatic paging |
| `read_by_key(entity_set, key)` | Read single entity by key |

### Discovery Methods

| Method | Description |
|--------|-------------|
| `list_entity_sets()` | List all entity sets in service |
| `list_fields(entity_set)` | List all fields for an entity |

## Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `fields` | list | Fields for $select |
| `filter_expr` | str | Raw $filter expression |
| `orderby` | str | $orderby expression |
| `top` | int | Max records per page |
| `skip` | int | Records to skip |
| `expand` | str | $expand for related entities |
| `max_pages` | int | Max pages to follow |
| `validate_fields` | bool | Validate against $metadata |
| `extra_params` | dict | Additional OData parameters |

## OData Filter Examples

```python
# Equals
filter_expr="CompanyCode eq '1000'"

# Greater than
filter_expr="CreatedDate gt datetime'2024-01-01T00:00:00'"

# Contains (substringof)
filter_expr="substringof('search', Description)"

# Starts with
filter_expr="startswith(Name, 'ABC')"

# Multiple conditions
filter_expr="CompanyCode eq '1000' and Status eq 'OPEN'"

# Draft entities (required for draft-enabled entities)
filter_expr="IsActiveEntity eq true"
```

## Metadata Caching

Metadata is cached by service name with configurable TTL:

```python
# Configure via environment
ODATA_META_TTL=900  # 15 minutes

# Or programmatically
service = ODataService(session, "API_SERVICE", meta_ttl=600)
```

## Error Handling

```python
from sap_ds.core.session import ODataUpstreamError

try:
    data = service.query("EntitySet", filter_expr="bad filter")
except ODataUpstreamError as e:
    print(f"SAP returned {e.status}: {e.message}")
    print(f"URL: {e.url}")
```

## Notes on Draft-Enabled Entities

SAP draft-enabled entities (like Force Elements) require special handling:

1. **Filter Required**: Must include `IsActiveEntity eq true` to get active records
2. **No OrderBy**: Some draft entities don't support $orderby
3. **Complex Keys**: Entity keys include `DraftUUID` and `IsActiveEntity`

```python
# Correct query for draft entity
items = service.query(
    "C_FrcElmntOrgTP",
    filter_expr="IsActiveEntity eq true",
    validate_fields=False,  # Avoid validation issues
)
```
