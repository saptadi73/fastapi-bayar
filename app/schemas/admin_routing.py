from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class Reasoned(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value):
        return value.strip() if isinstance(value, str) else value


class MerchantAccountCreate(Reasoned):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    gateway: str = Field(min_length=1, max_length=30)
    credential_ref: str | None = Field(default=None, max_length=255)
    active: StrictBool = True


class OrganizerCreate(Reasoned):
    code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    active: StrictBool = True


class OrganizerUpdate(Reasoned):
    name: str = Field(min_length=1, max_length=200)
    active: StrictBool
    expected_version: int = Field(strict=True, ge=1)


class MerchantAccountUpdate(Reasoned):
    name: str = Field(min_length=1, max_length=200)
    credential_ref: str | None = Field(default=None, max_length=255)
    active: StrictBool
    expected_version: int = Field(strict=True, ge=1)


class PaymentChannelCreate(Reasoned):
    merchant_account_id: UUID
    gateway: str = Field(min_length=1, max_length=30)
    channel_code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=150)
    active: StrictBool = True
    min_amount: int | None = Field(default=None, ge=1)
    max_amount: int | None = Field(default=None, ge=1)
    currencies: list[str] = Field(default_factory=lambda: ["IDR"], min_length=1, max_length=10)


class PaymentChannelUpdate(Reasoned):
    name: str = Field(min_length=1, max_length=150)
    active: StrictBool
    min_amount: int | None = Field(default=None, ge=1)
    max_amount: int | None = Field(default=None, ge=1)
    currencies: list[str] = Field(min_length=1, max_length=10)
    expected_version: int = Field(strict=True, ge=1)


class RoutingRuleCreate(Reasoned):
    service_id: UUID | None = None
    event_id: str | None = Field(default=None, max_length=150)
    channel_code: str = Field(min_length=1, max_length=80)
    merchant_account_id: UUID
    priority: int = Field(default=100, ge=0, le=100000)
    active: StrictBool = True


class RoutingRuleUpdate(Reasoned):
    merchant_account_id: UUID
    priority: int = Field(ge=0, le=100000)
    active: StrictBool
    expected_version: int = Field(strict=True, ge=1)


class FeatureFlagUpsert(Reasoned):
    key: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    enabled: StrictBool
    config: dict[str, Any] = Field(default_factory=dict)
    expected_version: int | None = Field(default=None, strict=True, ge=1)
