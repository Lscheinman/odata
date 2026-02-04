# Tests

Unit and integration tests for the sap_ds package.

## Running Tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_odata.py -v

# Run with coverage
pytest --cov=sap_ds --cov-report=html

# Run only unit tests (no SAP connection)
pytest -m "not integration"

# Run integration tests (requires SAP connection)
pytest -m integration
```

## Test Files

| File | Description |
|------|-------------|
| `conftest.py` | Pytest fixtures and configuration |
| `test_core.py` | Tests for sap_ds.core module |
| `test_odata.py` | Tests for sap_ds.odata module |
| `test_defense.py` | Tests for sap_ds.defense module |

## Fixtures

Common fixtures defined in `conftest.py`:

```python
@pytest.fixture
def mock_session():
    """Mock SAPODataSession for unit tests."""
    ...

@pytest.fixture
def sample_metadata():
    """Sample $metadata XML for testing."""
    ...

@pytest.fixture
def sample_force_elements():
    """Sample Force Element data."""
    ...
```

## Writing Tests

### Unit Tests (No SAP Required)

```python
def test_metadata_parsing(sample_metadata):
    """Test metadata parsing without SAP connection."""
    from sap_ds.odata import ODataMetadata
    
    meta = ODataMetadata(sample_metadata)
    assert "A_MaintenanceOrder" in meta.entity_sets()

def test_query_building(mock_session):
    """Test query construction."""
    from sap_ds.odata import ODataService
    
    service = ODataService(mock_session, "API_TEST_SRV")
    # Test query building logic
```

### Integration Tests (Requires SAP)

```python
import pytest

@pytest.mark.integration
def test_live_query():
    """Test against real SAP system."""
    from sap_ds import ConnectionContext
    
    with ConnectionContext() as conn:
        service = conn.get_service("API_MAINTENANCEORDER_SRV")
        result = service.query("A_MaintenanceOrder", top=1)
        assert len(result) <= 1
```

## Test Configuration

For integration tests, create a `.env.test` file:

```env
S4_BASE_URL="https://test-sap-system.example.com/sap/opu/odata/sap/"
S4_USER="TEST_USER"
S4_PASS="TEST_PASS"
S4_SAP_CLIENT=100
```

## Coverage

Generate HTML coverage report:

```bash
pytest --cov=sap_ds --cov-report=html
open htmlcov/index.html
```

## Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.integration` | Requires live SAP connection |
| `@pytest.mark.slow` | Long-running tests |
| `@pytest.mark.unit` | Pure unit tests |
