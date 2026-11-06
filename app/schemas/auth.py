from pydantic import BaseModel, Field, model_validator


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos de vida do access token


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    @model_validator(mode="after")
    def different(self):
        if self.current_password == self.new_password:
            raise ValueError("A nova senha deve ser diferente da atual")
        return self
