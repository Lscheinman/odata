"""
sap_ds.core.session - SAP OData HTTP Session Management
========================================================

Low-level session handling for SAP OData services with:
- Basic and Bearer token authentication
- Automatic retry with exponential backoff
- CSRF token handling for write operations
- sap-client injection
- Proper error extraction from SAP responses
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union
import json
import logging
import threading
import time

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class ODataUpstreamError(RuntimeError):
    """
    Exception raised when the SAP OData service returns an error.
    
    Attributes
    ----------
    status : int
        HTTP status code from SAP
    body : str
        Response body (truncated for display)
    url : str
        The URL that was called
    headers : dict
        Response headers
    """
    
    def __init__(
        self, 
        status: int, 
        body: str, 
        url: str, 
        headers: Optional[Dict[str, str]] = None
    ):
        snippet = (body or "")[:1200]
        super().__init__(f"OData upstream error {status} for {url}: {snippet}")
        self.status = status
        self.body = body or ""
        self.url = url
        self.headers = headers or {}


@dataclass
class ODataAuth:
    """
    Authentication configuration for SAP OData.
    
    Parameters
    ----------
    kind : str
        Either "basic" or "bearer"
    value : tuple or str
        For basic: (username, password) tuple
        For bearer: access token string
        
    Examples
    --------
    >>> auth = ODataAuth("basic", ("USER", "PASSWORD"))
    >>> auth = ODataAuth("bearer", "eyJ...")
    """
    kind: str  # "basic" | "bearer"
    value: Union[Tuple[str, str], str]  # (user, pass) or access_token


@dataclass
class ODataConfig:
    """
    Connection configuration for SAP OData services.
    
    Parameters
    ----------
    base_url : str
        Base URL for OData services, e.g. "https://host/sap/opu/odata/sap/"
    auth : ODataAuth
        Authentication configuration
    default_sap_client : str, optional
        Default SAP client number (can be overridden per-request)
    lang : str
        Language for SAP (default: "EN")
    timeout : float
        Request timeout in seconds (default: 60.0)
    retries : int
        Number of retry attempts (default: 3)
    backoff : float
        Backoff factor for retries (default: 0.5)
    verify : bool or str
        SSL verification (True, False, or path to CA bundle)
    user_agent : str
        User-Agent header value
        
    Examples
    --------
    >>> cfg = ODataConfig(
    ...     base_url="https://s4.example.com/sap/opu/odata/sap/",
    ...     auth=ODataAuth("basic", ("USER", "PASS")),
    ...     default_sap_client="100",
    ... )
    """
    base_url: str
    auth: ODataAuth
    default_sap_client: Optional[str] = None
    lang: str = "EN"
    timeout: float = 60.0
    retries: int = 3
    backoff: float = 0.5
    verify: Union[bool, str] = True
    user_agent: str = "sap-ds-sdk/0.1"


class SAPODataSession:
    """
    Low-level HTTP session for SAP OData v2/v4 services.
    
    Handles authentication, retries, CSRF tokens, and sap-client injection.
    Use as a context manager for automatic cleanup.
    
    Parameters
    ----------
    cfg : ODataConfig
        Connection configuration
        
    Examples
    --------
    >>> cfg = ODataConfig(...)
    >>> with SAPODataSession(cfg) as sess:
    ...     data = sess.get("SERVICE_NAME", "EntitySet")
    """

    def __init__(self, cfg: ODataConfig) -> None:
        self.cfg = cfg
        self.base = cfg.base_url.rstrip("/") + "/"
        self.timeout = float(cfg.timeout)
        self.verify = cfg.verify
        self.logger = logging.getLogger("sap_ds.odata")

        self.session = self._build_session()

        self._csrf_tokens: Dict[str, str] = {}
        self._csrf_lock = threading.Lock()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self) -> "SAPODataSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---------------- auth/session ----------------

    def _build_session(self) -> Session:
        sess = requests.Session()

        # auth
        if self.cfg.auth.kind == "basic":
            sess.auth = self.cfg.auth.value  # type: ignore[assignment]
        elif self.cfg.auth.kind == "bearer":
            sess.headers.update({"Authorization": f"Bearer {self.cfg.auth.value}"})
        else:
            raise ValueError("auth.kind must be 'basic' or 'bearer'")

        sess.headers.update({
            "Accept": "application/json",
            "Accept-Language": self.cfg.lang.lower(),
            "sap-language": self.cfg.lang.upper(),
            "DataServiceVersion": "2.0",
            "MaxDataServiceVersion": "2.0",
            "User-Agent": self.cfg.user_agent,
        })

        retry = Retry(
            total=self.cfg.retries,
            backoff_factor=self.cfg.backoff,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
        return sess

    # ---------------- helpers ----------------

    def _params(
        self,
        params: Optional[Dict[str, str]] = None,
        sap_client: Optional[str] = None,
        *,
        include_format: bool = True,
        include_client: bool = True,
    ) -> Dict[str, str]:
        p: Dict[str, str] = {}
        if include_format:
            p["$format"] = "json"
        if include_client:
            client = sap_client if sap_client is not None else self.cfg.default_sap_client
            if client:
                p["sap-client"] = str(client)
        if params:
            p.update(params)
        return p

    def _url(self, service: str, path: str) -> str:
        return f"{self.base}{service.strip('/')}/{path.lstrip('/')}"

    def _json_or_text(self, r: Response) -> Dict[str, Any]:
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "json" in ctype:
            try:
                return r.json()
            except Exception:
                pass
        return {"raw": r.text, "content_type": r.headers.get("Content-Type", "")}

    def _extract_sap_error(self, r: Response) -> str:
        try:
            data = r.json()
        except Exception:
            return r.text
        if not isinstance(data, dict):
            return r.text
        err = data.get("error")
        if not isinstance(err, dict):
            return r.text

        code = err.get("code")
        message = None
        if isinstance(err.get("message"), dict):
            message = err["message"].get("value")
        elif isinstance(err.get("message"), str):
            message = err.get("message")

        inner = err.get("innererror") or err.get("innerError")
        txid = inner.get("transactionid") if isinstance(inner, dict) else None
        ts = inner.get("timestamp") if isinstance(inner, dict) else None

        parts = []
        if code:
            parts.append(f"code={code}")
        if message:
            parts.append(f"message={message}")
        if txid:
            parts.append(f"txid={txid}")
        if ts:
            parts.append(f"ts={ts}")
        return " | ".join(parts) or r.text

    def _raise_for_error(self, r: Response, url: str) -> None:
        if r.status_code >= 400 or r.status_code in (301, 302, 303, 307, 308):
            body = self._extract_sap_error(r)
            raise ODataUpstreamError(r.status_code, body, url, dict(r.headers))

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, str]],
        headers: Dict[str, str],
        data: Optional[Union[str, bytes]] = None,
    ) -> Response:
        t0 = time.perf_counter()
        r = self.session.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            data=data,
            timeout=self.timeout,
            verify=self.verify,
        )
        self._raise_for_error(r, url)
        dt = (time.perf_counter() - t0) * 1000.0
        self.logger.debug("%s %s %sms", method.upper(), url, round(dt, 1))
        return r

    # ---------------- public ops ----------------

    def get(
        self,
        service: str,
        path: str,
        params: Optional[Dict[str, str]] = None,
        *,
        sap_client: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a GET request against an OData service path.
        
        Parameters
        ----------
        service : str
            Service name, e.g. "API_MAINTENANCEORDER_SRV"
        path : str
            Entity set or path, e.g. "A_MaintenanceOrder"
        params : dict, optional
            Additional query parameters
        sap_client : str, optional
            Override default sap-client
        extra_headers : dict, optional
            Additional HTTP headers
            
        Returns
        -------
        dict
            Parsed JSON response
        """
        url = self._url(service, path)
        headers = dict(self.session.headers)
        if extra_headers:
            headers.update(extra_headers)

        is_metadata = path.strip().lower() == "$metadata"
        if is_metadata:
            headers["Accept"] = "application/xml"

        if is_metadata:
            q = self._params(params, sap_client, include_format=False, include_client=True)
        else:
            q = self._params(params, sap_client, include_format=True, include_client=True)

        r = self._request("GET", url, params=q, headers=headers)
        return self._json_or_text(r)

    def get_text(
        self,
        service: str,
        path: str,
        params: Optional[Dict[str, str]] = None,
        *,
        sap_client: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Execute a GET request and return raw text response.
        
        Useful for $metadata which returns XML.
        """
        url = self._url(service, path)
        headers = dict(self.session.headers)
        
        # For $metadata, accept XML instead of JSON
        if path == "$metadata" or path.endswith("/$metadata"):
            headers["Accept"] = "application/xml"
        
        if extra_headers:
            headers.update(extra_headers)

        q = self._params(params, sap_client, include_format=False, include_client=True)

        r = self._request("GET", url, params=q, headers=headers)
        return r.text

    def _ensure_csrf(self, service: str, *, sap_client: Optional[str] = None) -> None:
        key = f"{service}::{sap_client or self.cfg.default_sap_client or ''}"
        if key in self._csrf_tokens:
            return

        with self._csrf_lock:
            if key in self._csrf_tokens:
                return

            url = self._url(service, "$metadata")
            headers = dict(self.session.headers)
            headers["X-CSRF-Token"] = "Fetch"

            q = self._params({}, sap_client, include_format=False, include_client=True)

            r = self._request("GET", url, params=q, headers=headers)
            token = r.headers.get("x-csrf-token")
            if not token:
                raise ODataUpstreamError(400, "Failed to obtain CSRF token", url, dict(r.headers))

            self._csrf_tokens[key] = token

    def post(
        self,
        service: str,
        entity_set: str,
        payload: Dict[str, Any],
        *,
        sap_client: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a POST (create) request against an entity set.
        
        Automatically handles CSRF token fetching.
        """
        self._ensure_csrf(service, sap_client=sap_client)
        url = self._url(service, entity_set)
        key = f"{service}::{sap_client or self.cfg.default_sap_client or ''}"
        headers = {
            "X-CSRF-Token": self._csrf_tokens[key],
            "Content-Type": "application/json"
        }
        r = self._request(
            "POST",
            url,
            params=self._params({}, sap_client),
            headers=headers,
            data=json.dumps(payload, separators=(",", ":"))
        )
        try:
            return r.json()
        except Exception:
            return {"location": r.headers.get("Location"), "etag": r.headers.get("ETag")}
