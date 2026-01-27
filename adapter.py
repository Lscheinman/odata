from session import ODataAuth, ODataConfig, SAPODataSession
from service import ODataService, escape_odata_literal

cfg = ODataConfig(
    base_url="https://coeportal515.saphosting.de/sap/opu/odata/sap",
    auth=ODataAuth("basic", ("ASEPA", "Password1")),   # or ODataAuth("bearer", "<token>")
    default_sap_client="600",
    verify=True,
)

with SAPODataSession(cfg) as sess:
    api = ODataService(sess, "API_MAINTENANCEORDER_SRV")

    # Discover what’s available
    print(api.list_entity_sets())
    print(api.list_fields("A_MaintenanceOrder"))

    # Query any entity set + fields you pass
    items = api.query(
        "A_MaintenanceOrder",
        fields=["MaintenanceOrder", "OrderType", "CompanyCode", "MaintenancePlant"],
        filter_expr=f"CompanyCode eq '{escape_odata_literal('1000')}'",
        top=50,
        orderby="MaintenanceOrder desc",
    )
    print(len(items), items[:2])
