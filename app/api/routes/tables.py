import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, ManagerUser, Meta, require_roles
from app.models.user import User, UserRole
from app.schemas.restaurant_table import TableCreate, TableRead, TableUpdate
from app.services import table_service

router = APIRouter(prefix='/tables', tags=['tables'])

Staff = Annotated[
    User,
    Depends(require_roles(UserRole.MANAGER, UserRole.WAITER, UserRole.CASHIER)),
]


@router.post('', response_model=TableRead, status_code=status.HTTP_201_CREATED)
async def create_table(data: TableCreate, actor: ManagerUser, db: DbSession, meta: Meta):
    try:
        return await table_service.create_table(db, data, actor, meta.ip)
    except table_service.TableNumberAlreadyExistsError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'Já existe uma mesa com esse número'
        ) from None


@router.get('', response_model=list[TableRead])
async def list_tables(
    actor: Staff,
    db: DbSession,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_inactive: bool = False,
):
    if include_inactive and actor.role != UserRole.MANAGER:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, 'Apenas o gerente vê mesas inativas'
        )
    return await table_service.list_tables(db, limit, offset, include_inactive)


@router.get('/{table_id}', response_model=TableRead)
async def get_table(table_id: uuid.UUID, actor: Staff, db: DbSession):
    table = await table_service.get_table(
        db, table_id, include_inactive=actor.role == UserRole.MANAGER
    )
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Mesa não encontrada')
    return table


@router.patch('/{table_id}', response_model=TableRead)
async def update_table(
    table_id: uuid.UUID, data: TableUpdate, actor: ManagerUser, db: DbSession, meta: Meta
):
    table = await table_service.get_table(db, table_id, include_inactive=True)
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Mesa não encontrada')
    try:
        return await table_service.update_table(db, table, data, actor, meta.ip)
    except table_service.TableNumberAlreadyExistsError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'Já existe uma mesa com esse número'
        ) from None
