import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TableSession(Base):
    """Um atendimento: da abertura da mesa até o fechamento de todas as contas."""

    __tablename__ = 'table_sessions'
    __table_args__ = (
        CheckConstraint('party_size BETWEEN 1 AND 99', name='party_size_range'),
        # Só um atendimento aberto por mesa. Abrir duas vezes falha no banco.
        Index(
            'uq_table_sessions_one_open',
            'table_id',
            unique=True,
            postgresql_where=text('closed_at IS NULL'),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('restaurant_tables.id', ondelete='RESTRICT'), index=True
    )
    waiter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('users.id', ondelete='RESTRICT'), index=True
    )
    party_size: Mapped[int]
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    bill_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
