"""Run the task worker (and built-in scheduler):  python -m careeros.workers"""

from __future__ import annotations

import asyncio
import contextlib
import signal

from careeros.config import get_settings
from careeros.container import build_container
from careeros.core.logging import configure_logging
from careeros.tasks.runtime import Worker, load_handlers


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.use_json_logs)
    load_handlers()
    container = build_container(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # not available on Windows
            loop.add_signal_handler(sig, stop.set)
    try:
        await Worker(container).run_forever(stop)
    finally:
        await container.aclose()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
