"""
Tests for sap_ds.defense module.
"""

import pytest
from unittest.mock import Mock, patch

from sap_ds.defense.base import DefenseClient
from sap_ds.defense.force_elements import ForceElementClient, ForceElement


class TestDefenseClient:
    """Tests for DefenseClient base class."""
    
    def test_requires_service_name(self, mock_session):
        client = DefenseClient(mock_session)
        
        with pytest.raises(NotImplementedError):
            _ = client.service
    
    def test_entity_set_mapping(self, mock_session):
        class TestClient(DefenseClient):
            SERVICE_NAME = "TEST_SRV"
            ENTITY_SETS = {
                "items": "A_ActualEntitySet",
            }
        
        client = TestClient(mock_session)
        
        assert client._get_entity_set("items") == "A_ActualEntitySet"
        assert client._get_entity_set("unmapped") == "unmapped"


class TestForceElementClient:
    """Tests for ForceElementClient."""
    
    def test_get_force_elements(self, mock_session, sample_force_elements):
        mock_session.get = Mock(return_value={
            "d": {"results": sample_force_elements}
        })
        mock_session.get_text = Mock(return_value="""<?xml version="1.0"?>
            <edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
                <edmx:DataServices>
                    <Schema xmlns="http://schemas.microsoft.com/ado/2008/09/edm">
                        <EntityType Name="ForceElement">
                            <Property Name="ForceElementID" Type="Edm.String"/>
                            <Property Name="ForceElementName" Type="Edm.String"/>
                            <Property Name="ForceElementType" Type="Edm.String"/>
                            <Property Name="ParentForceElementID" Type="Edm.String"/>
                            <Property Name="Status" Type="Edm.String"/>
                            <Property Name="Location" Type="Edm.String"/>
                            <Property Name="StrengthAuthorized" Type="Edm.Int32"/>
                            <Property Name="StrengthAssigned" Type="Edm.Int32"/>
                        </EntityType>
                        <EntityContainer>
                            <EntitySet Name="A_ForceElement" EntityType="ForceElement"/>
                        </EntityContainer>
                    </Schema>
                </edmx:DataServices>
            </edmx:Edmx>""")
        
        client = ForceElementClient(mock_session)
        elements = client.get_force_elements()
        
        assert len(elements) == 2
        assert elements[0]["ForceElementID"] == "FE-001"
    
    def test_get_force_element_by_id(self, mock_session, sample_force_elements):
        mock_session.get = Mock(return_value={
            "d": {"results": [sample_force_elements[0]]}
        })
        mock_session.get_text = Mock(return_value="""<?xml version="1.0"?>
            <edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
                <edmx:DataServices>
                    <Schema xmlns="http://schemas.microsoft.com/ado/2008/09/edm">
                        <EntityType Name="ForceElement">
                            <Property Name="ForceElementID" Type="Edm.String"/>
                            <Property Name="ForceElementName" Type="Edm.String"/>
                        </EntityType>
                        <EntityContainer>
                            <EntitySet Name="A_ForceElement" EntityType="ForceElement"/>
                        </EntityContainer>
                    </Schema>
                </edmx:DataServices>
            </edmx:Edmx>""")
        
        client = ForceElementClient(mock_session)
        element = client.get_force_element("FE-001")
        
        assert element is not None
        assert element["ForceElementID"] == "FE-001"
    
    def test_get_subordinates(self, mock_session, sample_force_elements):
        mock_session.get = Mock(return_value={
            "d": {"results": [sample_force_elements[1]]}  # Only child
        })
        mock_session.get_text = Mock(return_value="""<?xml version="1.0"?>
            <edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
                <edmx:DataServices>
                    <Schema xmlns="http://schemas.microsoft.com/ado/2008/09/edm">
                        <EntityType Name="ForceElement">
                            <Property Name="ForceElementID" Type="Edm.String"/>
                            <Property Name="ParentForceElementID" Type="Edm.String"/>
                        </EntityType>
                        <EntityContainer>
                            <EntitySet Name="A_ForceElement" EntityType="ForceElement"/>
                        </EntityContainer>
                    </Schema>
                </edmx:DataServices>
            </edmx:Edmx>""")
        
        client = ForceElementClient(mock_session)
        subs = client.get_subordinates("FE-001")
        
        assert len(subs) == 1
        assert subs[0]["ParentForceElementID"] == "FE-001"
    
    def test_to_dataclass(self, mock_session, sample_force_elements):
        client = ForceElementClient(mock_session)
        
        fe = client.to_dataclass(sample_force_elements[0])
        
        assert isinstance(fe, ForceElement)
        assert fe.id == "FE-001"
        assert fe.name == "1st Battalion"
        assert fe.type == "BATTALION"
        assert fe.status == "ACTIVE"
        assert fe.strength_authorized == 800


class TestForceElement:
    """Tests for ForceElement dataclass."""
    
    def test_creation(self):
        fe = ForceElement(
            id="001",
            name="Test Unit",
            type="COMPANY",
            status="ACTIVE",
        )
        
        assert fe.id == "001"
        assert fe.name == "Test Unit"
        assert fe.parent_id is None
        assert fe.strength_authorized is None
    
    def test_with_all_fields(self, sample_force_elements):
        data = sample_force_elements[0]
        fe = ForceElement(
            id=data["ForceElementID"],
            name=data["ForceElementName"],
            type=data["ForceElementType"],
            parent_id=data["ParentForceElementID"],
            status=data["Status"],
            location=data["Location"],
            strength_authorized=data["StrengthAuthorized"],
            strength_assigned=data["StrengthAssigned"],
            raw_data=data,
        )
        
        assert fe.strength_authorized == 800
        assert fe.strength_assigned == 750
        assert fe.raw_data == data
