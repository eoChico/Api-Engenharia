import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RestaurantTable(Base):
    __tablename__ = 'restaurant_tables'
    __table_args__ = (
        CheckConstraint('number > 0', name='number_positive'),
        CheckConstraint('seats > 0 AND seats <= 50', name='seats_range'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    number: Mapped[int] = mapped_column(unique=True)
    seats: Mapped[int]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
