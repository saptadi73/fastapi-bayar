from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


class CustomerInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr = Field(max_length=320)
    phone: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_empty_email(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email")
    @classmethod
    def normalize_identity_email(cls, value):
        # Explicit portal identity policy: case-insensitive, no dot/plus alias folding.
        return str(value).lower()

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None
