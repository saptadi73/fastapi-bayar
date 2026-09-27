from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.db_echo, pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow, pool_timeout=settings.db_pool_timeout, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def check_database() -> dict[str, str]:
    """Check database connectivity without leaking credentials or SQL errors."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


async def verify_migration_head(expected_revision: str) -> None:
    """Fail closed when production starts against an older/different schema."""
    async with engine.connect() as connection:
        current_revision = await connection.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    if current_revision != expected_revision:
        raise RuntimeError("Database migration head tidak sesuai dengan aplikasi")
