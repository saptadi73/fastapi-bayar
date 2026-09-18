import base64
import hashlib
import hmac
from datetime import datetime, timezone

from app.core.config import get_settings


def build_canonical(method: str, path: str, client_id: str, key_id: str, timestamp: str, nonce: str, body: bytes) -> str:
    body_digest = hashlib.sha256(body).hexdigest()
    return "\n".join([method.upper(), path, client_id, key_id, timestamp, nonce, body_digest])


def sign(canonical: str, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).digest()).decode()


def timestamp_is_valid(value: str) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return False
        return abs((datetime.now(timezone.utc) - parsed).total_seconds()) <= get_settings().hmac_clock_skew_seconds
    except (ValueError, TypeError, OverflowError):
        return False
