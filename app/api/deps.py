import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_meta import RequestMeta
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_request_meta(request: Request) -> RequestMeta:
    return RequestMeta(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


Meta = Annotated[RequestMeta, Depends(get_request_meta)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise credentials_error from None

    # Papel e status SEMPRE vêm do banco, nunca do token.
    user = await db.get(User, user_id)
    if user is None or not user.is_active or payload["tv"] != user.token_version:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    async def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para esta ação",
            )
        return user

    return checker


ManagerUser = Annotated[User, Depends(require_roles(UserRole.MANAGER))]

WaiterUser = Annotated[User, Depends(require_roles(UserRole.WAITER))]
FloorUser = Annotated[User, Depends(require_roles(UserRole.WAITER, UserRole.MANAGER))]
StaffUser = Annotated[
    User, Depends(require_roles(UserRole.MANAGER, UserRole.WAITER, UserRole.CASHIER))
]
CashierUser = Annotated[User, Depends(require_roles(UserRole.CASHIER, UserRole.MANAGER))]
KitchenUser = Annotated[User, Depends(require_roles(UserRole.KITCHEN, UserRole.MANAGER))]
OrderActor = Annotated[
    User, Depends(require_roles(UserRole.WAITER, UserRole.KITCHEN, UserRole.MANAGER))
]
