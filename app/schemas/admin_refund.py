from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminRefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_id: UUID
    amount: int | None = Field(default=None, strict=True, gt=0)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class RefundDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value
