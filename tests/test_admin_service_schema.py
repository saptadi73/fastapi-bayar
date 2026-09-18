import pytest
from pydantic import ValidationError
from app.schemas.admin_service import CreateService, UpdateService


@pytest.mark.parametrize("field,value", [("name", "  "), ("reason", ""),
                                        ("code", "bad/code"), ("active", "false"),
                                        ("client_id", "injected")])
def test_service_schema_rejects_bad_input(field, value):
    body = {"code": "TICKET", "name": "Ticket", "active": True, "reason": "Register"}
    body[field] = value
    with pytest.raises(ValidationError):
        CreateService(**body)


def test_service_update_normalizes_labels_and_rejects_boolean_version():
    body = {"name": " Ticket ", "active": False, "reason": " Pause ", "expected_version": 1}
    parsed = UpdateService(**body)
    assert parsed.name == "Ticket" and parsed.reason == "Pause"
    with pytest.raises(ValidationError):
        UpdateService(**{**body, "expected_version": True})
