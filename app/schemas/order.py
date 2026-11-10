import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.order_item import OrderItemStatus
from app.schemas.restaurant_table import TableStatus


class OpenTableRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    party_size: int = Field(ge=1, le=99)
    checks_count: int = Field(default=1, ge=1, le=10)


class AddItemRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    product_id: uuid.UUID
    quantity: int = Field(default=1, ge=1, le=99)
    notes: str | None = Field(default=None, max_length=200)

    @field_validator('notes')
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        return value or None


class ItemStatusUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: OrderItemStatus


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    waiter_id: uuid.UUID


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    quantity: int
    unit_price_cents: int
    notes: str | None
    status: OrderItemStatus
    created_at: datetime
    ready_at: datetime | None
    delivered_at: datetime | None

    @computed_field
    @property
    def line_total_cents(self) -> int:
        return self.unit_price_cents * self.quantity


class CheckRead(BaseModel):
    id: uuid.UUID
    number: int
    closed_at: datetime | None
    total_cents: int  # só itens não cancelados
    items: list[OrderItemRead]


class SessionDetail(BaseModel):
    session_id: uuid.UUID
    table_id: uuid.UUID
    table_number: int
    status: TableStatus
    waiter_id: uuid.UUID
    waiter_name: str
    party_size: int
    opened_at: datetime
    bill_requested_at: datetime | None
    waiting_since: datetime | None
    server_time: datetime  # o front calcula cronômetros pela diferença para o relógio do servidor
    total_cents: int
    checks: list[CheckRead]


class CloseCheckResult(BaseModel):
    check_id: uuid.UUID
    total_cents: int
    session_closed: bool  # true quando era a última conta: a mesa voltou a ficar livre


class KitchenItemRead(BaseModel):
    id: uuid.UUID
    table_number: int
    product_name: str
    quantity: int
    notes: str | None
    status: OrderItemStatus
    created_at: datetime
