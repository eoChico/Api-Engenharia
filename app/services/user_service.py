import uuid

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdateAdmin
from app.services import audit_service
from app.services.auth_service import utcnow


class EmailAlreadyExistsError(Exception):
    pass


class CannotModifySelfError(Exception):
    pass


class LastManagerError(Exception):
    pass


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def list_users(db: AsyncSession, limit: int, offset: int) -> list[User]:
    result = await db.execute(
        select(User).order_by(User.created_at).limit(limit).offset(offset)
    )
    return list(result.scalars())


async def create_user(
    db: AsyncSession, data: UserCreate, actor: User | None, ip: str | None
) -> User:
    user = User(
        name=data.name.strip(),
        email=data.email.lower(),
        hashed_password=await run_in_threadpool(hash_password, data.password),
        role=data.role,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise EmailAlreadyExistsError from None

    audit_service.record(
        db,
        "user_created",
        actor_id=actor.id if actor else None,
        target_id=user.id,
        ip=ip,
        detail={"role": user.role.value},
    )
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession, target: User, data: UserUpdateAdmin, actor: User, ip: str | None
) -> User:
    changes = {k: getattr(data, k) for k in data.model_fields_set}
    sensitive = {
        k for k in ("role", "is_active") if k in changes and changes[k] != getattr(target, k)
    }

    # Gerente não rebaixa nem desativa a si mesmo.
    if target.id == actor.id and sensitive:
        raise CannotModifySelfError

    # Nunca ficar sem gerente ativo. O lock evita que dois gerentes se
    # rebaixem ao mesmo tempo e deixem o sistema sem nenhum.
    loses_manager = target.role == UserRole.MANAGER and target.is_active and (
        changes.get("role", target.role) != UserRole.MANAGER
        or changes.get("is_active", target.is_active) is False
    )
    if loses_manager:
        result = await db.execute(
            select(User.id)
            .where(User.role == UserRole.MANAGER, User.is_active.is_(True))
            .with_for_update()
        )
        if len(result.scalars().all()) <= 1:
            await db.rollback()
            raise LastManagerError

    before = {k: str(getattr(target, k)) for k in changes}
    for key, value in changes.items():
        setattr(target, key, value.strip() if key == "name" else value)

    # Mudou papel ou status: derruba access tokens e todas as sessões.
    if sensitive:
        target.token_version += 1
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == target.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )

    audit_service.record(
        db,
        "user_updated",
        actor_id=actor.id,
        target_id=target.id,
        ip=ip,
        detail={"before": before, "after": {k: str(v) for k, v in changes.items()}},
    )
    await db.commit()
    await db.refresh(target)
    return target
