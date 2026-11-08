import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.product import ProductCategory

MAX_PRICE_CENTS = 10_000_000  # R$ 100.000,00: trava erro de digitação


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=120)
    category: ProductCategory
    price_cents: int = Field(ge=0, le=MAX_PRICE_CENTS)
    # Se omitido: true para prato e sobremesa, false para bebida e outros.
    needs_kitchen: bool | None = None


class ProductUpdate(BaseModel):
    """Só o gerente usa. Envie apenas o que quer mudar."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=120)
    category: ProductCategory | None = None
    price_cents: int | None = Field(default=None, ge=0, le=MAX_PRICE_CENTS)
    needs_kitchen: bool | None = None
    is_active: bool | None = None

    @model_validator(mode='after')
    def at_least_one_valid_field(self):
        if not self.model_fields_set:
            raise ValueError('Informe ao menos um campo')
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' não pode ser nulo")
        return self


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: ProductCategory
    price_cents: int
    needs_kitchen: bool
    is_active: bool
