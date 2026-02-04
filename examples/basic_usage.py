"""
Example: Basic OData usage with sap_ds
======================================

This example shows how to use sap_ds for generic OData queries.
"""

from sap_ds import ODataConfig, ODataAuth, SAPODataSession
from sap_ds.odata import ODataService, escape_odata_literal


def example_basic_query():
    """Basic OData query example."""
    
    cfg = ODataConfig(
        base_url="https://your-s4.example.com/sap/opu/odata/sap/",
        auth=ODataAuth("basic", ("USER", "PASSWORD")),
        default_sap_client="100",
        verify=True,
    )

    with SAPODataSession(cfg) as sess:
        api = ODataService(sess, "API_MAINTENANCEORDER_SRV")

        # Discover what's available
        print("Entity Sets:", api.list_entity_sets())
        print("Fields:", api.list_fields("A_MaintenanceOrder"))

        # Query any entity set with fields you pass
        items = api.query(
            "A_MaintenanceOrder",
            fields=["MaintenanceOrder", "OrderType", "CompanyCode", "MaintenancePlant"],
            filter_expr=f"CompanyCode eq '{escape_odata_literal('1000')}'",
            top=50,
            orderby="MaintenanceOrder desc",
        )
        print(f"Found {len(items)} orders")
        print("First 2:", items[:2])


def example_connection_context():
    """Using ConnectionContext (hana_ml style)."""
    from sap_ds import ConnectionContext
    
    # Reads from environment variables: S4_BASE_URL, S4_USER, S4_PASS, S4_SAP_CLIENT
    with ConnectionContext() as conn:
        service = conn.get_service("API_MAINTENANCEORDER_SRV")
        orders = service.query("A_MaintenanceOrder", top=10)
        print(f"Found {len(orders)} orders")


def example_force_elements():
    """Using Defense & Security Force Elements client."""
    from sap_ds import ConnectionContext
    from sap_ds.defense import ForceElementClient
    
    with ConnectionContext() as conn:
        force = ForceElementClient(conn)
        
        # Get all force elements
        elements = force.get_force_elements(top=100)
        print(f"Found {len(elements)} force elements")
        
        # Get specific unit
        if elements:
            unit_id = elements[0].get("ForceElementID")
            unit = force.get_force_element(unit_id)
            print(f"Unit: {unit}")
            
            # Convert to typed object
            fe = force.to_dataclass(unit)
            print(f"Force Element: {fe.name} ({fe.type})")


if __name__ == "__main__":
    # Uncomment the example you want to run
    # example_basic_query()
    # example_connection_context()
    # example_force_elements()
    
    print("Set up your environment variables and uncomment an example to run.")
    print("Required: S4_BASE_URL, S4_USER, S4_PASS (or S4_BEARER_TOKEN)")
