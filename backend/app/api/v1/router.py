from fastapi import APIRouter

from app.api.v1 import audits, contacts, discovery, followups, health, leads, outreach, workspace

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(leads.router)
api_router.include_router(contacts.router)
api_router.include_router(audits.router)
api_router.include_router(outreach.router)
api_router.include_router(followups.router)
api_router.include_router(workspace.router)
api_router.include_router(discovery.router)
