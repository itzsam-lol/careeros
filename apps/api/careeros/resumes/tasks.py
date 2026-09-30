"""GENERATE_RESUME: compile the master template or build a tailored document."""

from __future__ import annotations

from typing import Any

from careeros.resumes.models import ResumeMaster
from careeros.resumes.service import build_document, compile_master
from careeros.tasks.models import TaskType
from careeros.tasks.runtime import TaskContext, task_handler


@task_handler(TaskType.GENERATE_RESUME)
async def handle_generate_resume(ctx: TaskContext) -> dict[str, Any]:
    if "master_id" in ctx.payload:
        master = await ctx.session.get(ResumeMaster, ctx.uuid("master_id"))
        if master is None:
            return {"skipped": "master deleted"}
        await compile_master(ctx.session, master, ctx.container)
        await ctx.session.commit()
        return {"pages": master.pages, "error": bool(master.compile_error)}
    document = await build_document(ctx.session, ctx.uuid("document_id"), ctx.container)
    await ctx.session.commit()
    return {
        "status": document.status.value,
        "pages": document.pages,
        "coverage": document.coverage_after,
    }
