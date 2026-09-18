import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone

from app.gateways.doku.client import DokuDirectClient
from app.core.config import Settings


def test_doku_notification_signature_uses_request_target_and_digest():
    settings = Settings(doku_client_id="client", doku_secret_key="secret")
    body = json.dumps({"order": {"invoice_number": "PAY-1"}}, separators=(",", ":")).encode()
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    headers = {"client-id": "client", "request-id": "req-1", "request-timestamp": timestamp}
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    component = "Client-Id:client\nRequest-Id:req-1\nRequest-Timestamp:" + timestamp + "\nRequest-Target:/api/v1/webhooks/doku/test\nDigest:" + digest
    headers["signature"] = "HMACSHA256=" + base64.b64encode(hmac.new(b"secret", component.encode(), hashlib.sha256).digest()).decode()
    assert DokuDirectClient.verify_notification_signature(headers, body, "/api/v1/webhooks/doku/test", settings)


def test_doku_notification_rejects_stale_timestamp():
    settings = Settings(doku_client_id="client", doku_secret_key="secret")
    headers = {"client-id": "client", "request-id": "req-1", "request-timestamp": "2020-01-01T00:00:00Z", "signature": "bad"}
    assert not DokuDirectClient.verify_notification_signature(headers, b"{}", "/api/v1/webhooks/doku/test", settings)
