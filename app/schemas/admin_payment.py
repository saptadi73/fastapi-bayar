from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentStatus


class PageMeta(BaseModel):
    limit: int
    offset: int
    has_more: bool
    total_count: int | None = None


T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PageMeta


class PaymentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_no: str
    client_id: UUID
    client_name: str | None
    service_id: UUID
    event_id: str | None
    event_name: str | None
    reference_id: str
    amount: int
    currency: str
    status: PaymentStatus
    created_at: datetime
    expires_at: datetime | None


class PaymentDataResponse(BaseModel):
    data: PaymentView


class PaymentHistoryView(BaseModel):
    id: UUID
    from_status: str | None
    to_status: str
    source: str
    occurred_at: datetime


class PaymentAttemptView(BaseModel):
    id: UUID
    attempt_no: int
    gateway: str
    gateway_order_id: str
    channel_code: str
    status: str


class ExportMeta(BaseModel):
    limit: int
    has_more: bool
    next_cursor: str | None
    snapshot_at: str
    format: str
    source: str


class PaymentExportResponse(BaseModel):
    data: list[PaymentView]
    meta: ExportMeta
