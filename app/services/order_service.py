import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order_item import OrderItem, OrderItemStatus
from app.models.product import Product
from app.models.restaurant_table import RestaurantTable
from app.models.table_check import TableCheck
from app.models.table_session import TableSession
from app.models.user import User
from app.schemas.order import AddItemRequest, KitchenItemRead
from app.services import audit_service
from app.services.auth_service import utcnow
from app.services.errors import ConflictError, NotFoundError
from app.services.item_rules import authorize_transition
from app.services.session_service import ensure_can_act


async def add_item(
    db: AsyncSession, check_id: uuid.UUID, data: AddItemRequest, actor: User, ip: str | None
) -> OrderItem:
    check = await db.get(TableCheck, check_id)
    if check is None:
        raise NotFoundError('Conta não encontrada')

    # Trava o atendimento: não deixa lançar item enquanto o caixa fecha a conta.
    session = (
        await db.execute(
            select(TableSession).where(TableSession.id == check.session_id).with_for_update()
        )
    ).scalar_one()
    await db.refresh(check)

    if session.closed_at is not None or check.closed_at is not None:
        raise ConflictError('Esta conta já foi fechada')
    ensure_can_act(session, actor)
    if session.bill_requested_at is not None:
        raise ConflictError('A conta já foi pedida: não é possível lançar novos itens')

    product = await db.get(Product, data.product_id)
    if product is None or not product.is_active:
        raise NotFoundError('Produto não encontrado')

    now = utcnow()
    needs_kitchen = product.needs_kitchen
    item = OrderItem(
        check_id=check.id,
        product_id=product.id,
        product_name=product.name,
        unit_price_cents=product.price_cents,
        quantity=data.quantity,
        notes=data.notes,
        status=OrderItemStatus.PENDING if needs_kitchen else OrderItemStatus.READY,
        ready_at=None if needs_kitchen else now,
        created_by_id=actor.id,
    )
    db.add(item)
    await db.flush()

    audit_service.record(
        db,
        'order_item_added',
        actor_id=actor.id,
        target_id=item.id,
        ip=ip,
        detail={'product': product.name, 'quantity': data.quantity},
    )
    await db.commit()
    await db.refresh(item)
    return item


async def change_item_status(
    db: AsyncSession, item_id: uuid.UUID, new_status: OrderItemStatus, actor: User, ip: str | None
) -> OrderItem:
    # Ordem de travas: item e depois atendimento (as demais operações travam só o atendimento).
    item = (
        await db.execute(select(OrderItem).where(OrderItem.id == item_id).with_for_update())
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError('Item não encontrado')

    check = await db.get(TableCheck, item.check_id)
    assert check is not None
    session = (
        await db.execute(
            select(TableSession).where(TableSession.id == check.session_id).with_for_update()
        )
    ).scalar_one()
    await db.refresh(check)

    if check.closed_at is not None:
        raise ConflictError('Esta conta já foi fechada')

    old_status = item.status
    authorize_transition(old_status, new_status, actor.role, session.waiter_id == actor.id)

    now = utcnow()
    item.status = new_status
    if new_status == OrderItemStatus.READY:
        item.ready_at = now
    elif new_status == OrderItemStatus.DELIVERED:
        item.delivered_at = now
    elif new_status == OrderItemStatus.CANCELED:
        item.canceled_at = now

    audit_service.record(
        db,
        'order_item_canceled' if new_status == OrderItemStatus.CANCELED else 'order_item_status_changed',
        actor_id=actor.id,
        target_id=item.id,
        ip=ip,
        detail={'from': old_status.value, 'to': new_status.value, 'product': item.product_name},
    )
    await db.commit()
    await db.refresh(item)
    return item


async def kitchen_queue(db: AsyncSession, limit: int) -> list[KitchenItemRead]:
    # Item 'pending' ou 'preparing' só existe se o produto passa pela cozinha.
    rows = await db.execute(
        select(OrderItem, RestaurantTable.number)
        .join(TableCheck, TableCheck.id == OrderItem.check_id)
        .join(TableSession, TableSession.id == TableCheck.session_id)
        .join(RestaurantTable, RestaurantTable.id == TableSession.table_id)
        .where(OrderItem.status.in_((OrderItemStatus.PENDING, OrderItemStatus.PREPARING)))
        .order_by(OrderItem.created_at)
        .limit(limit)
    )
    return [
        KitchenItemRead(
            id=item.id,
            table_number=number,
            product_name=item.product_name,
            quantity=item.quantity,
            notes=item.notes,
            status=item.status,
            created_at=item.created_at,
        )
        for item, number in rows.all()
    ]
