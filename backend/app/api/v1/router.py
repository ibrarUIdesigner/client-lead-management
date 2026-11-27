from fastapi import APIRouter

from app.api.v1 import (
    apify,
    audits,
    auth,
    automation,
    design_guides,
    discovery,
    followups,
    gmail,
    health,
    insights,
    integrations,
    intelligence,
    jobs,
    leads,
    mockups,
    notifications,
    outreach,
    outreach_queue,
    pipeline,
    public,
    research,
    workspace,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(public.router)
api_router.include_router(notifications.router)
api_router.include_router(integrations.router)
api_router.include_router(jobs.router)
api_router.include_router(pipeline.router)
api_router.include_router(automation.router)
api_router.include_router(insights.router)
api_router.include_router(leads.router)
api_router.include_router(intelligence.router)
api_router.include_router(research.router)
api_router.include_router(audits.router)
api_router.include_router(outreach_queue.router)
api_router.include_router(outreach.router)
api_router.include_router(followups.router)
api_router.include_router(workspace.router)
api_router.include_router(design_guides.router)
api_router.include_router(mockups.router)
api_router.include_router(discovery.router)
api_router.include_router(gmail.router)
api_router.include_router(apify.router)
