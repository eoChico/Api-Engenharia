import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import (
    CashierUser,
    DbSession,
    FloorUser,
    ManagerUser,
    Meta,
    StaffUser,
    WaiterUser,
)
from app.models.user import UserRole
from app.schemas.order import (
    CloseCheckResult,
    OpenTableRequest,
    SessionDetail,
    TransferRequest,
)
from app.schemas.restaurant_table import TableCreate, TableRead, TableSummary, TableUpdate
from app.services import session_service, table_service

router = APIRouter(prefix='/tables', tags=['tables'])


@router.post('', response_model=TableRead, status_code=status.HTTP_201_CREATED)
async def create_table(data: TableCreate, actor: ManagerUser, db: DbSession, meta: Meta):
    try:
        return await table_service.create_table(db, data, actor, meta.ip)
    except table_service.TableNumberAlreadyExistsError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, 'Já existe uma mesa com esse número'
        ) from None


@router.get('', response_model=list[TableSummary])
async def list_tables(
    actor: StaffUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_inactive: bool = False,
):
    if include_inactive and actor.role != UserRole.MANAGER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Apenas o gerente vê mesas inativas')
    return await session_service.list_table_overview(db, limit, offset, include_inactive)


@router.get('/{table_id}', response_model=TableRead)
async def get_table(table_id: uuid.UUID, actor: StaffUser, db: DbSession):
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


# ---------- atendimento ----------

@router.post('/{table_id}/open', response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
async def open_table(
    table_id: uuid.UUID, data: OpenTableRequest, actor: WaiterUser, db: DbSession, meta: Meta
):
    return await session_service.open_table(db, table_id, data, actor, meta.ip)


@router.get('/{table_id}/session', response_model=SessionDetail)
async def get_session(table_id: uuid.UUID, actor: StaffUser, db: DbSession):
    return await session_service.get_session_detail(db, table_id, actor)


@router.post('/{table_id}/session/checks', response_model=SessionDetail)
async def add_check(table_id: uuid.UUID, actor: FloorUser, db: DbSession, meta: Meta):
    return await session_service.add_check(db, table_id, actor, meta.ip)


@router.post('/{table_id}/session/request-bill', response_model=SessionDetail)
async def request_bill(table_id: uuid.UUID, actor: FloorUser, db: DbSession, meta: Meta):
    return await session_service.request_bill(db, table_id, actor, meta.ip)


@router.post('/{table_id}/session/cancel', status_code=status.HTTP_204_NO_CONTENT)
async def cancel_session(table_id: uuid.UUID, actor: FloorUser, db: DbSession, meta: Meta):
    await session_service.cancel_session(db, table_id, actor, meta.ip)


@router.post('/{table_id}/session/transfer', response_model=SessionDetail)
async def transfer_session(
    table_id: uuid.UUID, data: TransferRequest, actor: ManagerUser, db: DbSession, meta: Meta
):
    return await session_service.transfer_session(db, table_id, data.waiter_id, actor, meta.ip)


@router.post(
    '/{table_id}/session/checks/{check_id}/close', response_model=CloseCheckResult
)
async def close_check(
    table_id: uuid.UUID, check_id: uuid.UUID, actor: CashierUser, db: DbSession, meta: Meta
):
    return await session_service.close_check(db, table_id, check_id, actor, meta.ip)
