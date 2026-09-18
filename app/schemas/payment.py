from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field, field_validator

from app.schemas.common import CustomerInput


class InitiatePaymentRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=150)
    event_name: str = Field(min_length=1, max_length=250)
    service_code: str = Field(min_length=1, max_length=100)
    organizer_code: str | None = None
    reference_id: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    amount: int = Field(strict=True, gt=0, le=9223372036854775807)
    currency: Literal["IDR"] = "IDR"
    customer: CustomerInput
    expires_at: AwareDatetime | None = None
    return_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "event_name", mode="before")
    @classmethod
    def strip_event_fields(cls, value):
        return value.strip() if isinstance(value, str) else value


class CreateAttemptRequest(BaseModel):
    channel_code: str = Field(min_length=1, max_length=80)


class RefundRequest(BaseModel):
    amount: int | None = Field(default=None, strict=True, gt=0, le=9223372036854775807)
    reason: str = Field(min_length=1, max_length=500)
