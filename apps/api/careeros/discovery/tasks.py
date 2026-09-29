from __future__ import annotations

from typing import Any

from careeros.discovery.service import run_source
from careeros.tasks.models import TaskType
from careeros.tasks.runtime import TaskContext, task_handler


@task_handler(TaskType.RUN_DISCOVERY)
async def handle_run_discovery(ctx: TaskContext) -> dict[str, Any]:
    stats = await run_source(
        ctx.session,
        ctx.uuid("source_id"),
        settings=ctx.container.settings,
        fetcher=ctx.container.fetcher,
        embedder=ctx.container.llm.embedder,
    )
    return {"stats": stats}
