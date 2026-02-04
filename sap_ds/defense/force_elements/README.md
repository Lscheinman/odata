# sap_ds.defense.force_elements

Force Element operations for SAP S/4HANA Defense & Security.

## Overview

This module provides comprehensive Force Element functionality:

- **Query** - List and search force elements
- **Hierarchy** - Build organizational trees
- **Graph** - Network relationship graphs
- **Readiness** - Material, personnel, and training readiness
- **Symbols** - Military symbol (SIDC) handling

## Files

| File | Description |
|------|-------------|
| `client.py` | Main ForceElementClient class |
| `constants.py` | Service names, entity sets, parent fields |
| `tree.py` | Hierarchical tree builder |
| `hierarchy.py` | Hierarchy utilities |
| `graph.py` | Network graph operations |
| `subgraph.py` | Subgraph extraction |
| `readiness.py` | Readiness calculations |
| `labels.py` | Label formatting utilities |
| `symbol.py` | Military symbol (SIDC) handling |

## Quick Start

```python
from sap_ds import ConnectionContext
from sap_ds.defense import ForceElementClient

with ConnectionContext() as conn:
    force = ForceElementClient(conn)
    
    # List force elements
    elements = force.get_force_elements(top=100)
    
    # Get by ID
    unit = force.get_force_element("50000027")
    
    # Get tree
    tree = force.get_tree("50000027", depth=3)
```

## ForceElementClient Methods

### Query Methods

```python
# List all force elements
elements = force.get_force_elements(
    top=100,
    filter_expr="startswith(FrcElmntOrgName, 'Division')",
    fields=["ForceElementOrgID", "FrcElmntOrgName"],
)

# Get single element
unit = force.get_force_element("50000027")

# Get subordinates
subs = force.get_subordinates(
    parent_id="50000027",
    hierarchy_type="structure",  # or "peacetime", "wartime"
    recursive=True,
)
```

### Hierarchy Methods

```python
# Build tree
tree = force.get_tree(
    root_id="50000027",
    depth=3,
    hierarchy_type="structure",
    include_readiness=True,
    include_sidc=True,
)

# Get hierarchy path
path = force.get_hierarchy_path("50000030")  # Returns [parent, ..., root]
```

### Graph Methods

```python
# Get network graph
graph = force.get_graph(
    node_ids=["50000027", "50000028"],
    relationship_types=["structure", "peacetime"],
)

# Get subgraph around a node
subgraph = force.get_subgraph(
    center_id="50000027",
    radius=2,
)
```

### Readiness Methods

```python
# Get readiness for a unit
readiness = force.get_readiness("50000027")
# Returns: {
#   "material": 85,
#   "personnel": 92,
#   "training": 78,
#   "overall": 85,
# }

# Get readiness for multiple units
batch = force.get_readiness_batch(["50000027", "50000028", "50000029"])
```

## Hierarchy Types

| Type | Parent Field | Description |
|------|--------------|-------------|
| `structure` | `FrcElmntOrgStrucParentID` | Organizational structure |
| `peacetime` | `FrcElmntOrgPeaceTimeParentID` | Peacetime assignments |
| `wartime` | `FrcElmntOrgWarTimeParentID` | Wartime assignments |
| `operation` | `FrcElmntOrgOplAssgmtParentID` | Operational assignments |
| `exercise` | `FrcElmntOrgExerAssgmtParentID` | Exercise assignments |

## Constants

```python
from sap_ds.defense.force_elements.constants import (
    SERVICE_NAME,      # "DFS_FE_FRCELMNTORG_SRV"
    ENTITY_SET,        # "C_FrcElmntOrgTP"
    GRAPH_SERVICE,     # "DFS_FE_FRCELMNTORGNTWKGRAPH_SRV"
    PARENT_FIELDS,     # Mapping of hierarchy type to parent field
)
```

## Tested IDs

Confirmed working in sandbox:

| ID | Name | Notes |
|----|------|-------|
| 50000026 | World | Root element |
| 50000027 | SandBox Org Structure | Structure root |
| 50000028 | SandBox 1st DIV | Division |
| 50000029 | SandBox 2nd DIV | Division (Active status) |
| 50000030 | Sandbox TRANSCOM Unit | Transport unit |

## Important Notes

### Draft-Enabled Entity

`C_FrcElmntOrgTP` is a draft-enabled entity requiring:

1. **IsActiveEntity filter**: Always include `IsActiveEntity eq true`
2. **No $orderby**: Ordering causes empty results
3. **validate_fields=False**: Avoid field validation issues

```python
# Internal query pattern used
items = service.query(
    "C_FrcElmntOrgTP",
    filter_expr="IsActiveEntity eq true",
    validate_fields=False,
)
```

### Fields Reference

Key fields for common operations:

```python
# Identification
"ForceElementOrgID"
"FrcElmntOrgName"
"FrcElmntOrgShortName"

# Hierarchy
"FrcElmntOrgStrucParentID"
"FrcElmntOrgPeaceTimeParentID"
"FrcElmntOrgWarTimeParentID"

# Readiness
"FrcElmntOrgMatlRdnssPct"
"FrcElmntOrgPrsnlRdnssPct"
"FrcElmntOrgTrngRdnssPct"

# Status
"FrcElmntOrgPlngStatus"
"FrcElmntOrgPlngStatusName"
"IsActiveEntity"

# Symbols
"FrcElmntOrgSymbol"
```
