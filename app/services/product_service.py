import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductCategory
from app.models.user import User
from app.schemas.product import ProductCreate, ProductUpdate
from app.services import audit_service


class ProductNameAlreadyExistsError(Exception):
    pass


def _plain(value):
    return getattr(value, 'value', value)  # enum -> texto, para o JSON da auditoria


async def list_products(
    db: AsyncSession,
    limit: int,
    offset: int,
    category: ProductCategory | None,
    include_inactive: bool,
) -> list[Product]:
    stmt = select(Product).order_by(Product.category, Product.name)
    if category is not None:
        stmt = stmt.where(Product.category == category)
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    result = await db.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars())


async def get_product(
    db: AsyncSession, product_id: uuid.UUID, include_inactive: bool
) -> Product | None:
    product = await db.get(Product, product_id)
    if product is None or (not product.is_active and not include_inactive):
        return None
    return product


async def create_product(
    db: AsyncSession, data: ProductCreate, actor: User, ip: str | None
) -> Product:
    needs_kitchen = data.needs_kitchen
    if needs_kitchen is None:
        needs_kitchen = data.category in (ProductCategory.FOOD, ProductCategory.DESSERT)

    product = Product(
        name=data.name,
        category=data.category,
        price_cents=data.price_cents,
        needs_kitchen=needs_kitchen,
    )
    db.add(product)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ProductNameAlreadyExistsError from None

    audit_service.record(
        db,
        'product_created',
        actor_id=actor.id,
        target_id=product.id,
        ip=ip,
        detail={'name': product.name, 'price_cents': product.price_cents},
    )
    await db.commit()
    await db.refresh(product)
    return product


async def update_product(
    db: AsyncSession, product: Product, data: ProductUpdate, actor: User, ip: str | None
) -> Product:
    changes = {k: getattr(data, k) for k in data.model_fields_set}
    before = {k: _plain(getattr(product, k)) for k in changes}

    for key, value in changes.items():
        setattr(product, key, value)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ProductNameAlreadyExistsError from None

    audit_service.record(
        db,
        'product_updated',
        actor_id=actor.id,
        target_id=product.id,
        ip=ip,
        detail={'before': before, 'after': {k: _plain(v) for k, v in changes.items()}},
    )
    await db.commit()
    await db.refresh(product)
    return product
