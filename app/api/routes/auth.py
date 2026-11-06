from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession, Meta
from app.core.config import settings
from app.core.limiter import limiter
from app.schemas.auth import ChangePasswordRequest, RefreshRequest, TokenPair
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_BEARER = {"WWW-Authenticate": "Bearer"}


@router.post("/login", response_model=TokenPair)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(
    request: Request,  # exigido pelo slowapi
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
    meta: Meta,
):
    # OAuth2 exige o campo "username"; aqui ele carrega o e-mail.
    try:
        return await auth_service.login(db, form.username, form.password, meta)
    except auth_service.InvalidCredentialsError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos", headers=_BEARER
        ) from None


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(settings.REFRESH_RATE_LIMIT)
async def refresh(request: Request, body: RefreshRequest, db: DbSession, meta: Meta):
    try:
        return await auth_service.refresh(db, body.refresh_token, meta)
    except auth_service.InvalidRefreshTokenError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Faça login novamente.", headers=_BEARER
        ) from None


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: DbSession, meta: Meta):
    await auth_service.logout(db, body.refresh_token, meta)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: CurrentUser, db: DbSession, meta: Meta):
    await auth_service.logout_all(db, user, meta)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: ChangePasswordRequest, user: CurrentUser, db: DbSession, meta: Meta):
    try:
        await auth_service.change_password(
            db, user, body.current_password, body.new_password, meta
        )
    except auth_service.InvalidCredentialsError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha atual incorreta") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser):
    return user
