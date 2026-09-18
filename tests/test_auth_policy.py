from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.core.security import timestamp_is_valid


@pytest.mark.parametrize("stamp", ["bad", "2026-01-01T12:00:00", "", None])
def test_bad_timestamp_rejected_without_server_error(stamp):
    assert not timestamp_is_valid(stamp)


def test_timestamp_window():
    now = datetime.now(timezone.utc)
    assert timestamp_is_valid(now.isoformat())
    assert not timestamp_is_valid((now - timedelta(hours=1)).isoformat())
    assert not timestamp_is_valid((now + timedelta(hours=1)).isoformat())


@pytest.mark.parametrize("changes", [
    {"auth_enabled": False}, {"auto_create_tables": True}, {"APP_DEBUG": True},
    {"db_echo": True}, {"public_base_url": "http://example.com"},
    {"nonce_ttl_seconds": 100},
])
def test_production_rejects_unsafe_runtime(changes):
    values = dict(environment="production", auth_enabled=True, auto_create_tables=False,
                  APP_DEBUG=False, db_echo=False, public_base_url="https://example.com",
                  client_api_secret="test-configured-secret", jwt_secret="test-only-" * 8)
    values.update(changes)
    with pytest.raises(ValueError):
        Settings(_env_file=None, **values).validate_production()


def test_production_valid_configuration():
    Settings(_env_file=None, environment="production", auth_enabled=True, auto_create_tables=False,
             APP_DEBUG=False, db_echo=False, public_base_url="https://example.com",
             client_api_secret="test-configured-secret", jwt_secret="test-only-" * 8).validate_production()
