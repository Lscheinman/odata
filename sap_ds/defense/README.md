# sap_ds.defense

SAP S/4HANA Defense & Security domain functionality.

## Overview

This module provides specialized clients for Defense & Security domain operations:

- **Force Elements** - Organizational units, hierarchies, and readiness
- **Base Client** - Abstract base for all D&S domain clients

## Submodules

### `force_elements/`

Complete Force Element operations including:

- Query force elements with filtering
- Build organizational hierarchies (tree structures)
- Network graph relationships
- Readiness data (material, personnel, training)
- Military symbol (SIDC) handling

See [force_elements/README.md](force_elements/README.md) for details.

## Base Client

All domain clients extend `DefenseClient`:

```python
from sap_ds.defense.base import DefenseClient

class MyDomainClient(DefenseClient):
    """Custom domain client."""
    
    SERVICE_NAME = "API_MY_SERVICE_SRV"
    
    ENTITY_SETS = {
        "my_entities": "A_MyEntity",
        "related": "A_RelatedEntity",
    }
    
    def get_my_data(self, top: int = 100):
        return self.query("my_entities", top=top)
```

## Quick Start

```python
from sap_ds import ConnectionContext
from sap_ds.defense import ForceElementClient

with ConnectionContext() as conn:
    # Force Elements
    force = ForceElementClient(conn)
    
    # List all force elements
    elements = force.get_force_elements(top=100)
    
    # Get specific element
    unit = force.get_force_element("50000027")
    
    # Get hierarchy tree
    tree = force.get_tree(
        root_id="50000027",
        depth=3,
        hierarchy_type="structure",
        include_readiness=True,
    )
    
    # Get subordinates
    subs = force.get_subordinates("50000027", recursive=True)
```

## Available Clients

| Client | Service | Description |
|--------|---------|-------------|
| `ForceElementClient` | DFS_FE_FRCELMNTORG_SRV | Force Element organizations |

## OData Services Used

| Service | Description |
|---------|-------------|
| `DFS_FE_FRCELMNTORG_SRV` | Force Element Organization |
| `DFS_FE_FRCELMNTORGNTWKGRAPH_SRV` | Force Element Network Graph |

## Entity Sets

### Force Elements (C_FrcElmntOrgTP)

| Field | Description |
|-------|-------------|
| `ForceElementOrgID` | Unique identifier |
| `FrcElmntOrgName` | Full name |
| `FrcElmntOrgShortName` | Short name |
| `FrcElmntOrgStrucParentID` | Structure parent ID |
| `FrcElmntOrgPeaceTimeParentID` | Peacetime parent ID |
| `FrcElmntOrgWarTimeParentID` | Wartime parent ID |
| `FrcElmntOrgMatlRdnssPct` | Material readiness % |
| `FrcElmntOrgPrsnlRdnssPct` | Personnel readiness % |
| `FrcElmntOrgTrngRdnssPct` | Training readiness % |
| `IsActiveEntity` | Draft status (must filter on this) |

## Creating New Domain Clients

1. Create a new file in `sap_ds/defense/`
2. Extend `DefenseClient`
3. Define service name and entity sets
4. Implement domain-specific methods

```python
from sap_ds.defense.base import DefenseClient

class EquipmentClient(DefenseClient):
    SERVICE_NAME = "API_EQUIPMENT_SRV"
    
    ENTITY_SETS = {
        "equipment": "A_Equipment",
        "equipment_text": "A_EquipmentText",
    }
    
    def get_equipment(self, plant: str = None, top: int = 100):
        filter_expr = f"Plant eq '{plant}'" if plant else None
        return self.query("equipment", filter_expr=filter_expr, top=top)
    
    def get_equipment_by_id(self, equipment_id: str):
        return self.read_by_key("equipment", equipment_id)
```

## Future Domain Clients

Planned additions:

- `PersonnelClient` - Personnel positions and assignments
- `EquipmentClient` - Equipment and material
- `OperationClient` - Operations and exercises
- `ReadinessClient` - Readiness reporting
