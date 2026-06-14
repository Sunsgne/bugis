"""Audit middleware: persists mutating API calls."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.audit import AuditLog

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# Skip noisy / non-audit-worthy paths.
_SKIP_PREFIXES = ("/api/v1/auth/login",)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        try:
            if (
                request.method in _MUTATING
                and request.url.path.startswith("/api/")
                and not any(request.url.path.startswith(p) for p in _SKIP_PREFIXES)
            ):
                self._record(request, response.status_code)
        except Exception:
            # Auditing must never break the request path.
            pass
        return response

    def _record(self, request: Request, status_code: int) -> None:
        actor = "anonymous"
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            sub = decode_access_token(auth.split(" ", 1)[1])
            if sub:
                actor = sub
        wh = request.headers.get("x-webhook-token")
        if wh:
            actor = "webhook"
        client_ip = request.client.host if request.client else None
        db = SessionLocal()
        try:
            db.add(
                AuditLog(
                    actor=actor,
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    source_ip=client_ip,
                )
            )
            db.commit()
        finally:
            db.close()
