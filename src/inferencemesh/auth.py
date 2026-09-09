"""Authentication for model APIs and a separately protected metrics endpoint."""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException

from inferencemesh.config import Settings


@dataclass(frozen=True, slots=True)
class Principal:
    tenant_id: str


class ApiKeyAuthenticator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @staticmethod
    def _supplied(authorization: str | None, x_api_key: str | None) -> str | None:
        if authorization and authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return x_api_key

    async def authenticate(
        self,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> Principal:
        if not self._settings.require_api_key:
            return Principal("local-demo")
        supplied = self._supplied(authorization, x_api_key)
        if not supplied or not hmac.compare_digest(
            supplied.encode(), self._settings.api_key.encode()
        ):
            raise HTTPException(
                401, detail={"message": "invalid API key", "type": "authentication_error"}
            )
        return Principal("configured-tenant")

    async def authenticate_metrics(
        self,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> Principal:
        key = self._settings.metrics_api_key
        supplied = self._supplied(authorization, x_api_key)
        if not key:
            raise HTTPException(404, detail="metrics endpoint is disabled")
        if not supplied or not hmac.compare_digest(supplied.encode(), key.encode()):
            raise HTTPException(401, detail="invalid metrics key")
        return Principal("metrics")
