from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = Field(max_length=100)
    expected_version: int = Field(strict=True, ge=1)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("display_name", "reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class ClientAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: UUID
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value
