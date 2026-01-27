from __future__ import annotations

from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple, Union

from session import SAPODataSession, ODataUpstreamError
from metadata import ODataMetadata


def escape_odata_literal(value: str) -> str:
    return value.replace("'", "''")


def _join_csv(items: Sequence[str]) -> str:
    return ",".join([s.strip() for s in items if s and s.strip()])


class ODataService:
    """
    Service-scoped query client.

    Key improvement: generic query() that takes entity_set + fields + filters,
    and can validate fields using $metadata (optional).
    """

    def __init__(
        self,
        sess: SAPODataSession,
        service: str,
        *,
        default_sap_client: Optional[str] = None,
    ) -> None:
        self.sess = sess
        self.service = service
        self.default_sap_client = default_sap_client
        self.meta = ODataMetadata(sess, service, sap_client=default_sap_client)

    # ---------------- core reads ----------------

    def read(self, entity_set: str, *, sap_client: Optional[str] = None, **query: str) -> List[Dict[str, Any]]:
        payload = self.sess.get(self.service, entity_set, params=query, sap_client=sap_client or self.default_sap_client)
        return payload.get("d", {}).get("results") or payload.get("value") or []

    def iterate(
        self,
        entity_set: str,
        *,
        sap_client: Optional[str] = None,
        max_pages: Optional[int] = None,
        **query: str,
    ) -> Generator[List[Dict[str, Any]], None, None]:
        sap = sap_client or self.default_sap_client
        p = self.sess.get(self.service, entity_set, params=query, sap_client=sap)

        yielded = 0
        first = p.get("d", {}).get("results") or p.get("value") or []
        if first:
            yield first
            yielded += 1
            if max_pages is not None and yielded >= int(max_pages):
                return

        next_link = p.get("d", {}).get("__next") or p.get("@odata.nextLink")
        seen = set()

        while next_link:
            if next_link in seen:
                return
            seen.add(next_link)

            r = self.sess.session.get(next_link, timeout=self.sess.timeout, verify=self.sess.verify)
            self.sess._raise_for_error(r, next_link)
            p = r.json()

            chunk = p.get("d", {}).get("results") or p.get("value") or []
            if chunk:
                yield chunk
                yielded += 1
                if max_pages is not None and yielded >= int(max_pages):
                    return

            next_link = p.get("d", {}).get("__next") or p.get("@odata.nextLink")

    def read_all(
        self,
        entity_set: str,
        *,
        sap_client: Optional[str] = None,
        max_pages: Optional[int] = None,
        **query: str,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for page in self.iterate(entity_set, sap_client=sap_client, max_pages=max_pages, **query):
            out.extend(page)
        return out

    # ---------------- generic query builder ----------------

    def query(
        self,
        entity_set: str,
        *,
        fields: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        orderby: Optional[str] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        expand: Optional[str] = None,
        sap_client: Optional[str] = None,
        max_pages: Optional[int] = None,
        validate_fields: bool = True,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generic, “works with any table/field you provide” query.

        - fields -> $select
        - filter_expr -> $filter (string)
        - validate_fields -> checks against $metadata and drops unknown fields (does not fail)
        """
        params: Dict[str, str] = {}
        if extra_params:
            params.update(extra_params)

        if fields:
            use_fields = fields
            if validate_fields:
                valid, unknown = self.meta.validate_select(entity_set, fields)
                use_fields = valid
                if unknown:
                    # deliberate: don't explode; just make it visible
                    # (you can flip this to raise if you prefer)
                    # print or log is fine; leaving silent is also ok.
                    pass
            if use_fields:
                params["$select"] = _join_csv(use_fields)

        if filter_expr:
            params["$filter"] = filter_expr
        if orderby:
            params["$orderby"] = orderby
        if expand:
            params["$expand"] = expand
        if top is not None:
            params["$top"] = str(int(top))
        if skip is not None:
            params["$skip"] = str(int(skip))

        return self.read_all(entity_set, sap_client=sap_client, max_pages=max_pages, **params)

    # ---------------- discovery helpers ----------------

    def list_entity_sets(self) -> List[str]:
        return self.meta.entity_sets()

    def list_fields(self, entity_set: str) -> List[str]:
        return self.meta.properties(entity_set)
