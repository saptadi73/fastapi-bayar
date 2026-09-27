"""Portal-owned event and payer identities; distinct from admin login users."""
import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PortalEvent(Base):
    __tablename__ = "portal_events"
    __table_args__ = (
        UniqueConstraint("client_id", "event_id", name="uq_portal_event_identity"),
        UniqueConstraint("client_id", "id", name="uq_portal_event_owner"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))
    event_id: Mapped[str] = mapped_column(String(150))
    name: Mapped[str] = mapped_column(String(250))


class PortalUser(Base):
    __tablename__ = "portal_users"
    __table_args__ = (
        UniqueConstraint("client_id", "email", name="uq_portal_user_identity"),
        UniqueConstraint("client_id", "id", name="uq_portal_user_owner"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
