"""Small authentication boundary for local and initial public deployments."""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from inferencemesh.config import Settings


@dataclass(frozen=True, slots=True)
class Principal:
    tenant_id: str


class ApiKeyAuthenticator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate(
        self,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> Principal:
        if not self._settings.require_api_key:
            return Principal(tenant_id="local-demo")

        bearer = None
        if authorization and authorization.lower().startswith("bearer "):
            bearer = authorization[7:].strip()
        supplied = bearer or x_api_key
        if not supplied or not hmac.compare_digest(supplied, self._settings.api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "invalid API key", "type": "authentication_error"},
            )
        return Principal(tenant_id="configured-tenant")
