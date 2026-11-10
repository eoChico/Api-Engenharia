import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderItemStatus(StrEnum):
    PENDING = 'pending'        # aguardando a cozinha
    PREPARING = 'preparing'    # em preparo
    READY = 'ready'            # pronto, esperando o garçom entregar
    DELIVERED = 'delivered'    # entregue na mesa
    CANCELED = 'canceled'


class OrderItem(Base):
    __tablename__ = 'order_items'
    __table_args__ = (
        CheckConstraint('quantity BETWEEN 1 AND 99', name='quantity_range'),
        CheckConstraint('unit_price_cents >= 0', name='price_non_negative'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    check_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('table_checks.id', ondelete='RESTRICT'), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('products.id', ondelete='RESTRICT'), index=True
    )
    # Cópia do produto no momento do pedido: mudar o cardápio não altera contas antigas.
    product_name: Mapped[str] = mapped_column(String(120))
    unit_price_cents: Mapped[int]
    quantity: Mapped[int]
    notes: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[OrderItemStatus] = mapped_column(
        Enum(
            OrderItemStatus,
            name='order_item_status',
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        index=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('users.id', ondelete='RESTRICT')
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
