import base64
import hashlib
import hmac
import struct
import time


def new_secret() -> str:
    import secrets
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def code(secret: str, timestamp: int | None = None) -> str:
    raw = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    counter = int((timestamp or int(time.time())) // 30)
    digest = hmac.new(raw, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff) % 1000000
    return f"{value:06d}"


def verify(secret: str, supplied: str, timestamp: int | None = None) -> bool:
    supplied = supplied.strip()
    return any(hmac.compare_digest(code(secret, (timestamp or int(time.time())) + step * 30), supplied)
               for step in (-1, 0, 1))
