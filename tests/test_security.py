from app.core.security import build_canonical, sign


def test_canonical_signature_is_deterministic():
    canonical = build_canonical("POST", "/api/v1/client/payments", "EVENT-CLIENT", "key-1", "2026-09-18T07:30:00Z", "nonce-1", b'{"amount":100}')
    assert sign(canonical, "secret") == sign(canonical, "secret")
    assert sign(canonical, "secret") != sign(canonical, "other-secret")

