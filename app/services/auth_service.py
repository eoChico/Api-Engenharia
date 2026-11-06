import uuid
from datetime import datetime, timedelta, timezone

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.request_meta import RequestMeta
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair
from app.services import audit_service


class InvalidCredentialsError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- helpers ----------

def _issue_refresh_token(
    db: AsyncSession,
    user: User,
    family_id: uuid.UUID,
    family_started_at: datetime,
    meta: RequestMeta,
) -> str:
    now = utcnow()
    raw = generate_refresh_token()
    expires_at = min(
        now + timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS),
        family_started_at + timedelta(days=settings.REFRESH_ABSOLUTE_LIFETIME_DAYS),
    )
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id,
            token_hash=hash_refresh_token(raw),
            family_started_at=family_started_at,
            expires_at=expires_at,
            ip=meta.ip,
            user_agent=(meta.user_agent or "")[:255] or None,
        )
    )
    return raw


def _pair(user: User, raw_refresh: str) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), user.token_version),
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def _revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def revoke_all_for_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def _get_refresh_token(db: AsyncSession, raw: str, lock: bool = False) -> RefreshToken | None:
    stmt = select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))
    if lock:
        stmt = stmt.with_for_update()  # serializa refreshes concorrentes do mesmo token
    return (await db.execute(stmt)).scalar_one_or_none()


# ---------- login ----------

async def login(db: AsyncSession, email: str, password: str, meta: RequestMeta) -> TokenPair:
    from app.services import user_service  # evita import circular

    now = utcnow()
    user = await user_service.get_by_email(db, email)

    if user is None:
        await run_in_threadpool(verify_password, password, DUMMY_HASH)
        audit_service.record(db, "login_failed", ip=meta.ip, detail={"email": email[:255]})
        await db.commit()
        raise InvalidCredentialsError

    if user.locked_until is not None and user.locked_until > now:
        await run_in_threadpool(verify_password, password, DUMMY_HASH)
        audit_service.record(db, "login_blocked", actor_id=user.id, ip=meta.ip)
        await db.commit()
        raise InvalidCredentialsError  # mesma resposta: não revela o bloqueio

    password_ok = await run_in_threadpool(verify_password, password, user.hashed_password)
    if not password_ok:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
            audit_service.record(db, "account_locked", actor_id=user.id, ip=meta.ip)
        audit_service.record(db, "login_failed", actor_id=user.id, ip=meta.ip)
        await db.commit()
        raise InvalidCredentialsError

    if not user.is_active:
        audit_service.record(db, "login_inactive", actor_id=user.id, ip=meta.ip)
        await db.commit()
        raise InvalidCredentialsError  # não confirma que a senha estava certa

    user.failed_login_attempts = 0
    user.locked_until = None
    raw = _issue_refresh_token(db, user, uuid.uuid4(), now, meta)
    audit_service.record(db, "login_success", actor_id=user.id, ip=meta.ip)
    await db.commit()
    return _pair(user, raw)


# ---------- refresh com rotação e detecção de reuso ----------

async def refresh(db: AsyncSession, raw_token: str, meta: RequestMeta) -> TokenPair:
    now = utcnow()
    token = await _get_refresh_token(db, raw_token, lock=True)
    if token is None:
        raise InvalidRefreshTokenError

    if token.revoked_at is not None:
        raise InvalidRefreshTokenError

    if token.used_at is not None:
        # Token já rotacionado sendo apresentado de novo.
        # Dentro da janela de tolerância = duas abas/requisições concorrentes (inofensivo).
        # Fora dela = possível roubo: revoga a sessão inteira.
        if now - token.used_at > timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS):
            await _revoke_family(db, token.family_id)
            audit_service.record(
                db, "refresh_reuse_detected", actor_id=token.user_id, ip=meta.ip
            )
            await db.commit()
        raise InvalidRefreshTokenError

    family_end = token.family_started_at + timedelta(days=settings.REFRESH_ABSOLUTE_LIFETIME_DAYS)
    if token.expires_at <= now or family_end <= now:
        raise InvalidRefreshTokenError

    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        await _revoke_family(db, token.family_id)
        await db.commit()
        raise InvalidRefreshTokenError

    token.used_at = now
    raw = _issue_refresh_token(db, user, token.family_id, token.family_started_at, meta)
    await db.commit()
    return _pair(user, raw)


# ---------- logout / senha ----------

async def logout(db: AsyncSession, raw_token: str, meta: RequestMeta) -> None:
    """Idempotente: sempre 'sucesso', para não servir de oráculo de tokens."""
    token = await _get_refresh_token(db, raw_token)
    if token is not None:
        await _revoke_family(db, token.family_id)
        audit_service.record(db, "logout", actor_id=token.user_id, ip=meta.ip)
        await db.commit()


async def logout_all(db: AsyncSession, user: User, meta: RequestMeta) -> None:
    user.token_version += 1
    await revoke_all_for_user(db, user.id)
    audit_service.record(db, "logout_all", actor_id=user.id, ip=meta.ip)
    await db.commit()


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str, meta: RequestMeta
) -> None:
    if not await run_in_threadpool(verify_password, current_password, user.hashed_password):
        audit_service.record(db, "password_change_failed", actor_id=user.id, ip=meta.ip)
        await db.commit()
        raise InvalidCredentialsError

    user.hashed_password = await run_in_threadpool(hash_password, new_password)
    user.token_version += 1
    await revoke_all_for_user(db, user.id)
    audit_service.record(db, "password_changed", actor_id=user.id, ip=meta.ip)
    await db.commit()
