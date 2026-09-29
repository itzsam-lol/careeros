from __future__ import annotations

from typing import Any

from careeros.intelligence.service import analyze_job
from careeros.tasks.models import TaskType
from careeros.tasks.runtime import TaskContext, task_handler


@task_handler(TaskType.ANALYZE_JOB)
async def handle_analyze_job(ctx: TaskContext) -> dict[str, Any]:
    analysis = await analyze_job(ctx.session, ctx.uuid("job_id"), ctx.container.llm)
    return {"analysis_id": str(analysis.id), "extractor": analysis.extractor}
