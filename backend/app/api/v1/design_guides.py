from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import Response

from app.api.deps import SessionDep
from app.schemas.design_guides import (
    DesignGuideList,
    DesignGuideRead,
    DesignGuideTemplate,
    DesignGuideWrite,
)
from app.services.design_guides import DesignGuideService
from app.services.design_markdown import normalize_guide_tags

router = APIRouter(prefix="/design-guides", tags=["design-guides"])


@router.get("", response_model=DesignGuideList)
def list_guides(
    session: SessionDep,
    request: Request,
    q: str | None = Query(default=None, max_length=120),
    tag: str | None = Query(default=None, max_length=32),
) -> DesignGuideList:
    return DesignGuideService(session, request.app.state.settings).list_guides(query=q, tag=tag)


@router.get("/template", response_model=DesignGuideTemplate)
def guide_template(session: SessionDep, request: Request) -> DesignGuideTemplate:
    return DesignGuideService(session, request.app.state.settings).template()


@router.get("/{guide_id}", response_model=DesignGuideRead)
def get_guide(guide_id: UUID, session: SessionDep, request: Request) -> DesignGuideRead:
    return DesignGuideService(session, request.app.state.settings).get_guide(guide_id)


@router.post("", response_model=DesignGuideRead, status_code=201)
def create_guide(
    data: DesignGuideWrite,
    session: SessionDep,
    request: Request,
) -> DesignGuideRead:
    return DesignGuideService(session, request.app.state.settings).create_guide(data)


@router.post("/upload", response_model=DesignGuideRead, status_code=201)
async def upload_guide(
    session: SessionDep,
    request: Request,
    name: str = Form(min_length=1, max_length=120),
    description: str | None = Form(default=None),
    tags: str = Form(default=""),
    file: UploadFile = File(),  # noqa: B008
) -> DesignGuideRead:
    payload = await file.read()
    tag_list = normalize_guide_tags([part for part in tags.split(",")])
    return DesignGuideService(session, request.app.state.settings).create_from_upload(
        name=name.strip(),
        description=description.strip() if description else None,
        tags=tag_list,
        filename=file.filename,
        payload=payload,
    )


@router.put("/{guide_id}", response_model=DesignGuideRead)
def update_guide(
    guide_id: UUID,
    data: DesignGuideWrite,
    session: SessionDep,
    request: Request,
) -> DesignGuideRead:
    return DesignGuideService(session, request.app.state.settings).update_guide(guide_id, data)


@router.delete("/{guide_id}", status_code=204)
def delete_guide(guide_id: UUID, session: SessionDep, request: Request) -> Response:
    DesignGuideService(session, request.app.state.settings).delete_guide(guide_id)
    return Response(status_code=204)


@router.get("/{guide_id}/download")
def download_guide(guide_id: UUID, session: SessionDep, request: Request) -> Response:
    guide = DesignGuideService(session, request.app.state.settings).get_guide(guide_id)
    filename = "".join(char if char.isalnum() or char in "-_" else "-" for char in guide.name)
    filename = filename.strip("-") or "design-guide"
    return Response(
        content=guide.content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
    )
