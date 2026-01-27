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
    def __init__(self, status: int, body: str, url: str, headers: Optional[Dict[str, str]] = None):
        snippet = (body or "")[:1200]
        super().__init__(f"OData upstream error {status} for {url}: {snippet}")
        self.status = status
        self.body = body or ""
        self.url = url
        self.headers = headers or {}


@dataclass
class ODataAuth:
    kind: str  # "basic" | "bearer"
    value: Union[Tuple[str, str], str]  # (user, pass) or access_token


@dataclass
class ODataConfig:
    base_url: str                         # e.g. https://my-s4.example.com/sap/opu/odata/
    auth: ODataAuth                       # basic or bearer
    default_sap_client: Optional[str] = None
    lang: str = "EN"
    timeout: float = 60.0
    retries: int = 3
    backoff: float = 0.5
    verify: Union[bool, str] = True       # bool or CA bundle path
    user_agent: str = "Standalone-ODataClient/1.0"


class SAPODataSession:
    """
    Standalone requests wrapper for SAP OData v2/v4.
    Keeps your ergonomics: retries, csrf caching, sap-client injection, paging-compatible.
    """

    def __init__(self, cfg: ODataConfig) -> None:
        self.cfg = cfg
        self.base = cfg.base_url.rstrip("/") + "/"
        self.timeout = float(cfg.timeout)
        self.verify = cfg.verify
        self.logger = logging.getLogger("odata")

        self.session = self._build_session()

        self._csrf_tokens: Dict[str, str] = {}
        self._csrf_lock = threading.Lock()

    def close(self) -> None:
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
        url = self._url(service, path)
        headers = dict(self.session.headers)
        if extra_headers:
            headers.update(extra_headers)

        is_metadata = path.strip().lower() == "$metadata"
        q = None if is_metadata else self._params(params, sap_client, include_format=True, include_client=True)

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
        url = self._url(service, path)
        headers = dict(self.session.headers)
        if extra_headers:
            headers.update(extra_headers)

        is_metadata = path.strip().lower() == "$metadata"
        q = None if is_metadata else self._params(params, sap_client, include_format=False, include_client=True)

        r = self._request("GET", url, params=q, headers=headers)
        return r.text

    def _ensure_csrf(self, service: str) -> None:
        if service in self._csrf_tokens:
            return
        with self._csrf_lock:
            if service in self._csrf_tokens:
                return
            url = self._url(service, "$metadata")
            headers = dict(self.session.headers)
            headers["X-CSRF-Token"] = "Fetch"
            r = self._request("GET", url, params=None, headers=headers)  # NO params on $metadata
            token = r.headers.get("x-csrf-token")
            if not token:
                raise ODataUpstreamError(400, "Failed to obtain CSRF token", url, dict(r.headers))
            self._csrf_tokens[service] = token

    def post(self, service: str, entity_set: str, payload: Dict[str, Any], *, sap_client: Optional[str] = None) -> Dict[str, Any]:
        self._ensure_csrf(service)
        url = self._url(service, entity_set)
        headers = {"X-CSRF-Token": self._csrf_tokens[service], "Content-Type": "application/json"}
        r = self._request("POST", url, params=self._params({}, sap_client), headers=headers, data=json.dumps(payload, separators=(",", ":")))
        try:
            return r.json()
        except Exception:
            return {"location": r.headers.get("Location"), "etag": r.headers.get("ETag")}
