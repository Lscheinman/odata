# SAP Defense & Security Python SDK (sap-ds)

A modular Python package for SAP S/4HANA integration, focusing on Defense & Security domain functionality alongside generic OData access.

## Features

- **Generic OData Access**: Query any SAP OData v2/v4 service with automatic paging, field validation, and CSRF handling
- **Defense & Security Domain**: Specialized clients for Force Elements, Personnel, Equipment, and more
- **hana_ml-style API**: Familiar interface for SAP HANA ML users
- **Optional REST Gateway**: FastAPI-based microservice for exposing OData via REST
- **Fully Testable**: Modular design enables easy mocking and testing

## Installation

### From source (development)

```bash
# Clone the repository
git clone https://github.com/sap/sap-ds-python.git
cd sap-ds-python

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# With API gateway support
pip install -e ".[all]"
```

### From PyPI (when published)

```bash
# Core package
pip install sap-ds

# With API gateway
pip install sap-ds[api]

# With all extras
pip install sap-ds[all]
```

## Quick Start

### Basic OData Query

```python
from sap_ds import ODataConfig, ODataAuth, SAPODataSession
from sap_ds.odata import ODataService

# Configure connection
cfg = ODataConfig(
    base_url="https://your-s4.example.com/sap/opu/odata/sap/",
    auth=ODataAuth("basic", ("USER", "PASSWORD")),
    default_sap_client="100",
)

# Query OData service
with SAPODataSession(cfg) as sess:
    api = ODataService(sess, "API_MAINTENANCEORDER_SRV")
    
    # Discover available data
    print(api.list_entity_sets())
    print(api.list_fields("A_MaintenanceOrder"))
    
    # Execute query
    orders = api.query(
        "A_MaintenanceOrder",
        fields=["MaintenanceOrder", "OrderType", "CompanyCode"],
        filter_expr="CompanyCode eq '1000'",
        top=50,
        orderby="MaintenanceOrder desc",
    )
    print(f"Found {len(orders)} orders")
```

### Using ConnectionContext (hana_ml style)

```python
from sap_ds import ConnectionContext

# Using environment variables (S4_BASE_URL, S4_USER, S4_PASS, S4_SAP_CLIENT)
with ConnectionContext() as conn:
    service = conn.get_service("API_MAINTENANCEORDER_SRV")
    orders = service.query("A_MaintenanceOrder", top=10)

# Or with explicit parameters
with ConnectionContext(
    base_url="https://s4.example.com/sap/opu/odata/sap/",
    user="USER",
    password="PASS",
    sap_client="100",
) as conn:
    service = conn.get_service("API_MAINTENANCEORDER_SRV")
```

### Defense & Security: Force Elements

```python
from sap_ds import ConnectionContext
from sap_ds.defense import ForceElementClient

with ConnectionContext() as conn:
    force = ForceElementClient(conn)
    
    # Get all force elements
    elements = force.get_force_elements(top=100)
    
    # Get specific unit
    unit = force.get_force_element("UNIT-001")
    
    # Get subordinate units
    subordinates = force.get_subordinates("PARENT-001", recursive=True)
    
    # Get hierarchy
    hierarchy = force.get_hierarchy(root_id="ROOT-001")
    
    # Get personnel and equipment
    personnel = force.get_personnel("UNIT-001")
    equipment = force.get_equipment("UNIT-001")
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `S4_BASE_URL` | OData base URL | Yes |
| `S4_USER` | Basic auth username | Yes* |
| `S4_PASS` | Basic auth password | Yes* |
| `S4_BEARER_TOKEN` | Bearer token (alternative to user/pass) | Yes* |
| `S4_SAP_CLIENT` | Default SAP client | No |
| `S4_VERIFY_TLS` | Verify TLS certificates (default: true) | No |

\* Either user/pass or bearer token is required

## Running the API Gateway

```bash
# Set environment variables
export S4_BASE_URL="https://your-s4.example.com/sap/opu/odata/sap/"
export S4_USER="user"
export S4_PASS="password"
export S4_SAP_CLIENT="100"
export ODATA_API_KEY="your-api-key"

# Run the gateway
python -m sap_ds.api

# Or with uvicorn directly
uvicorn sap_ds.api:app --host 0.0.0.0 --port 5050
```

API documentation available at `http://localhost:5050/docs`

## Package Structure

```
sap_ds/
├── __init__.py          # Main exports
├── core/                # Core connectivity
│   ├── session.py       # HTTP session, auth, retry
│   └── connection.py    # High-level ConnectionContext
├── odata/               # Generic OData
│   ├── service.py       # Query builder
│   └── metadata.py      # $metadata parsing
├── defense/             # Defense & Security domain
│   ├── base.py          # Base client class
│   └── force_elements.py # Force Elements client
└── api/                 # Optional REST gateway
    ├── gateway.py       # FastAPI app
    └── models.py        # Pydantic models
```

## Adding New Domain Clients

Create new clients by extending `DefenseClient`:

```python
from sap_ds.defense.base import DefenseClient

class MyDomainClient(DefenseClient):
    SERVICE_NAME = "API_MY_SERVICE_SRV"
    
    ENTITY_SETS = {
        "my_entities": "A_MyEntity",
    }
    
    def get_my_data(self, **kwargs):
        return self.query("my_entities", **kwargs)
```

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=sap_ds --cov-report=html

# Run specific test file
pytest tests/test_odata.py -v
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Format code
black sap_ds tests
ruff check sap_ds tests --fix

# Type checking
mypy sap_ds
```

## License

Apache License 2.0
