"""
sap_ds.odata.metadata - OData $metadata parsing
================================================

Lightweight $metadata parser for OData v2/v4 services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from sap_ds.core.session import SAPODataSession


@dataclass
class EntitySetInfo:
    """
    Information about an OData entity set.
    
    Attributes
    ----------
    name : str
        Entity set name (e.g., "A_MaintenanceOrder")
    entity_type : str
        Full entity type name including namespace
    properties : list of str
        List of property names available on this entity set
    """
    name: str
    entity_type: str
    properties: List[str]


def _strip_ns(tag: str) -> str:
    """Strip XML namespace from a tag name."""
    return tag.split("}", 1)[-1] if "}" in tag else tag


class ODataMetadata:
    """
    Lightweight $metadata parser for OData v2/v4.
    
    Parses entity sets and their properties from OData $metadata XML.
    Useful for field validation and service discovery.
    
    Parameters
    ----------
    sess : SAPODataSession
        Active OData session
    service : str
        Service name
    sap_client : str, optional
        SAP client override
        
    Examples
    --------
    >>> meta = ODataMetadata(sess, "API_MAINTENANCEORDER_SRV")
    >>> meta.entity_sets()
    ['A_MaintenanceOrder', 'A_MaintenanceOrderItem', ...]
    >>> meta.properties("A_MaintenanceOrder")
    ['MaintenanceOrder', 'OrderType', 'CompanyCode', ...]
    """

    def __init__(
        self,
        sess: SAPODataSession,
        service: str,
        *,
        sap_client: Optional[str] = None
    ):
        self.sess = sess
        self.service = service
        self.sap_client = sap_client
        self._entity_sets: Dict[str, EntitySetInfo] = {}

    def refresh(self) -> None:
        """
        Fetch and parse $metadata from the service.
        
        Called automatically on first access to entity_sets() or properties().
        """
        xml_text = self.sess.get_text(self.service, "$metadata", sap_client=self.sap_client)
        root = ET.fromstring(xml_text)

        # Collect EntityType -> properties
        entity_props: Dict[str, List[str]] = {}
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
                et_full = node.attrib.get("EntityType")
                if not es_name or not et_full:
                    continue
                et_name = et_full.split(".")[-1]
                props = entity_props.get(et_name, [])
                entity_sets[es_name] = EntitySetInfo(
                    name=es_name,
                    entity_type=et_full,
                    properties=props
                )

        self._entity_sets = entity_sets

    def entity_sets(self) -> List[str]:
        """
        Get list of entity set names in the service.
        
        Returns
        -------
        list of str
            Sorted list of entity set names
        """
        if not self._entity_sets:
            self.refresh()
        return sorted(self._entity_sets.keys())

    def properties(self, entity_set: str) -> List[str]:
        """
        Get list of properties for an entity set.
        
        Parameters
        ----------
        entity_set : str
            Name of the entity set
            
        Returns
        -------
        list of str
            List of property names
        """
        if not self._entity_sets:
            self.refresh()
        info = self._entity_sets.get(entity_set)
        return list(info.properties) if info else []

    def validate_select(
        self,
        entity_set: str,
        fields: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Validate fields against entity set metadata.
        
        Parameters
        ----------
        entity_set : str
            Name of the entity set
        fields : list of str
            Field names to validate
            
        Returns
        -------
        tuple of (list, list)
            (valid_fields, unknown_fields)
        """
        props = set(self.properties(entity_set))
        valid, unknown = [], []
        for f in fields:
            (valid if f in props else unknown).append(f)
        return valid, unknown
    
    def get_entity_set_info(self, entity_set: str) -> Optional[EntitySetInfo]:
        """
        Get detailed info about an entity set.
        
        Parameters
        ----------
        entity_set : str
            Name of the entity set
            
        Returns
        -------
        EntitySetInfo or None
            Entity set info if found
        """
        if not self._entity_sets:
            self.refresh()
        return self._entity_sets.get(entity_set)
