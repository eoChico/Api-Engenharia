import uuid
from collections import defaultdict

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order_item import OrderItem, OrderItemStatus
from app.models.restaurant_table import RestaurantTable
from app.models.table_check import TableCheck
from app.models.table_session import TableSession
from app.models.user import User, UserRole
from app.schemas.order import (
    CheckRead,
    CloseCheckResult,
    OpenTableRequest,
    OrderItemRead,
    SessionDetail,
)
from app.schemas.restaurant_table import TableStatus, TableSummary
from app.services import audit_service
from app.services.auth_service import utcnow
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.item_rules import NOT_OWNER

MAX_CHECKS = 10
# Itens que a mesa ainda está esperando (não entregues e não cancelados).
OPEN_ITEM_STATUSES = (OrderItemStatus.PENDING, OrderItemStatus.PREPARING, OrderItemStatus.READY)


# ---------- permissões ----------

def ensure_can_act(session: TableSession, actor: User) -> None:
    """Quem pode mexer no atendimento: o garçom dono ou o gerente."""
    if actor.role == UserRole.MANAGER:
        return
    if actor.role == UserRole.WAITER and session.waiter_id == actor.id:
        return
    raise ForbiddenError(NOT_OWNER)


def ensure_can_view(session: TableSession, actor: User) -> None:
    if actor.role in (UserRole.MANAGER, UserRole.CASHIER):
        return
    ensure_can_act(session, actor)


# ---------- helpers ----------

def _derive_status(session: TableSession | None) -> TableStatus:
    if session is None:
        return TableStatus.FREE
    if session.bill_requested_at is not None:
        return TableStatus.BILL_REQUESTED
    return TableStatus.OCCUPIED


async def _get_table(db: AsyncSession, table_id: uuid.UUID) -> RestaurantTable:
    table = await db.get(RestaurantTable, table_id)
    if table is None:
        raise NotFoundError('Mesa não encontrada')
    return table


async def _load_open(
    db: AsyncSession, table_id: uuid.UUID
) -> tuple[RestaurantTable, TableSession, str]:
    table = await _get_table(db, table_id)
    row = (
        await db.execute(
            select(TableSession, User.name)
            .join(User, User.id == TableSession.waiter_id)
            .where(TableSession.table_id == table_id, TableSession.closed_at.is_(None))
        )
    ).first()
    if row is None:
        raise NotFoundError('Esta mesa não tem atendimento aberto')
    return table, row[0], row[1]


