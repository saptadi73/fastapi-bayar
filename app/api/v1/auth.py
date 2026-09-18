import base64
from urllib.parse import unquote
from fastapi import APIRouter, Depends, Form, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.access import SCOPES, hash_secret, issue_access_token, verify_secret
from app.core.config import get_settings
from app.core.database import get_db
from app.models.payment import Client

router = APIRouter(prefix="/oauth", tags=["Authentication"])
DUMMY_HASH = hash_secret("not-a-real-client-secret")


def oauth_error(code, status=400):
    return JSONResponse(status_code=status, content={"error": code},
                        headers={"Cache-Control": "no-store", "Pragma": "no-cache",
                                 **({"WWW-Authenticate": 'Basic realm="payment-token"'} if status == 401 else {})})


@router.post("/token")
async def token(grant_type: str = Form(...), scope: str = Form(""),
                authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)):
    if grant_type != "client_credentials":
        return oauth_error("unsupported_grant_type")
    try:
        scheme, value = (authorization or "").split(" ", 1)
        if scheme.lower() != "basic" or len(value) > 2048:
            raise ValueError()
        code, secret = base64.b64decode(value, validate=True).decode().split(":", 1)
        code, secret = unquote(code), unquote(secret)
        if not code or not secret or len(secret) > 256:
            raise ValueError()
    except (ValueError, UnicodeError):
        return oauth_error("invalid_client", 401)
    client = await db.scalar(select(Client).where(Client.code == code))
    valid = await run_in_threadpool(verify_secret, secret, client.oauth_secret_hash if client and client.oauth_secret_hash else DUMMY_HASH)
    if not valid or not client or not client.active or not client.oauth_secret_hash:
        return oauth_error("invalid_client", 401)
    permitted = set(client.allowed_scopes.split()) & SCOPES
    requested = set(scope.split()) if scope else permitted
    if not requested or not requested <= permitted:
        return oauth_error("invalid_scope")
    return JSONResponse({"access_token": issue_access_token(client, requested), "token_type": "Bearer",
                         "expires_in": get_settings().access_token_ttl_seconds, "scope": " ".join(sorted(requested))},
                        headers={"Cache-Control": "no-store", "Pragma": "no-cache"})

