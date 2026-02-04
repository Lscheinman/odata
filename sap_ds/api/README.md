# sap_ds.api

FastAPI REST Gateway for SAP OData services.

## Overview

This module provides a REST API gateway that exposes SAP OData operations via HTTP:

- **Swagger UI** - Interactive API documentation at `/docs`
- **API Key Security** - Simple authentication via `X-API-Key` header
- **Force Elements Endpoints** - Pre-built endpoints for D&S operations
- **Generic Query** - Query any OData service dynamically
- **Discovery** - List entity sets and fields

## Quick Start

### Running the API

```bash
# Using Python module
python -m sap_ds.api

# Using uvicorn directly
uvicorn sap_ds.api:app --host 0.0.0.0 --port 8000

# Development mode with auto-reload
uvicorn sap_ds.api:app --host 0.0.0.0 --port 8000 --reload
```

### Accessing Swagger UI

Open http://localhost:8000/docs in your browser.

### Making Requests

```bash
# Health check
curl http://localhost:8000/health

# List force elements (requires API key)
curl -H "X-API-Key: your_api_key_here" \
     "http://localhost:8000/force-elements?top=10"

# Get single force element
curl -H "X-API-Key: your_api_key_here" \
     "http://localhost:8000/force-elements/50000027"

# Generic query
curl -H "X-API-Key: your_api_key_here" \
     -H "Content-Type: application/json" \
     -X POST "http://localhost:8000/query" \
     -d '{
       "service": "DFS_FE_FRCELMNTORG_SRV",
       "entity_set": "C_FrcElmntOrgTP",
       "top": 10,
       "filter": "IsActiveEntity eq true"
     }'
```

## Files

| File | Description |
|------|-------------|
| `__init__.py` | Module init, exports FastAPI app |
| `__main__.py` | Entry point for `python -m sap_ds.api` |
| `gateway.py` | FastAPI application and routes |
| `models.py` | Pydantic request/response models |

## Endpoints

### Health & Discovery

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (no auth required) |
| `/discover/entity-sets` | GET | List entity sets in a service |
| `/discover/fields` | GET | List fields for an entity set |

### Force Elements

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/force-elements` | GET | List force elements |
| `/force-elements/{id}` | GET | Get single force element |
| `/force-elements/tree` | POST | Build hierarchy tree |
| `/force-elements/graph` | POST | Get network graph |
| `/force-elements/readiness` | POST | Get readiness data |
| `/force-elements/metadata` | GET | Get Force Element API info |

### Generic Query

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/query` | POST | Query any OData service |

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `S4_BASE_URL` | SAP OData base URL | Required |
| `S4_USER` | SAP username | Required |
| `S4_PASS` | SAP password | Required |
| `S4_SAP_CLIENT` | SAP client number | None |
| `ODATA_API_KEY` | API key for authentication | Required |
| `ODATA_MAX_TOP` | Max results per request | 500 |
| `ODATA_MAX_PAGES` | Max pages to follow | 5 |

## Request/Response Models

### QueryRequest

```json
{
  "service": "DFS_FE_FRCELMNTORG_SRV",
  "entity_set": "C_FrcElmntOrgTP",
  "top": 100,
  "skip": 0,
  "filter": "IsActiveEntity eq true",
  "select": ["ForceElementOrgID", "FrcElmntOrgName"],
  "orderby": null,
  "validate_fields": false
}
```

### ForceElementTreeRequest

```json
{
  "root_id": "50000027",
  "depth": 3,
  "hierarchy_type": "structure",
  "include_readiness": true,
  "include_sidc": false
}
```

## Security

### API Key Authentication

All endpoints except `/health` require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your_api_key_here" http://localhost:8000/force-elements
```

### Production Recommendations

1. **Use HTTPS** - Never expose over plain HTTP
2. **Strong API Key** - Use a secure random key
3. **Rate Limiting** - Add rate limiting middleware
4. **Read-Only SAP User** - Use SAP user with minimal permissions
5. **Network Isolation** - Run behind a reverse proxy

## Extending the API

### Adding New Endpoints

```python
from fastapi import Depends
from sap_ds.api.gateway import app, require_api_key, get_gateway

@app.get("/my-endpoint", tags=["Custom"])
def my_endpoint(
    param: str,
    _: None = Depends(require_api_key),
):
    gw = get_gateway()
    with gw.build_session() as sess:
        # Your logic here
        return {"result": "data"}
```

### Custom Response Models

```python
from pydantic import BaseModel
from typing import List

class MyResponse(BaseModel):
    count: int
    items: List[dict]

@app.get("/my-endpoint", response_model=MyResponse)
def my_endpoint():
    return MyResponse(count=0, items=[])
```

## Error Responses

| Status | Description |
|--------|-------------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Not found |
| 502 | Bad gateway (SAP upstream error) |
| 503 | Service unavailable |

### Error Response Format

```json
{
  "detail": {
    "upstream_status": 400,
    "url": "https://sap.example.com/...",
    "error": "Error message from SAP"
  }
}
```
