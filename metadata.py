from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET

from session import SAPODataSession


@dataclass
class EntitySetInfo:
    name: str
    entity_type: str
    properties: List[str]


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


class ODataMetadata:
    """
    Lightweight $metadata parser for OData v2/v4.
    Works well enough for: list entity sets, list properties, validate $select fields.
    """

    def __init__(self, sess: SAPODataSession, service: str, *, sap_client: Optional[str] = None):
        self.sess = sess
        self.service = service
        self.sap_client = sap_client
        self._entity_sets: Dict[str, EntitySetInfo] = {}

    def refresh(self) -> None:
        xml_text = self.sess.get_text(self.service, "$metadata", sap_client=self.sap_client)
        root = ET.fromstring(xml_text)

        # Collect EntityType -> properties
        entity_props: Dict[str, List[str]] = {}
        # Many namespaces exist; we just walk and match by local names.
        for node in root.iter():
            if _strip_ns(node.tag) == "EntityType":
                et_name = node.attrib.get("Name")
                if not et_name:
                    continue
                props: List[str] = []
                for c in node:
                    if _strip_ns(c.tag) == "Property":
                        pname = c.attrib.get("Name")
                        if pname:
                            props.append(pname)
                entity_props[et_name] = props

        # Find EntitySets in EntityContainer
        entity_sets: Dict[str, EntitySetInfo] = {}
        for node in root.iter():
            if _strip_ns(node.tag) == "EntitySet":
                es_name = node.attrib.get("Name")
                et_full = node.attrib.get("EntityType")  # often Namespace.Type
                if not es_name or not et_full:
                    continue
                et_name = et_full.split(".")[-1]
                props = entity_props.get(et_name, [])
                entity_sets[es_name] = EntitySetInfo(name=es_name, entity_type=et_full, properties=props)

        self._entity_sets = entity_sets

    def entity_sets(self) -> List[str]:
        if not self._entity_sets:
            self.refresh()
        return sorted(self._entity_sets.keys())

    def properties(self, entity_set: str) -> List[str]:
        if not self._entity_sets:
            self.refresh()
        info = self._entity_sets.get(entity_set)
        return list(info.properties) if info else []

    def validate_select(self, entity_set: str, fields: List[str]) -> Tuple[List[str], List[str]]:
        """
        Returns (valid_fields, unknown_fields)
        """
        props = set(self.properties(entity_set))
        valid, unknown = [], []
        for f in fields:
            (valid if f in props else unknown).append(f)
        return valid, unknown
