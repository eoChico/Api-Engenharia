import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
