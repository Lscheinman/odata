# Examples

This directory contains example scripts for using the `sap_ds` package.

## Available Examples

### basic_usage.py

Demonstrates:
- Basic OData queries with `ODataConfig` and `SAPODataSession`
- Using `ConnectionContext` (hana_ml style)
- Force Elements client for Defense & Security

### Running Examples

1. Set up environment variables:

```bash
export S4_BASE_URL="https://your-s4.example.com/sap/opu/odata/sap/"
export S4_USER="your_user"
export S4_PASS="your_password"
export S4_SAP_CLIENT="100"
```

2. Run an example:

```bash
python examples/basic_usage.py
```

## Adding Your Own Examples

Feel free to add new example files for specific use cases. Follow the pattern in `basic_usage.py`.
