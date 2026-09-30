from fastapi import APIRouter

from app.api.v1 import audits, contacts, health, leads

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(leads.router)
api_router.include_router(contacts.router)
api_router.include_router(audits.router)
