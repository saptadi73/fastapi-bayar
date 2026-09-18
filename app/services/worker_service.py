"""Independent periodic loops. No worker is started by the API lifespan."""
import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.callback_service import deliver_pending_callbacks
from app.services.maintenance_service import cleanup_admin_retention, cleanup_expired_checkouts, cleanup_expired_nonces
from app.services.reconciliation_worker_service import reconciliation_tick
from app.services.refund_worker_service import refund_tick

logger = logging.getLogger("payment.worker")


async def callback_tick() -> dict[str, int]:
    # Commit one event at a time: a later crash cannot roll back an earlier success.
    # Multiple processes share work through PostgreSQL SKIP LOCKED.
    totals = {"succeeded": 0, "retry": 0, "dead_letter": 0}
    for _ in range(get_settings().worker_callback_batch_size):
        async with SessionLocal() as db:
            result = await deliver_pending_callbacks(db, limit=1)
        for key, value in result.items():
            totals[key] += value
        if not any(result.values()):
            break
    return totals


async def cleanup_tick() -> dict[str, int]:
    async with SessionLocal() as db:
        settings = get_settings()
        result = await cleanup_expired_checkouts(db, settings.worker_cleanup_batch_size)
        result.update(await cleanup_expired_nonces(db, settings.worker_cleanup_batch_size))
        result.update(await cleanup_admin_retention(db, settings.worker_cleanup_batch_size,
                                                    settings.admin_idle_ttl_seconds,
                                                    settings.admin_login_window_seconds))
        return result


async def periodic_job(name: str, operation: Callable[[], Awaitable[dict]],
                       interval: float, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            result = await operation()
            logger.info("job=%s outcome=ok counts=%s", name, result)
        except Exception as exc:
            # Never log exception text: database/HTTP errors can contain credentials/URLs.
            logger.error("job=%s outcome=error error_type=%s", name, type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def run_worker(stop: asyncio.Event, jobs: str = "all", once: bool = False) -> None:
    if jobs not in {"all", "callbacks", "cleanup", "reconciliation", "refunds"}:
        raise ValueError("Unknown worker jobs")
    settings = get_settings()
    selected = []
    if jobs in {"all", "callbacks"}:
        selected.append(("callbacks", callback_tick, settings.worker_callback_interval_seconds))
    if jobs in {"all", "cleanup"}:
        selected.append(("cleanup", cleanup_tick, settings.worker_cleanup_interval_seconds))
    if jobs in {"all", "reconciliation"}:
        selected.append(("reconciliation", reconciliation_tick, settings.worker_reconciliation_interval_seconds))
    if jobs in {"all", "refunds"}:
        selected.append(("refunds", refund_tick, settings.worker_refund_interval_seconds))
    if once:
        # Fail the command on error so a task scheduler can alert/retry.
        for name, operation, _ in selected:
            logger.info("job=%s outcome=ok counts=%s", name, await operation())
        return
    await asyncio.gather(*(periodic_job(name, op, interval, stop) for name, op, interval in selected))
