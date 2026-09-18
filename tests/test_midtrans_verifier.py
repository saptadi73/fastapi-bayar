import hashlib

from app.gateways.midtrans.verifier import verify_legacy_notification


def test_midtrans_legacy_signature():
    server_key = "server-secret"
    payload = {"order_id": "PAY-1", "status_code": "200", "gross_amount": "100000.00"}
    raw = payload["order_id"] + payload["status_code"] + payload["gross_amount"] + server_key
    payload["signature_key"] = hashlib.sha512(raw.encode()).hexdigest()
    assert verify_legacy_notification(payload, server_key)
