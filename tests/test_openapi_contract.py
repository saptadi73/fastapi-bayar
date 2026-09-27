from app.main import app
from app.schemas.common import ErrorBody


def test_active_admin_and_system_paths_are_published_in_openapi():
    paths = app.openapi()["paths"]
    expected = {
        "/health", "/health/database", "/health/ready",
        "/api/v1/admin/clients",
        "/api/v1/admin/clients/{client_id}/events",
        "/api/v1/admin/clients/{client_id}/portal-users",
        "/api/v1/admin/clients/{client_id}/portal-users/{user_id}",
        "/api/v1/admin/clients/{client_id}/merchant-accounts",
        "/api/v1/admin/clients/{client_id}/merchant-accounts/{account_id}",
        "/api/v1/admin/clients/{client_id}/organizers",
        "/api/v1/admin/clients/{client_id}/organizers/{organizer_id}",
        "/api/v1/admin/clients/{client_id}/payment-channels",
        "/api/v1/admin/clients/{client_id}/payment-channels/{channel_id}",
        "/api/v1/admin/clients/{client_id}/routing-rules",
        "/api/v1/admin/clients/{client_id}/routing-rules/{rule_id}",
        "/api/v1/admin/clients/{client_id}/feature-flags",
        "/api/v1/admin/clients/{client_id}/revoke-checkouts",
        "/api/v1/admin/clients/{client_id}/rotate-callback-secret",
        "/api/v1/admin/payments", "/api/v1/admin/payments/export",
        "/api/v1/admin/payments/summary", "/api/v1/admin/reconciliation",
        "/api/v1/admin/refunds",
    }
    assert expected <= paths.keys()

    portal_user = paths["/api/v1/admin/clients/{client_id}/portal-users/{user_id}"]
    assert {"patch", "delete"} <= portal_user.keys()


def test_error_envelope_documents_request_id():
    schema = ErrorBody.model_json_schema()
    assert set(schema["properties"]) == {"code", "message", "request_id", "details"}
    assert set(schema["required"]) == {"code", "message", "request_id"}


def test_payment_list_and_export_publish_search_contract():
    paths = app.openapi()["paths"]
    for path in ("/api/v1/admin/payments", "/api/v1/admin/payments/export"):
        parameters = paths[path]["get"]["parameters"]
        names = {parameter["name"] for parameter in parameters}
        assert {"search", "limit"} <= names

    responses = paths["/api/v1/admin/payments"]["get"]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith("PageResponse_PaymentView_")
    export_responses = paths["/api/v1/admin/payments/export"]["get"]["responses"]
    assert export_responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith("PaymentExportResponse")

