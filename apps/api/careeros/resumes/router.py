"""Resumes: the master LaTeX template, tailored versions, cover letters, prep and outreach drafts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from careeros.api.deps import ContainerDep, CurrentUser, DbSession
from careeros.core.errors import AuthenticationError, NotFoundError
from careeros.jobs.models import Job
from careeros.profile.service import get_or_create_profile, load_snapshot
from careeros.resumes import coaching, service
from careeros.resumes.models import DocumentKind, DocumentStatus, ResumeDocument

router = APIRouter(prefix="/resumes", tags=["resumes"])
coaching_router = APIRouter(prefix="/jobs", tags=["resumes"])

MAX_TEX_BYTES = 200_000


class MasterIn(BaseModel):
    tex: Annotated[str, Field(min_length=50, max_length=MAX_TEX_BYTES)]
    filename: Annotated[str, Field(max_length=200)] = "resume.tex"


class MasterOut(BaseModel):
    filename: str
    revision: int
    tex: str
    pages: int | None
    engine: str | None
    compiled_at: datetime | None
    compile_error: str | None
    has_pdf: bool
    sections: list[dict[str, Any]]
    updated_at: datetime


class DocumentRequest(BaseModel):
    job_id: uuid.UUID | None = None
    kind: DocumentKind = DocumentKind.RESUME
    options: service.DocumentOptions = Field(default_factory=service.DocumentOptions)


class DocumentSummary(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None
    kind: DocumentKind
    status: DocumentStatus
    title: str
    pages: int | None
    coverage_before: float | None
    coverage_after: float | None
    starred: bool
    created_at: datetime


class DocumentDetail(DocumentSummary):
    changes: list[dict[str, Any]]
    keywords_before: dict[str, Any]
    keywords_after: dict[str, Any]
    body: str | None
    tex: str | None
    error: str | None
    options: dict[str, Any]


class DocumentPatch(BaseModel):
    starred: bool | None = None
    title: Annotated[str, Field(min_length=1, max_length=300)] | None = None


class DownloadLink(BaseModel):
    url: str
    expires_in: int


def _summary(doc: ResumeDocument) -> DocumentSummary:
    return DocumentSummary.model_validate(doc, from_attributes=True)


async def _owned(session: DbSession, user_id: uuid.UUID, document_id: uuid.UUID) -> ResumeDocument:
    document = await session.get(ResumeDocument, document_id)
    if document is None or document.user_id != user_id:
        raise NotFoundError("Document not found")
    return document


def _pdf_response(pdf: bytes, filename: str, inline: bool = True) -> Response:
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


# --- master -------------------------------------------------------------------------------------


@router.get("/master", response_model=MasterOut | None, summary="Your master LaTeX resume")
async def get_master(user: CurrentUser, session: DbSession) -> MasterOut | None:
    master = await service.get_master(session, user.id)
    if master is None:
        return None
    return MasterOut(
        filename=master.filename,
        revision=master.revision,
        tex=master.tex,
        pages=master.pages,
        engine=master.engine,
        compiled_at=master.compiled_at,
        compile_error=master.compile_error,
        has_pdf=master.pdf is not None,
        sections=service.section_summary(master.tex),
        updated_at=master.updated_at,
    )


@router.put(
    "/master", response_model=MasterOut, summary="Upload or replace your master LaTeX resume"
)
async def put_master(payload: MasterIn, user: CurrentUser, session: DbSession) -> MasterOut:
    await service.set_master(session, user, payload.tex, payload.filename)
    await session.commit()
    result = await get_master(user, session)
    if result is None:  # pragma: no cover - just written in this request
        raise NotFoundError("Master resume not found")
    return result


@router.get("/master/pdf", summary="The compiled master resume")
async def master_pdf(user: CurrentUser, session: DbSession) -> Response:
    master = await service.get_master(session, user.id)
    if master is None or master.pdf is None:
        raise NotFoundError("The master resume has not been compiled yet")
    profile = await get_or_create_profile(session, user)
    name = (profile.full_name or "Resume").replace(" ", "_")
    return _pdf_response(master.pdf, f"{name}_Resume.pdf")


# --- documents ------------------------------------------------------------------------------------


@router.get("", response_model=list[DocumentSummary], summary="Generated resumes and cover letters")
async def list_documents(
    user: CurrentUser,
    session: DbSession,
    job_id: uuid.UUID | None = None,
    kind: DocumentKind | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[DocumentSummary]:
    query = select(ResumeDocument).where(ResumeDocument.user_id == user.id)
    if job_id:
        query = query.where(ResumeDocument.job_id == job_id)
    if kind:
        query = query.where(ResumeDocument.kind == kind)
    rows = (
        (await session.execute(query.order_by(ResumeDocument.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    return [_summary(row) for row in rows]


@router.post(
    "",
    response_model=DocumentSummary,
    status_code=202,
    summary="Generate a tailored resume or cover letter",
)
async def create_document(
    payload: DocumentRequest, user: CurrentUser, session: DbSession
) -> DocumentSummary:
    document = await service.request_document(
        session, user, job_id=payload.job_id, kind=payload.kind, options=payload.options
    )
    await session.commit()
    return _summary(document)


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> DocumentDetail:
    return DocumentDetail.model_validate(
        await _owned(session, user.id, document_id), from_attributes=True
    )


@router.patch("/{document_id}", response_model=DocumentSummary)
async def patch_document(
    document_id: uuid.UUID, payload: DocumentPatch, user: CurrentUser, session: DbSession
) -> DocumentSummary:
    document = await _owned(session, user.id, document_id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(document, key, value)
    await session.commit()
    return _summary(document)


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: uuid.UUID, user: CurrentUser, session: DbSession) -> None:
    await session.delete(await _owned(session, user.id, document_id))
    await session.commit()


@router.get("/{document_id}/pdf", summary="Download the PDF")
async def document_pdf(document_id: uuid.UUID, user: CurrentUser, session: DbSession) -> Response:
    document = await _owned(session, user.id, document_id)
    if document.pdf is None:
        raise NotFoundError("This document has no PDF yet")
    profile = await get_or_create_profile(session, user)
    return _pdf_response(document.pdf, service.pdf_filename(document, profile.full_name))


@router.post(
    "/{document_id}/link",
    response_model=DownloadLink,
    summary="A short-lived link to open the PDF in a browser",
)
async def document_link(
    document_id: uuid.UUID,
    request: Request,
    user: CurrentUser,
    session: DbSession,
    container: ContainerDep,
) -> DownloadLink:
    document = await _owned(session, user.id, document_id)
    if document.pdf is None:
        raise NotFoundError("This document has no PDF yet")
    token = service.sign_download(container.settings.signing_secret.get_secret_value(), document.id)
    base = str(request.base_url).rstrip("/")
    if request.headers.get("x-forwarded-proto") == "https":
        base = base.replace("http://", "https://", 1)
    return DownloadLink(
        url=f"{base}/api/v1/resumes/{document.id}/download?token={token}", expires_in=900
    )


@router.get("/{document_id}/download", include_in_schema=False)
async def document_download(
    document_id: uuid.UUID,
    session: DbSession,
    container: ContainerDep,
    token: str = "",
    attachment: bool = False,
) -> Response:
    if not service.verify_download(
        container.settings.signing_secret.get_secret_value(), document_id, token
    ):
        raise AuthenticationError("This download link has expired")
    document = await session.get(ResumeDocument, document_id)
    if document is None or document.pdf is None:
        raise NotFoundError("Document not found")
    return _pdf_response(document.pdf, service.pdf_filename(document, None), inline=not attachment)


# --- coaching (per job) -----------------------------------------------------------------------------


async def _job_target(
    session: DbSession, user: CurrentUser, job_id: uuid.UUID
) -> tuple[Any, Any, Job]:
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    from careeros.intelligence.service import latest_analysis
    from careeros.resumes.tailor import JobTarget

    analysis = await latest_analysis(session, job.id)
    target = JobTarget.from_extraction(
        job.title, job.company, analysis.extraction if analysis else {}, job.description or ""
    )
    snapshot = await load_snapshot(session, await get_or_create_profile(session, user))
    return snapshot, target, job


@coaching_router.get("/{job_id}/prep", summary="Interview preparation from your verified profile")
async def job_prep(job_id: uuid.UUID, user: CurrentUser, session: DbSession) -> dict[str, Any]:
    snapshot, target, _ = await _job_target(session, user, job_id)
    return coaching.interview_prep(snapshot, target)


class Draft(BaseModel):
    kind: Literal["connection_note", "referral_request", "follow_up", "thank_you"]
    title: str
    subject: str
    body: str


@coaching_router.get(
    "/{job_id}/outreach",
    response_model=list[Draft],
    summary="Message drafts you can edit and send yourself",
)
async def job_outreach(job_id: uuid.UUID, user: CurrentUser, session: DbSession) -> list[Draft]:
    snapshot, target, job = await _job_target(session, user, job_id)
    return [
        Draft(**d)
        for d in coaching.outreach_drafts(
            snapshot, target, job.canonical_url or job.application_url
        )
    ]
