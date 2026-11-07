import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant_table import RestaurantTable
from app.models.user import User
from app.schemas.restaurant_table import TableCreate, TableUpdate
from app.services import audit_service


class TableNumberAlreadyExistsError(Exception):
    pass


async def list_tables(
    db: AsyncSession, limit: int, offset: int, include_inactive: bool
) -> list[RestaurantTable]:
    stmt = select(RestaurantTable).order_by(RestaurantTable.number)
    if not include_inactive:
        stmt = stmt.where(RestaurantTable.is_active.is_(True))
    result = await db.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars())


async def get_table(
    db: AsyncSession, table_id: uuid.UUID, include_inactive: bool
) -> RestaurantTable | None:
    table = await db.get(RestaurantTable, table_id)
    if table is None or (not table.is_active and not include_inactive):
        return None  # para quem não pode ver inativas, é como se não existisse
    return table


async def create_table(
    db: AsyncSession, data: TableCreate, actor: User, ip: str | None
) -> RestaurantTable:
    table = RestaurantTable(number=data.number, seats=data.seats)
    db.add(table)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise TableNumberAlreadyExistsError from None

    audit_service.record(
        db,
        'table_created',
        actor_id=actor.id,
        target_id=table.id,
        ip=ip,
        detail={'number': table.number, 'seats': table.seats},
    )
    await db.commit()
    await db.refresh(table)
    return table


async def update_table(
    db: AsyncSession,
    table: RestaurantTable,
    data: TableUpdate,
    actor: User,
    ip: str | None,
) -> RestaurantTable:
    changes = {k: getattr(data, k) for k in data.model_fields_set}
    before = {k: getattr(table, k) for k in changes}

    for key, value in changes.items():
        setattr(table, key, value)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise TableNumberAlreadyExistsError from None

    audit_service.record(
        db,
        'table_updated',
        actor_id=actor.id,
        target_id=table.id,
        ip=ip,
        detail={'before': before, 'after': changes},
    )
    await db.commit()
    await db.refresh(table)
    return table
