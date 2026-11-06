import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import UserRole


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: UserRole


class UserUpdateAdmin(BaseModel):
    """Só o gerente usa. Qualquer campo fora desta lista é rejeitado (anti mass assignment)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def at_least_one_valid_field(self):
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"'{field}' não pode ser nulo")
        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
