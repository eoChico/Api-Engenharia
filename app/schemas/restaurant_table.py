import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime
from enum import StrEnum

class TableCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    number: int = Field(ge=1, le=9999)
    seats: int = Field(ge=1, le=50)


class TableUpdate(BaseModel):
    """Só o gerente usa. Envie apenas o que quer mudar."""

    model_config = ConfigDict(extra='forbid')

    number: int | None = Field(default=None, ge=1, le=9999)
    seats: int | None = Field(default=None, ge=1, le=50)
    is_active: bool | None = None

    @model_validator(mode='after')
    def at_least_one_valid_field(self):
        if not self.model_fields_set:
            raise ValueError('Informe ao menos um campo')
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' não pode ser nulo")
        return self


class TableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: int
    seats: int
    is_active: bool

class TableStatus(StrEnum):
    FREE = 'free'
    OCCUPIED = 'occupied'
    BILL_REQUESTED = 'bill_requested'


class TableSummary(TableRead):
    """Cartão da mesa na listagem. É um superset do TableRead."""

    status: TableStatus
    waiter_id: uuid.UUID | None = None
    waiter_name: str | None = None
    party_size: int | None = None
    opened_at: datetime | None = None
    checks_count: int = 0
    total_cents: int = 0
    ready_count: int = 0                    # itens prontos ainda não entregues
    waiting_since: datetime | None = None   # item mais antigo ainda não entregue
