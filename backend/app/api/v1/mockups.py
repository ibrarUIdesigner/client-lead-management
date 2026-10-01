from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.schemas.design_guides import MockupCreate, MockupCreated, MockupGuideRead
from app.services.mockups import MockupService

router = APIRouter(tags=["mockups"])


@router.post("/mockups", response_model=MockupCreated, status_code=201)
def create_mockup(data: MockupCreate, session: SessionDep) -> MockupCreated:
    return MockupService(session).create(data)


@router.get("/mockups/{mockup_id}/guide", response_model=MockupGuideRead)
def mockup_guide(mockup_id: UUID, session: SessionDep) -> MockupGuideRead:
    return MockupService(session).guide_snapshot(mockup_id)
