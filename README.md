# SAP Defense & Security Python SDK (`sap_ds`)

A modular Python package for SAP S/4HANA integration, focusing on Defense & Security domain functionality alongside generic OData access. Designed to be imported and used like `hana_ml`.

## Features

- ✅ **Generic OData Access** - Query any SAP OData service
- ✅ **Force Elements** - Full support for SAP D&S Force Element operations
- ✅ **REST API Gateway** - Optional FastAPI-based REST gateway with Swagger UI
- ✅ **Draft-Enabled Entity Support** - Properly handles SAP draft entities
- ✅ **Metadata Caching** - Efficient $metadata caching with configurable TTL
- ✅ **Hierarchical Queries** - Tree and graph operations for Force Elements

## Installation

```bash
# Install in development mode
pip install -e ".[all]"

# Or just the core (no API dependencies)
pip install -e .
```

## Quick Start

### As a Python Library

```python
from sap_ds import ConnectionContext, ODataService
from sap_ds.defense import ForceElementClient

# Using environment variables from .env
with ConnectionContext() as conn:
    # Generic OData query
    service = conn.get_service("API_MAINTENANCEORDER_SRV")
    orders = service.query("A_MaintenanceOrder", top=10)
    
    # Force Elements
    force = ForceElementClient(conn)
    elements = force.get_force_elements(top=100)
    tree = force.get_tree("50000027", depth=3)
```

### As a REST API

```bash
# Start the API server
python -m sap_ds.api

# Or with uvicorn directly
uvicorn sap_ds.api:app --host 0.0.0.0 --port 8000 --reload
```

Then open http://localhost:8000/docs for Swagger UI.

## Configuration

Create a `.env` file in your project root:

```env
# SAP OData Connection
S4_BASE_URL="https://your-sap-system.com/sap/opu/odata/sap"
S4_USER="YOUR_USER"
S4_PASS="YOUR_PASSWORD"
S4_SAP_CLIENT=100

# Optional Settings
ODATA_MAX_TOP=500
ODATA_MAX_PAGES=5
ODATA_META_TTL=900
ODATA_TIMEOUT=60

# API Gateway Security
ODATA_API_KEY="your-secure-api-key"
```

## Package Structure

```
sap_ds/
├── core/              # Connection, session, authentication
│   ├── connection.py  # ConnectionContext manager
│   └── session.py     # HTTP session with SAP auth
├── odata/             # Generic OData operations
│   ├── service.py     # ODataService class
│   └── metadata.py    # Metadata parsing & caching
├── defense/           # Defense & Security domain
│   ├── base.py        # Base defense service
│   └── force_elements/  # Force Element operations
│       ├── client.py  # Main ForceElementClient
│       ├── tree.py    # Hierarchical tree builder
│       ├── graph.py   # Network graph operations
│       └── readiness.py # Readiness calculations
└── api/               # REST API Gateway
    ├── gateway.py     # FastAPI application
    └── models.py      # Pydantic request/response models
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/force-elements` | GET | List force elements |
| `/force-elements/{id}` | GET | Get single force element |
| `/force-elements/tree` | POST | Build hierarchy tree |
| `/force-elements/graph` | POST | Get network graph |
| `/force-elements/readiness` | POST | Get readiness data |
| `/query` | POST | Generic OData query |
| `/discover/entity-sets` | GET | List available entity sets |
| `/discover/fields` | GET | List fields for an entity |

## Tested Force Element IDs

The following IDs are confirmed working in the sandbox:

| ID | Name |
|----|------|
| 50000026 | World |
| 50000027 | SandBox Org Structure |
| 50000028 | SandBox 1st DIV |
| 50000029 | SandBox 2nd DIV |
| 50000030 | Sandbox TRANSCOM Unit |

## Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Start API in development mode
uvicorn sap_ds.api:app --reload
```

## License

Internal SAP use only.

