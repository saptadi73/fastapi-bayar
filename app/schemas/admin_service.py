from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class ServiceFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=250)
    active: StrictBool
    reason: str = Field(min_length=1, max_length=500)
    organizer_id: UUID | None = None

    @field_validator("name", "reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class CreateService(ServiceFields):
    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class UpdateService(ServiceFields):
    expected_version: int = Field(strict=True, ge=1)
