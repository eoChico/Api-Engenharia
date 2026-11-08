import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession, ManagerUser, Meta
from app.models.product import ProductCategory
from app.models.user import UserRole
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services import product_service

router = APIRouter(prefix='/products', tags=['products'])

_NAME_CONFLICT = 'Já existe um produto com esse nome'


@router.post('', response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductCreate, actor: ManagerUser, db: DbSession, meta: Meta):
    try:
        return await product_service.create_product(db, data, actor, meta.ip)
    except product_service.ProductNameAlreadyExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT, _NAME_CONFLICT) from None


@router.get('', response_model=list[ProductRead])
async def list_products(
    actor: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: ProductCategory | None = None,
    include_inactive: bool = False,
):
    if include_inactive and actor.role != UserRole.MANAGER:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, 'Apenas o gerente vê produtos inativos'
        )
    return await product_service.list_products(db, limit, offset, category, include_inactive)


@router.get('/{product_id}', response_model=ProductRead)
async def get_product(product_id: uuid.UUID, actor: CurrentUser, db: DbSession):
    product = await product_service.get_product(
        db, product_id, include_inactive=actor.role == UserRole.MANAGER
    )
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Produto não encontrado')
    return product


@router.patch('/{product_id}', response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID, data: ProductUpdate, actor: ManagerUser, db: DbSession, meta: Meta
):
    product = await product_service.get_product(db, product_id, include_inactive=True)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Produto não encontrado')
    try:
        return await product_service.update_product(db, product, data, actor, meta.ip)
    except product_service.ProductNameAlreadyExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT, _NAME_CONFLICT) from None
