"""
sap_ds.defense.force_elements.constants - Service and field constants
======================================================================
"""

# OData Services
SVC_FORCE_ELEMENT = "DFS_FE_FRCELMNTORG_SRV"
SVC_GRAPH = "DFS_FE_FRCELMNTORGNTWKGRAPH_SRV"

# Entity Sets
ES_FORCE_ELEMENT_TP = "C_FrcElmntOrgTP"
ES_GRAPH_EDGE = "C_FrcElmntOrgNtwkGraphRelshp"

# Key Fields
ID_FIELD = "ForceElementOrgID"
SRC_FIELD = "ForceElementOrgID"
DST_FIELD = "FrcElmntOrgRelatedOrgID"
REL_FIELD = "FrcElmntOrgSubType"

# Relationship Types
REL_STRUCTURE = "B002"  # Structural hierarchy

# Parent Field Mapping (hierarchy types)
PARENT_FIELDS = {
    "structure": "FrcElmntOrgStrucParentID",
    "peacetime": "FrcElmntOrgPeaceTimeParentID",
    "wartime": "FrcElmntOrgWarTimeParentID",
    "operation": "FrcElmntOrgOplAssgmtParentID",
    "exercise": "FrcElmntOrgExerAssgmtParentID",
}

# Name Fields (in preference order)
NAME_FIELDS = [
    "FrcElmntOrgName",
    "FrcElmntOrgShortName",
    "FrcElmntOrgConcatenatedName",
    "ForceElementOrgName",
    "Name",
    "Description",
]

# Readiness Fields
READINESS_FIELDS = [
    "FrcElmntOrgMatlRdnssPct",
    "FrcElmntOrgPrsnlRdnssPct",
    "FrcElmntOrgTrngRdnssPct",
]

# SIDC Field Candidates (discovered at runtime)
SIDC_FIELD_CANDIDATES = [
    "SIDC",
    "Sidc",
    "MILSIDC",
    "MilSidc",
    "MilStdSidc",
    "MilStd2525Sidc",
    "NATOApp6bSidc",
    "NatoApp6bSidc",
    "MilitarySymbolCode",
    "MilSymbolCode",
    "MilSymbolID",
    "MilSymbol",
    "FrcElmntOrgMilSymbCode",
    "FrcElmntOrgMilSymbCd",
    "FrcElmntOrgMilSymbID",
    "FrcElmntOrgSymbol",
]
