"""Run callback and checkout-retention jobs as a separate process."""
import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine
from app.services.worker_service import run_worker


async def main(args):
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    try:
        await run_worker(stop, jobs=args.jobs, once=args.once)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", choices=["all", "callbacks", "cleanup", "reconciliation", "refunds"], default="all")
    parser.add_argument("--once", action="store_true", help="One batch per selected job; fail on error")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        asyncio.run(main(parser.parse_args()))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logging.getLogger("payment.worker").error("worker_exit error_type=%s", type(exc).__name__)
        sys.exit(1)