async def _lock_open_session(db: AsyncSession, table_id: uuid.UUID) -> TableSession:
    """Trava a linha do atendimento até o commit: serializa pedir conta, lançar item e fechar."""
    session = (
        await db.execute(
            select(TableSession)
            .where(TableSession.table_id == table_id, TableSession.closed_at.is_(None))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if session is None:
        raise NotFoundError('Esta mesa não tem atendimento aberto')
    return session


async def _count_items(db: AsyncSession, session_id: uuid.UUID, *conditions) -> int:
    result = await db.scalar(
        select(func.count(OrderItem.id))
        .select_from(OrderItem)
        .join(TableCheck, TableCheck.id == OrderItem.check_id)
        .where(TableCheck.session_id == session_id, *conditions)
    )
    return result or 0


async def _build_detail(
    db: AsyncSession, table: RestaurantTable, session: TableSession, waiter_name: str
) -> SessionDetail:
    checks = list(
        (
            await db.execute(
                select(TableCheck)
                .where(TableCheck.session_id == session.id)
                .order_by(TableCheck.number)
            )
        ).scalars()
    )
    items = list(
        (
            await db.execute(
                select(OrderItem)
                .join(TableCheck, TableCheck.id == OrderItem.check_id)
                .where(TableCheck.session_id == session.id)
                .order_by(OrderItem.created_at)
            )
        ).scalars()
    )
    by_check: dict[uuid.UUID, list[OrderItem]] = defaultdict(list)
    for item in items:
        by_check[item.check_id].append(item)

    check_reads: list[CheckRead] = []
    for check in checks:
        check_items = by_check.get(check.id, [])
        if check.total_cents is not None:
            total = check.total_cents
        else:
            total = sum(
                i.unit_price_cents * i.quantity
                for i in check_items
                if i.status != OrderItemStatus.CANCELED
            )
        check_reads.append(
            CheckRead(
                id=check.id,
                number=check.number,
                closed_at=check.closed_at,
                total_cents=total,
                items=[OrderItemRead.model_validate(i) for i in check_items],
            )
        )

    waiting = [i.created_at for i in items if i.status in OPEN_ITEM_STATUSES]
    return SessionDetail(
        session_id=session.id,
        table_id=table.id,
        table_number=table.number,
        status=_derive_status(session),
        waiter_id=session.waiter_id,
        waiter_name=waiter_name,
        party_size=session.party_size,
        opened_at=session.opened_at,
        bill_requested_at=session.bill_requested_at,
        waiting_since=min(waiting) if waiting else None,
        server_time=utcnow(),
        total_cents=sum(c.total_cents for c in check_reads),
        checks=check_reads,
    )


async def _detail_after_change(db: AsyncSession, table_id: uuid.UUID) -> SessionDetail:
    table, session, waiter_name = await _load_open(db, table_id)
    return await _build_detail(db, table, session, waiter_name)


# ---------- listagem (cartões das mesas) ----------

async def list_table_overview(
    db: AsyncSession, limit: int, offset: int, include_inactive: bool
) -> list[TableSummary]:
    stmt = select(RestaurantTable).order_by(RestaurantTable.number)
    if not include_inactive:
        stmt = stmt.where(RestaurantTable.is_active.is_(True))
    tables = list((await db.execute(stmt.limit(limit).offset(offset))).scalars())
    if not tables:
        return []

    rows = await db.execute(
        select(TableSession, User.name)
        .join(User, User.id == TableSession.waiter_id)
        .where(
            TableSession.table_id.in_([t.id for t in tables]),
            TableSession.closed_at.is_(None),
        )
    )
    open_sessions = {s.table_id: (s, name) for s, name in rows.all()}

    stats = {}
    if open_sessions:
        agg = await db.execute(
            select(
                TableCheck.session_id,
                func.count(func.distinct(TableCheck.id)).label('checks'),
                func.sum(
                    case(
                        (
                            OrderItem.status != OrderItemStatus.CANCELED,
                            OrderItem.unit_price_cents * OrderItem.quantity,
                        ),
                        else_=0,
                    )
                ).label('total'),
                func.count(OrderItem.id)
                .filter(OrderItem.status == OrderItemStatus.READY)
                .label('ready'),
                func.min(OrderItem.created_at)
                .filter(OrderItem.status.in_(OPEN_ITEM_STATUSES))
                .label('waiting_since'),
            )
            .select_from(TableCheck)
            .outerjoin(OrderItem, OrderItem.check_id == TableCheck.id)
            .where(TableCheck.session_id.in_([s.id for s, _ in open_sessions.values()]))
            .group_by(TableCheck.session_id)
        )
        stats = {row.session_id: row for row in agg.all()}

    summaries: list[TableSummary] = []
    for table in tables:
        found = open_sessions.get(table.id)
        if found is None:
            summaries.append(
                TableSummary(
                    id=table.id,
                    number=table.number,
                    seats=table.seats,
                    is_active=table.is_active,
                    status=TableStatus.FREE,
                )
            )
            continue
        session, waiter_name = found
        row = stats.get(session.id)
        summaries.append(
            TableSummary(
                id=table.id,
                number=table.number,
                seats=table.seats,
                is_active=table.is_active,
                status=_derive_status(session),
                waiter_id=session.waiter_id,
                waiter_name=waiter_name,
                party_size=session.party_size,
                opened_at=session.opened_at,
                checks_count=row.checks if row else 0,
                total_cents=int(row.total or 0) if row else 0,
                ready_count=row.ready if row else 0,
                waiting_since=row.waiting_since if row else None,
            )
        )
    return summaries


# ---------- ações ----------

async def open_table(
    db: AsyncSession, table_id: uuid.UUID, data: OpenTableRequest, actor: User, ip: str | None
) -> SessionDetail:
    table = await _get_table(db, table_id)
    if not table.is_active:
        raise ConflictError('Esta mesa está desativada')

    session = TableSession(table_id=table_id, waiter_id=actor.id, party_size=data.party_size)
    db.add(session)
    try:
        await db.flush()
    except IntegrityError:
        # Outro garçom abriu a mesma mesa um instante antes.
        await db.rollback()
        owner = await db.scalar(
            select(User.name)
            .join(TableSession, TableSession.waiter_id == User.id)
            .where(TableSession.table_id == table_id, TableSession.closed_at.is_(None))
        )
        raise ConflictError(
            f'Esta mesa já foi aberta por {owner}' if owner else 'Esta mesa já está aberta'
        ) from None

    for number in range(1, data.checks_count + 1):
        db.add(TableCheck(session_id=session.id, number=number))

    audit_service.record(
        db,
        'table_opened',
        actor_id=actor.id,
        target_id=table_id,
        ip=ip,
        detail={'party_size': data.party_size, 'checks': data.checks_count},
    )
    await db.commit()
    return await _detail_after_change(db, table_id)


async def get_session_detail(db: AsyncSession, table_id: uuid.UUID, actor: User) -> SessionDetail:
    table, session, waiter_name = await _load_open(db, table_id)
    ensure_can_view(session, actor)
    return await _build_detail(db, table, session, waiter_name)


async def add_check(
    db: AsyncSession, table_id: uuid.UUID, actor: User, ip: str | None
) -> SessionDetail:
    session = await _lock_open_session(db, table_id)
    ensure_can_act(session, actor)
    if session.bill_requested_at is not None:
        raise ConflictError('A conta já foi pedida')

    count = await db.scalar(
        select(func.count(TableCheck.id)).where(TableCheck.session_id == session.id)
    )
    if (count or 0) >= MAX_CHECKS:
        raise ConflictError(f'Limite de {MAX_CHECKS} contas por mesa')
    last = await db.scalar(
        select(func.max(TableCheck.number)).where(TableCheck.session_id == session.id)
    )
    db.add(TableCheck(session_id=session.id, number=(last or 0) + 1))

    audit_service.record(db, 'check_added', actor_id=actor.id, target_id=table_id, ip=ip)
    await db.commit()
    return await _detail_after_change(db, table_id)


async def request_bill(
    db: AsyncSession, table_id: uuid.UUID, actor: User, ip: str | None
) -> SessionDetail:
    session = await _lock_open_session(db, table_id)
    ensure_can_act(session, actor)
    if session.bill_requested_at is not None:
        raise ConflictError('A conta já foi pedida')
    active = await _count_items(db, session.id, OrderItem.status != OrderItemStatus.CANCELED)
    if active == 0:
        raise ConflictError(
            'A mesa não tem pedidos. Se abriu por engano, cancele o atendimento.'
        )

    session.bill_requested_at = utcnow()
    audit_service.record(db, 'bill_requested', actor_id=actor.id, target_id=table_id, ip=ip)
    await db.commit()
    return await _detail_after_change(db, table_id)


async def cancel_session(
    db: AsyncSession, table_id: uuid.UUID, actor: User, ip: str | None
) -> None:
    """Libera uma mesa aberta por engano. Só vale se não houver nenhum pedido ativo."""
    session = await _lock_open_session(db, table_id)
    ensure_can_act(session, actor)
    if await _count_items(db, session.id, OrderItem.status != OrderItemStatus.CANCELED):
        raise ConflictError('A mesa já tem pedidos. Só o fechamento das contas libera a mesa.')

    now = utcnow()
    await db.execute(
        update(TableCheck)
        .where(TableCheck.session_id == session.id, TableCheck.closed_at.is_(None))
        .values(closed_at=now, closed_by_id=actor.id, total_cents=0)
    )
    session.closed_at = now
    audit_service.record(
        db, 'table_session_canceled', actor_id=actor.id, target_id=table_id, ip=ip
    )
    await db.commit()


async def transfer_session(
    db: AsyncSession, table_id: uuid.UUID, waiter_id: uuid.UUID, actor: User, ip: str | None
) -> SessionDetail:
    session = await _lock_open_session(db, table_id)
    target = await db.get(User, waiter_id)
    if target is None or target.role != UserRole.WAITER or not target.is_active:
        raise DomainError('Garçom não encontrado ou inativo')

    previous = session.waiter_id
    session.waiter_id = target.id
    audit_service.record(
        db,
        'table_session_transferred',
        actor_id=actor.id,
        target_id=table_id,
        ip=ip,
        detail={'from': str(previous), 'to': str(target.id)},
    )
    await db.commit()
    return await _detail_after_change(db, table_id)


async def close_check(
    db: AsyncSession, table_id: uuid.UUID, check_id: uuid.UUID, actor: User, ip: str | None
) -> CloseCheckResult:
    session = await _lock_open_session(db, table_id)
    if session.bill_requested_at is None:
        raise ConflictError('A conta ainda não foi pedida pelo garçom')

    check = await db.get(TableCheck, check_id)
    if check is None or check.session_id != session.id:
        raise NotFoundError('Conta não encontrada')
    if check.closed_at is not None:
        raise ConflictError('Esta conta já foi fechada')

    undelivered = await db.scalar(
        select(func.count(OrderItem.id)).where(
            OrderItem.check_id == check.id, OrderItem.status.in_(OPEN_ITEM_STATUSES)
        )
    )
    if undelivered:
        raise ConflictError('Há itens desta conta que ainda não foram entregues')

    raw_total = await db.scalar(
        select(func.coalesce(func.sum(OrderItem.unit_price_cents * OrderItem.quantity), 0)).where(
            OrderItem.check_id == check.id, OrderItem.status != OrderItemStatus.CANCELED
        )
    )
    # Variável local `int`: o model guarda `int | None`, mas aqui o total já é definitivo.
    total_cents = int(raw_total or 0)

    now = utcnow()
    check.closed_at = now
    check.closed_by_id = actor.id
    check.total_cents = total_cents
    audit_service.record(
        db,
        'check_closed',
        actor_id=actor.id,
        target_id=check.id,
        ip=ip,
        detail={'total_cents': total_cents, 'table_id': str(table_id)},
    )

    await db.flush()
    remaining = await db.scalar(
        select(func.count(TableCheck.id)).where(
            TableCheck.session_id == session.id, TableCheck.closed_at.is_(None)
        )
    )
    session_closed = remaining == 0
    if session_closed:
        session.closed_at = now
        audit_service.record(
            db, 'table_session_closed', actor_id=actor.id, target_id=table_id, ip=ip
        )
    await db.commit()
    return CloseCheckResult(
        check_id=check.id, total_cents=total_cents, session_closed=session_closed
    )
