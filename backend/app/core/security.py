import os
from dataclasses import dataclass
from typing import Iterable, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


security_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    token_name: str
    roles: Set[str]


def _parse_token_config() -> dict[str, Principal]:
    """
    LIC_API_TOKENS format:
    token-name:secret:role1,role2;admin:another-secret:admin,operator
    """
    configured = os.environ.get("LIC_API_TOKENS", "")
    principals: dict[str, Principal] = {}

    for item in configured.split(";"):
        if not item.strip():
            continue
        parts = item.split(":", 2)
        if len(parts) != 3:
            continue
        token_name, token_value, roles = parts
        principals[token_value] = Principal(
            token_name=token_name,
            roles={role.strip() for role in roles.split(",") if role.strip()},
        )

    return principals


def _auth_disabled() -> bool:
    return os.environ.get("LIC_DISABLE_AUTH", "").lower() in {"1", "true", "yes"}


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> Principal:
    if _auth_disabled():
        return Principal(token_name="development", roles={"admin", "operator", "viewer"})

    principals = _parse_token_config()
    if not principals:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    principal = principals.get(credentials.credentials)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return principal


def require_roles(*required_roles: str):
    required = set(required_roles)

    async def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if required and not principal.roles.intersection(required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of these roles: {', '.join(sorted(required))}",
            )
        return principal

    return dependency
