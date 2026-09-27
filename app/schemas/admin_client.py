from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClientConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    active: bool
    scopes: list[Literal["payments:read", "payments:write", "payments:refund"]] = Field(min_length=1, max_length=3)
    allowed_return_urls: list[str] = Field(max_length=20)
    allowed_callback_urls: list[str] = Field(max_length=20)
    callback_url: str | None
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("name", "reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class CreateClient(ClientConfiguration):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    service_code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class UpdateClient(ClientConfiguration):
    expected_version: int = Field(strict=True, ge=1)


class RotateClientSecret(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(strict=True, ge=1)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class RevokeCheckouts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value
