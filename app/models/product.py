import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductCategory(StrEnum):
    FOOD = 'food'          # prato
    DRINK = 'drink'        # bebida
    DESSERT = 'dessert'    # sobremesa
    OTHER = 'other'        # outros


class Product(Base):
    __tablename__ = 'products'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[ProductCategory] = mapped_column(
        Enum(
            ProductCategory,
            name='product_category',
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        index=True,
    )
    price_cents: Mapped[int]
    needs_kitchen: Mapped[bool] = mapped_column(Boolean)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint('price_cents >= 0', name='price_non_negative'),
        # Nome único sem diferenciar maiúsculas de minúsculas.
        Index('uq_products_name_lower', func.lower(name), unique=True),
    )
