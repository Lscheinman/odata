"""
Tests for sap_ds.odata module.
"""

import pytest
from unittest.mock import Mock, patch

from sap_ds.odata.service import ODataService, escape_odata_literal, _join_csv
from sap_ds.odata.metadata import ODataMetadata, EntitySetInfo, _strip_ns


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_escape_odata_literal(self):
        assert escape_odata_literal("simple") == "simple"
        assert escape_odata_literal("O'Brien") == "O''Brien"
        assert escape_odata_literal("test''double") == "test''''double"
    
    def test_join_csv(self):
        assert _join_csv(["a", "b", "c"]) == "a,b,c"
        assert _join_csv(["  a  ", "b", "  c"]) == "a,b,c"
        assert _join_csv(["a", "", "c"]) == "a,c"
        assert _join_csv([]) == ""
    
    def test_strip_ns(self):
        assert _strip_ns("{http://example.com}Tag") == "Tag"
        assert _strip_ns("Tag") == "Tag"


class TestODataMetadata:
    """Tests for ODataMetadata."""
    
    def test_parse_metadata(self, mock_session, sample_metadata_xml):
        mock_session.get_text = Mock(return_value=sample_metadata_xml)
        
        meta = ODataMetadata(mock_session, "TestService")
        
        entity_sets = meta.entity_sets()
        assert "TestEntities" in entity_sets
    
    def test_get_properties(self, mock_session, sample_metadata_xml):
        mock_session.get_text = Mock(return_value=sample_metadata_xml)
        
        meta = ODataMetadata(mock_session, "TestService")
        
        props = meta.properties("TestEntities")
        assert "ID" in props
        assert "Name" in props
        assert "Status" in props
        assert "CreatedAt" in props
    
    def test_validate_select(self, mock_session, sample_metadata_xml):
        mock_session.get_text = Mock(return_value=sample_metadata_xml)
        
        meta = ODataMetadata(mock_session, "TestService")
        
        valid, unknown = meta.validate_select(
            "TestEntities",
            ["ID", "Name", "InvalidField"]
        )
        assert "ID" in valid
        assert "Name" in valid
        assert "InvalidField" in unknown


class TestODataService:
    """Tests for ODataService."""
    
    def test_read_single_page(self, mock_session, sample_odata_response):
        mock_session.get = Mock(return_value=sample_odata_response)
        
        svc = ODataService(mock_session, "TestService")
        results = svc.read("TestEntities")
        
        assert len(results) == 2
        assert results[0]["ID"] == "001"
    
    def test_read_all_follows_paging(self, mock_session):
        page1 = {
            "d": {
                "results": [{"ID": "001"}],
                "__next": "https://test.com/page2",
            }
        }
        page2_response = Mock()
        page2_response.status_code = 200
        page2_response.json.return_value = {
            "d": {
                "results": [{"ID": "002"}],
                "__next": None,
            }
        }
        
        mock_session.get = Mock(return_value=page1)
        mock_session.session.get = Mock(return_value=page2_response)
        mock_session._raise_for_error = Mock()
        
        svc = ODataService(mock_session, "TestService")
        results = svc.read_all("TestEntities")
        
        assert len(results) == 2
    
    def test_query_builds_params(self, mock_session, sample_odata_response):
        mock_session.get = Mock(return_value=sample_odata_response)
        mock_session.get_text = Mock(return_value="""<?xml version="1.0"?>
            <edmx:Edmx xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
                <edmx:DataServices>
                    <Schema xmlns="http://schemas.microsoft.com/ado/2008/09/edm">
                        <EntityType Name="Test">
                            <Property Name="ID" Type="Edm.String"/>
                            <Property Name="Name" Type="Edm.String"/>
                        </EntityType>
                        <EntityContainer>
                            <EntitySet Name="TestEntities" EntityType="Test"/>
                        </EntityContainer>
                    </Schema>
                </edmx:DataServices>
            </edmx:Edmx>""")
        
        svc = ODataService(mock_session, "TestService")
        svc.query(
            "TestEntities",
            fields=["ID", "Name"],
            filter_expr="ID eq '001'",
            top=10,
            orderby="Name asc",
        )
        
        # Verify get was called with proper params
        call_args = mock_session.get.call_args
        params = call_args.kwargs.get("params", {}) or call_args[1].get("params", {})
        assert "$filter" in params
        assert "$top" in params
        assert "$orderby" in params
    
    def test_list_entity_sets(self, mock_session, sample_metadata_xml):
        mock_session.get_text = Mock(return_value=sample_metadata_xml)
        
        svc = ODataService(mock_session, "TestService")
        entity_sets = svc.list_entity_sets()
        
        assert "TestEntities" in entity_sets
    
    def test_list_fields(self, mock_session, sample_metadata_xml):
        mock_session.get_text = Mock(return_value=sample_metadata_xml)
        
        svc = ODataService(mock_session, "TestService")
        fields = svc.list_fields("TestEntities")
        
        assert "ID" in fields
        assert "Name" in fields
