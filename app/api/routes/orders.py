import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession, FloorUser, KitchenUser, Meta, OrderActor
from app.schemas.order import AddItemRequest, ItemStatusUpdate, KitchenItemRead, OrderItemRead
from app.services import order_service

router = APIRouter(tags=['orders'])


@router.post(
    '/checks/{check_id}/items', response_model=OrderItemRead, status_code=status.HTTP_201_CREATED
)
async def add_item(
    check_id: uuid.UUID, data: AddItemRequest, actor: FloorUser, db: DbSession, meta: Meta
):
    return await order_service.add_item(db, check_id, data, actor, meta.ip)


@router.patch('/order-items/{item_id}/status', response_model=OrderItemRead)
async def change_item_status(
    item_id: uuid.UUID, data: ItemStatusUpdate, actor: OrderActor, db: DbSession, meta: Meta
):
    return await order_service.change_item_status(db, item_id, data.status, actor, meta.ip)


@router.get('/kitchen/queue', response_model=list[KitchenItemRead])
async def kitchen_queue(actor: KitchenUser, db: DbSession, limit: int = Query(100, ge=1, le=200)):
    return await order_service.kitchen_queue(db, limit)
