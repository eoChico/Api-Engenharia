import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TableCheck(Base):
    """Uma conta dentro do atendimento (mesa com 2 contas = 2 registros)."""

    __tablename__ = 'table_checks'
    __table_args__ = (
        UniqueConstraint('session_id', 'number', name='uq_table_checks_session_number'),
        CheckConstraint('number >= 1', name='number_positive'),
        CheckConstraint('total_cents IS NULL OR total_cents >= 0', name='total_non_negative'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('table_sessions.id', ondelete='RESTRICT'), index=True
    )
    number: Mapped[int]
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey('users.id', ondelete='RESTRICT')
    )
    # Preenchido só ao fechar. Depois disso o valor fica congelado.
    total_cents: Mapped[int | None]
