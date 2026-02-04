"""
Pytest configuration and shared fixtures.
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Any, Dict, List


@pytest.fixture
def mock_session():
    """Create a mock SAPODataSession."""
    session = Mock()
    session.cfg = Mock()
    session.cfg.default_sap_client = "100"
    session.base = "https://test.example.com/sap/opu/odata/sap/"
    session.timeout = 60.0
    session.verify = True
    session.session = Mock()
    return session


@pytest.fixture
def sample_odata_response():
    """Sample OData v2 response."""
    return {
        "d": {
            "results": [
                {"ID": "001", "Name": "Test 1", "Status": "ACTIVE"},
                {"ID": "002", "Name": "Test 2", "Status": "INACTIVE"},
            ],
            "__next": None,
        }
    }


@pytest.fixture
def sample_metadata_xml():
    """Sample OData $metadata XML."""
    return """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
  <edmx:DataServices m:DataServiceVersion="2.0" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
    <Schema Namespace="TestService" xmlns="http://schemas.microsoft.com/ado/2008/09/edm">
      <EntityType Name="TestEntity">
        <Key>
          <PropertyRef Name="ID"/>
        </Key>
        <Property Name="ID" Type="Edm.String" Nullable="false"/>
        <Property Name="Name" Type="Edm.String"/>
        <Property Name="Status" Type="Edm.String"/>
        <Property Name="CreatedAt" Type="Edm.DateTime"/>
      </EntityType>
      <EntityContainer Name="TestService" m:IsDefaultEntityContainer="true">
        <EntitySet Name="TestEntities" EntityType="TestService.TestEntity"/>
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>"""


@pytest.fixture
def sample_force_elements():
    """Sample force element data."""
    return [
        {
            "ForceElementID": "FE-001",
            "ForceElementName": "1st Battalion",
            "ForceElementType": "BATTALION",
            "ParentForceElementID": None,
            "Status": "ACTIVE",
            "Location": "Base Alpha",
            "StrengthAuthorized": 800,
            "StrengthAssigned": 750,
        },
        {
            "ForceElementID": "FE-002",
            "ForceElementName": "Alpha Company",
            "ForceElementType": "COMPANY",
            "ParentForceElementID": "FE-001",
            "Status": "ACTIVE",
            "Location": "Base Alpha",
            "StrengthAuthorized": 200,
            "StrengthAssigned": 180,
        },
    ]
