from fastapi import APIRouter

from app.api.v1 import (
    apify,
    audits,
    auth,
    design_guides,
    discovery,
    followups,
    gmail,
    health,
    integrations,
    intelligence,
    jobs,
    leads,
    mockups,
    notifications,
    outreach,
    research,
    workspace,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(notifications.router)
api_router.include_router(integrations.router)
api_router.include_router(jobs.router)
api_router.include_router(leads.router)
api_router.include_router(intelligence.router)
api_router.include_router(research.router)
api_router.include_router(audits.router)
api_router.include_router(outreach.router)
api_router.include_router(followups.router)
api_router.include_router(workspace.router)
api_router.include_router(design_guides.router)
api_router.include_router(mockups.router)
api_router.include_router(discovery.router)
api_router.include_router(gmail.router)
api_router.include_router(apify.router)
