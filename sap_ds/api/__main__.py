"""
sap_ds.api - Run as module

Usage: python -m sap_ds.api
"""

import os
import uvicorn

from sap_ds.api import create_app


def main():
    """Run the API gateway server."""
    host = os.environ.get("ODATA_HOST", "0.0.0.0")
    port = int(os.environ.get("ODATA_PORT", "5050"))
    reload = os.environ.get("ODATA_RELOAD", "false").lower() == "true"
    log_level = os.environ.get("ODATA_LOG_LEVEL", "info")
    
    print(f"Starting SAP OData Gateway on {host}:{port}")
    
    uvicorn.run(
        "sap_ds.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
