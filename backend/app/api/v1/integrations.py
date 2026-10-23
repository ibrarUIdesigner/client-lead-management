from typing import Literal
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.outreach_ai import provider_ready, resolve_email_provider

router = APIRouter(prefix="/integrations", tags=["integrations"])


class IntegrationItem(BaseModel):
    id: str
    name: str
    category: str
    description: str
    status: Literal["active", "ready", "not_configured", "public"]
    is_configured: bool
    env_var: str
    details: str
    website: str | None = None


class IntegrationsResponse(BaseModel):
    integrations: list[IntegrationItem]
    total_count: int
    configured_count: int


@router.get("", response_model=IntegrationsResponse)
def get_integrations(request: Request) -> IntegrationsResponse:
    settings = request.app.state.settings
    active_draft_provider = resolve_email_provider(settings)

    gemini_key = bool(settings.gemini_api_key.strip())
    groq_key = bool(settings.groq_api_key.strip())
    tavily_key = bool(settings.tavily_api_key.strip())
    exa_key = bool(settings.exa_api_key.strip())
    apollo_key = bool(settings.apollo_api_key.strip())
    serpapi_key = bool(settings.serpapi_api_key.strip())
    scrapingbee_key = bool(settings.scrapingbee_api_key.strip())
    pagespeed_key = bool(settings.google_pagespeed_api_key.strip())
    gmail_key = bool(settings.google_oauth_client_id.strip() and settings.google_oauth_client_secret.strip())
    apify_key = bool(settings.apify_token.strip())
    google_places_key = bool(settings.google_places_api_key.strip())
    yelp_key = bool(settings.yelp_api_key.strip())

    items: list[IntegrationItem] = [
        IntegrationItem(
            id="tavily",
            name="Tavily Search API",
            category="Lead Research",
            description="Autonomous web search engine designed for LLMs to research company offerings, reputation, reviews, and market presence.",
            status="ready" if tavily_key else "not_configured",
            is_configured=tavily_key,
            env_var="TAVILY_API_KEY",
            details="API key configured · Advanced web research enabled" if tavily_key else "Missing TAVILY_API_KEY",
            website="https://tavily.com",
        ),
        IntegrationItem(
            id="exa",
            name="Exa AI Search",
            category="Lead Research",
            description="Neural search engine designed to discover company news, semantic context, highlights, and industry intelligence.",
            status="ready" if exa_key else "not_configured",
            is_configured=exa_key,
            env_var="EXA_API_KEY",
            details="API key configured · Neural web intelligence enabled" if exa_key else "Missing EXA_API_KEY",
            website="https://exa.ai",
        ),
        IntegrationItem(
            id="gemini",
            name="Google Gemini AI",
            category="AI Intelligence",
            description="Generates personalized cold outreach email drafts based on business overview and operational pain points.",
            status="active" if active_draft_provider == "gemini" else ("ready" if gemini_key else "not_configured"),
            is_configured=gemini_key,
            env_var="GEMINI_API_KEY",
            details=f"Model: {settings.gemini_model} · {'Primary provider' if active_draft_provider == 'gemini' else 'Configured'}" if gemini_key else "Missing GEMINI_API_KEY",
            website="https://ai.google.dev",
        ),
        IntegrationItem(
            id="groq",
            name="Groq AI",
            category="AI Intelligence",
            description="Ultra-fast Llama/OpenAI-compatible LLM inference for high-throughput draft generation and text extraction.",
            status="active" if active_draft_provider == "groq" else ("ready" if groq_key else "not_configured"),
            is_configured=groq_key,
            env_var="GROQ_API_KEY",
            details=f"Model: {settings.groq_model} · {'Primary provider' if active_draft_provider == 'groq' else 'Standby fallback'}" if groq_key else "Missing GROQ_API_KEY",
            website="https://groq.com",
        ),
        IntegrationItem(
            id="apollo",
            name="Apollo.io",
            category="Lead Discovery",
            description="B2B search engine for finding worldwide companies, organizational domains, phone numbers, and industry details.",
            status="ready" if apollo_key else "not_configured",
            is_configured=apollo_key,
            env_var="APOLLO_API_KEY",
            details="API key configured · Global B2B organizations enabled" if apollo_key else "Missing APOLLO_API_KEY",
            website="https://apollo.io",
        ),
        IntegrationItem(
            id="serpapi",
            name="SerpApi (Google Maps)",
            category="Lead Discovery",
            description="Real-time Google Maps search engine API to discover local businesses worldwide with phone, address, and ratings.",
            status="ready" if serpapi_key else "not_configured",
            is_configured=serpapi_key,
            env_var="SERPAPI_API_KEY",
            details="API key configured · Live Google Maps worldwide enabled" if serpapi_key else "Missing SERPAPI_API_KEY",
            website="https://serpapi.com",
        ),
        IntegrationItem(
            id="scrapingbee",
            name="ScrapingBee",
            category="Lead Discovery & Web Crawling",
            description="Google search snippet scraper for direct contact emails and rotating proxy engine to bypass 403 blocks on business sites.",
            status="ready" if scrapingbee_key else "not_configured",
            is_configured=scrapingbee_key,
            env_var="SCRAPINGBEE_API_KEY",
            details="API key configured · Google SERP search & proxy scraping enabled" if scrapingbee_key else "Missing SCRAPINGBEE_API_KEY",
            website="https://scrapingbee.com",
        ),
        IntegrationItem(
            id="pagespeed",
            name="Google PageSpeed Insights",
            category="Website Audit",
            description="Analyzes website speed, Core Web Vitals (FCP, LCP), mobile responsiveness, and render-blocking bottlenecks.",
            status="ready" if pagespeed_key else "not_configured",
            is_configured=pagespeed_key,
            env_var="GOOGLE_PAGESPEED_API_KEY",
            details="API key configured · Mobile & Desktop Lighthouse auditing enabled" if pagespeed_key else "Missing GOOGLE_PAGESPEED_API_KEY",
            website="https://developers.google.com/speed/pagespeed/insights",
        ),
        IntegrationItem(
            id="gmail",
            name="Gmail (Google OAuth 2.0)",
            category="Email Outreach",
            description="Authenticates team Gmail mailboxes to send automated cold outreach and continuously sync inbox replies.",
            status="ready" if gmail_key else "not_configured",
            is_configured=gmail_key,
            env_var="GOOGLE_OAUTH_CLIENT_ID / SECRET",
            details="OAuth client ID & secret configured" if gmail_key else "Missing GOOGLE_OAUTH_CLIENT_ID",
            website="https://console.cloud.google.com",
        ),
        IntegrationItem(
            id="apify",
            name="Apify",
            category="Web Scraping",
            description="Cloud platform for running web scrapers, social media crawlers, and importing structured business datasets.",
            status="ready" if apify_key else "not_configured",
            is_configured=apify_key,
            env_var="APIFY_TOKEN",
            details="API token configured · Actor crawler integration ready" if apify_key else "Missing APIFY_TOKEN",
            website="https://apify.com",
        ),
        IntegrationItem(
            id="openstreetmap",
            name="OpenStreetMap (Overpass & Nominatim)",
            category="Lead Discovery",
            description="Open-access worldwide geographic database for discovering local businesses, clinics, and service providers.",
            status="public",
            is_configured=True,
            env_var="None (Public API)",
            details="Public API active · No key required · Worldwide coverage",
            website="https://www.openstreetmap.org",
        ),
        IntegrationItem(
            id="google_places",
            name="Google Places API",
            category="Lead Discovery",
            description="Official Google Maps Places API for finding local business coordinates, reviews, and details.",
            status="ready" if google_places_key else "not_configured",
            is_configured=google_places_key,
            env_var="GOOGLE_PLACES_API_KEY",
            details="API key configured" if google_places_key else "Set GOOGLE_PLACES_API_KEY in .env to enable",
            website="https://mapsplatform.google.com",
        ),
        IntegrationItem(
            id="yelp",
            name="Yelp Fusion API",
            category="Lead Discovery",
            description="Directory search for businesses, ratings, and customer reviews in US, UK, and Canada.",
            status="ready" if yelp_key else "not_configured",
            is_configured=yelp_key,
            env_var="YELP_API_KEY",
            details="API key configured" if yelp_key else "Set YELP_API_KEY in .env to enable",
            website="https://fusion.yelp.com",
        ),
        IntegrationItem(
            id="webpush",
            name="Web Push (VAPID)",
            category="Notifications",
            description="Browser Push Service and VAPID protocol for real-time background notifications on outreach replies and events.",
            status="active" if settings.vapid_configured else "not_configured",
            is_configured=settings.vapid_configured,
            env_var="VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY",
            details="VAPID keypair configured · Push delivery active" if settings.vapid_configured else "VAPID keys missing",
            website="https://www.w3.org/TR/push-api/",
        ),
    ]

    configured_count = sum(1 for item in items if item.is_configured)
    return IntegrationsResponse(
        integrations=items,
        total_count=len(items),
        configured_count=configured_count,
    )
