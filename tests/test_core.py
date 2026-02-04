"""
Tests for sap_ds.core module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from sap_ds.core.session import (
    ODataAuth,
    ODataConfig,
    SAPODataSession,
    ODataUpstreamError,
)
from sap_ds.core.connection import ConnectionContext


class TestODataAuth:
    """Tests for ODataAuth dataclass."""
    
    def test_basic_auth(self):
        auth = ODataAuth("basic", ("user", "pass"))
        assert auth.kind == "basic"
        assert auth.value == ("user", "pass")
    
    def test_bearer_auth(self):
        auth = ODataAuth("bearer", "token123")
        assert auth.kind == "bearer"
        assert auth.value == "token123"


class TestODataConfig:
    """Tests for ODataConfig dataclass."""
    
    def test_default_values(self):
        cfg = ODataConfig(
            base_url="https://test.com/odata/",
            auth=ODataAuth("basic", ("user", "pass")),
        )
        assert cfg.lang == "EN"
        assert cfg.timeout == 60.0
        assert cfg.retries == 3
        assert cfg.verify is True
    
    def test_custom_values(self):
        cfg = ODataConfig(
            base_url="https://test.com/odata/",
            auth=ODataAuth("bearer", "token"),
            default_sap_client="200",
            lang="DE",
            timeout=30.0,
            verify=False,
        )
        assert cfg.default_sap_client == "200"
        assert cfg.lang == "DE"
        assert cfg.timeout == 30.0
        assert cfg.verify is False


class TestODataUpstreamError:
    """Tests for ODataUpstreamError exception."""
    
    def test_error_attributes(self):
        err = ODataUpstreamError(
            status=404,
            body="Not found",
            url="https://test.com/entity",
            headers={"x-request-id": "123"},
        )
        assert err.status == 404
        assert err.body == "Not found"
        assert err.url == "https://test.com/entity"
        assert err.headers == {"x-request-id": "123"}
    
    def test_error_message_truncation(self):
        long_body = "x" * 2000
        err = ODataUpstreamError(500, long_body, "https://test.com")
        # Message should be truncated
        assert len(str(err)) < 1500


class TestSAPODataSession:
    """Tests for SAPODataSession."""
    
    @patch("sap_ds.core.session.requests.Session")
    def test_session_creation_basic_auth(self, mock_session_class):
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        cfg = ODataConfig(
            base_url="https://test.com/odata",
            auth=ODataAuth("basic", ("user", "pass")),
        )
        
        sess = SAPODataSession(cfg)
        assert sess.base == "https://test.com/odata/"
        assert mock_session.auth == ("user", "pass")
    
    @patch("sap_ds.core.session.requests.Session")
    def test_session_creation_bearer_auth(self, mock_session_class):
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        cfg = ODataConfig(
            base_url="https://test.com/odata",
            auth=ODataAuth("bearer", "mytoken"),
        )
        
        sess = SAPODataSession(cfg)
        mock_session.headers.update.assert_called()
    
    @patch("sap_ds.core.session.requests.Session")
    def test_context_manager(self, mock_session_class):
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        cfg = ODataConfig(
            base_url="https://test.com/odata",
            auth=ODataAuth("basic", ("user", "pass")),
        )
        
        with SAPODataSession(cfg) as sess:
            assert sess is not None
        
        mock_session.close.assert_called_once()


class TestConnectionContext:
    """Tests for ConnectionContext."""
    
    def test_missing_base_url_raises(self):
        with pytest.raises(ValueError, match="Missing base_url"):
            ConnectionContext(base_url="")
    
    def test_missing_credentials_raises(self):
        with pytest.raises(ValueError, match="Missing credentials"):
            ConnectionContext(base_url="https://test.com/odata/")
    
    @patch.dict("os.environ", {
        "S4_BASE_URL": "https://env.test.com/odata/",
        "S4_USER": "envuser",
        "S4_PASS": "envpass",
        "S4_SAP_CLIENT": "300",
    })
    def test_reads_from_environment(self):
        conn = ConnectionContext()
        assert conn.base_url == "https://env.test.com/odata/"
        assert conn.sap_client == "300"
    
    def test_explicit_params_override_env(self):
        conn = ConnectionContext(
            base_url="https://explicit.com/odata/",
            user="explicituser",
            password="explicitpass",
            sap_client="400",
        )
        assert conn.base_url == "https://explicit.com/odata/"
        assert conn.sap_client == "400"
