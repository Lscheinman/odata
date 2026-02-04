"""
sap_ds.api - Optional REST API Gateway
=======================================

This module provides an optional FastAPI-based REST gateway
for exposing OData services via HTTP.

The gateway is optional and only needed if you want to run
the SDK as a microservice.

Usage
-----
>>> from sap_ds.api import create_app
>>> app = create_app()
>>> # Run with: uvicorn sap_ds.api:app

Or run directly:
>>> python -m sap_ds.api

"""

import os
from pathlib import Path

# Load .env before importing gateway
try:
    from dotenv import load_dotenv
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

from sap_ds.api.gateway import create_app, ODataGateway

# Create default app instance for uvicorn
app = create_app()

__all__ = [
    "create_app",
    "ODataGateway",
    "app",
]
