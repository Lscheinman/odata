# sap_ds.core

Core connectivity and session management for SAP OData integration.

## Overview

This module provides the foundational components for connecting to SAP systems:

- **Session Management** - HTTP session handling with authentication, CSRF tokens, and cookie management
- **Connection Context** - High-level context manager for easy connection handling
- **Authentication** - Support for Basic auth and Bearer token authentication
- **Error Handling** - Typed exceptions for OData upstream errors

## Components

### `session.py`

Core HTTP session handling for SAP OData.

```python
from sap_ds.core.session import (
    ODataConfig,
    ODataAuth,
    SAPODataSession,
    ODataUpstreamError,
)

# Configure connection
config = ODataConfig(
    base_url="https://sap-system.example.com/sap/opu/odata/sap/",
    auth=ODataAuth("basic", ("USER", "PASS")),
    default_sap_client="100",
    verify_tls=True,
    timeout=60,
)

# Use session
with SAPODataSession(config) as session:
    # GET request
    data = session.get_json("API_SERVICE/EntitySet?$top=10")
    
    # Get raw text (for $metadata)
    metadata_xml = session.get_text("API_SERVICE/$metadata")
```

### `connection.py`

High-level connection context manager (hana_ml style).

```python
from sap_ds.core.connection import ConnectionContext

# Using environment variables
with ConnectionContext() as conn:
    service = conn.get_service("API_MAINTENANCEORDER_SRV")
    orders = service.query("A_MaintenanceOrder", top=10)

# Or with explicit parameters
with ConnectionContext(
    base_url="https://sap.example.com/sap/opu/odata/sap/",
    user="USER",
    password="PASS",
    sap_client="100",
) as conn:
    # Use connection
    pass
```

## Classes

### ODataConfig

Configuration dataclass for OData connections.

| Attribute | Type | Description |
|-----------|------|-------------|
| `base_url` | str | Base OData URL (must end with /) |
| `auth` | ODataAuth | Authentication configuration |
| `default_sap_client` | str | Default SAP client number |
| `verify_tls` | bool | Verify TLS certificates |
| `timeout` | int | HTTP timeout in seconds |

### ODataAuth

Authentication configuration.

| Attribute | Type | Description |
|-----------|------|-------------|
| `method` | str | Auth method: "basic" or "bearer" |
| `credentials` | tuple/str | (user, pass) for basic, token for bearer |

### SAPODataSession

HTTP session with SAP-specific handling:

- Automatic CSRF token fetching and refresh
- Cookie-based session management
- Retry with exponential backoff
- Proper Accept headers for JSON/XML

### ODataUpstreamError

Exception raised when SAP returns an error.

| Attribute | Type | Description |
|-----------|------|-------------|
| `status` | int | HTTP status code |
| `url` | str | Request URL |
| `message` | str | Error message |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `S4_BASE_URL` | OData base URL |
| `S4_USER` | Basic auth username |
| `S4_PASS` | Basic auth password |
| `S4_BEARER_TOKEN` | Bearer token (alternative) |
| `S4_SAP_CLIENT` | Default SAP client |
| `S4_VERIFY_TLS` | TLS verification (true/false) |
| `ODATA_TIMEOUT` | HTTP timeout seconds |
| `ODATA_RETRIES` | Max retry attempts |
| `ODATA_BACKOFF` | Retry backoff multiplier |
