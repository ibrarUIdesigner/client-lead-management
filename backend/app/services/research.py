"""Lead research service using Tavily and Exa search APIs with sequential fallback."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.enums import ResearchStatus
from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.repositories.activities import ActivityRepository
from app.repositories.leads import LeadRepository
from app.services.persistence import flush_or_reject

logger = logging.getLogger(__name__)


class ResearchService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.leads = LeadRepository(session)
        self.activities = ActivityRepository(session)

    def get_for_lead(self, lead_id: UUID) -> LeadResearch | None:
        return self.session.scalar(
            select(LeadResearch).where(LeadResearch.lead_id == lead_id)
        )

    def prepare_research(
        self,
        lead_id: UUID,
        *,
        force_refresh: bool = False,
        custom_query: str | None = None,
        preferred_tool: str | None = None,
    ) -> tuple[LeadResearch, bool]:
        lead = self.leads.get(lead_id)
        if lead is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )

        existing = self.get_for_lead(lead_id)
        if (
            existing
            and existing.status == ResearchStatus.COMPLETED.value
            and not force_refresh
            and not custom_query
        ):
            return existing, False

        research = existing
        if research is None:
            research = LeadResearch(lead_id=lead.id, status=ResearchStatus.RUNNING.value)
            self.session.add(research)
        else:
            research.status = ResearchStatus.RUNNING.value
            research.error_message = None

        query_parts = [lead.business_name]
        if lead.city:
            query_parts.append(lead.city)
        if lead.industry:
            query_parts.append(lead.industry)
        base_query = custom_query.strip() if custom_query else " ".join(query_parts).strip()
        research.query_used = base_query

        flush_or_reject(self.session)
        self.session.commit()
        return research, True

    def execute_research(
        self,
        research_id: UUID,
        *,
        preferred_tool: str | None = None,
    ) -> LeadResearch:
        research = self.session.get(LeadResearch, research_id)
        if research is None:
            raise AppError(code="RESEARCH_NOT_FOUND", message="Research not found", status_code=404)
        lead = self.leads.get(research.lead_id)
        if lead is None:
            research.status = ResearchStatus.FAILED.value
            research.error_message = "Lead not found."
            self.session.commit()
            return research

        base_query = research.query_used or lead.business_name
        try:
            (
                sources,
                provider_used,
                fallback_used,
                fallback_reason,
                tavily_data,
                exa_data,
            ) = self._fetch_sources_sequential(base_query, lead, preferred_tool or "tavily")

            research_data, summary_markdown = self._synthesize(lead, sources, base_query)
            research_data["provider_used"] = provider_used
            research_data["fallback_used"] = fallback_used
            research_data["fallback_reason"] = fallback_reason

            research.status = ResearchStatus.COMPLETED.value
            research.summary = summary_markdown
            research.research_data = research_data
            research.sources = sources
            research.raw_tavily = tavily_data or None
            research.raw_exa = exa_data or None
            research.completed_at = datetime.now(UTC)
            research.error_message = None

            flush_or_reject(self.session)
            primary_name = (preferred_tool or "tavily").title()
            tool_desc = (
                f"{provider_used.title()} (fallback from {primary_name} limit)"
                if fallback_used and provider_used
                else (provider_used.title() if provider_used else "Web Search")
            )
            self.activities.add(
                lead.id,
                "research_completed",
                "Lead research completed",
                description=f"Researched {lead.business_name} using {tool_desc}.",
                details={
                    "sources_count": len(sources),
                    "provider": provider_used,
                    "fallback_used": fallback_used,
                    "query": base_query,
                },
            )
            self.session.commit()
            return research

        except Exception as exc:
            logger.exception("lead_research_failed research_id=%s", research_id)
            research.status = ResearchStatus.FAILED.value
            research.error_message = str(exc)
            flush_or_reject(self.session)
            self.session.commit()
            return research

    def research_lead(
        self,
        lead_id: UUID,
        *,
        force_refresh: bool = False,
        custom_query: str | None = None,
        preferred_tool: str | None = None,
    ) -> LeadResearch:
        research, should_run = self.prepare_research(
            lead_id,
            force_refresh=force_refresh,
            custom_query=custom_query,
            preferred_tool=preferred_tool,
        )
        if not should_run:
            return research
        return self.execute_research(research.id, preferred_tool=preferred_tool)

    def _fetch_sources_sequential(
        self,
        base_query: str,
        lead: Lead | None = None,
        preferred_tool: str = "tavily",
    ) -> tuple[list[dict[str, Any]], str | None, bool, str | None, dict[str, Any], dict[str, Any]]:
        """Search sequentially with a single tool; fallback to secondary if primary hits limits."""
        primary_tool = (preferred_tool or "tavily").strip().lower()
        if primary_tool not in {"tavily", "exa"}:
            primary_tool = "tavily"
        fallback_tool = "exa" if primary_tool == "tavily" else "tavily"

        provider_used: str | None = None
        fallback_used = False
        fallback_reason: str | None = None
        tavily_data: dict[str, Any] = {}
        exa_data: dict[str, Any] = {}
        sources: list[dict[str, Any]] = []

        primary_error: str | None = None
        if primary_tool == "tavily":
            try:
                tavily_data = self._search_tavily(base_query, lead)
            except Exception as e:
                tavily_data = {"error": str(e), "results": []}
            t_results = tavily_data.get("results", []) if isinstance(tavily_data, dict) else []
            if t_results:
                provider_used = "tavily"
                for item in t_results:
                    if isinstance(item, dict):
                        sources.append(
                            {
                                "title": item.get("title") or "Tavily Result",
                                "url": item.get("url") or "",
                                "snippet": item.get("content") or "",
                                "provider": "tavily",
                                "score": item.get("score"),
                            }
                        )
            else:
                primary_error = (
                    (tavily_data.get("error") if isinstance(tavily_data, dict) else None)
                    or "No results returned from Tavily"
                )
        else:
            try:
                exa_data = self._search_exa(base_query, lead)
            except Exception as e:
                exa_data = {"error": str(e), "results": []}
            e_results = exa_data.get("results", []) if isinstance(exa_data, dict) else []
            if e_results:
                provider_used = "exa"
                for item in e_results:
                    if isinstance(item, dict):
                        highlights = item.get("highlights") or []
                        snippet = " ".join(highlights) if highlights else item.get("text") or ""
                        sources.append(
                            {
                                "title": item.get("title") or "Exa Result",
                                "url": item.get("url") or "",
                                "snippet": snippet[:500],
                                "highlights": highlights,
                                "provider": "exa",
                                "published_date": item.get("published_date"),
                            }
                        )
            else:
                primary_error = (
                    (exa_data.get("error") if isinstance(exa_data, dict) else None)
                    or "No results returned from Exa"
                )

        if not sources:
            fallback_used = True
            fallback_reason = primary_error
            logger.warning(
                "%s reached limit or failed (%s). Falling back to %s search.",
                primary_tool.title(),
                primary_error,
                fallback_tool.title(),
            )

            if fallback_tool == "exa":
                try:
                    exa_data = self._search_exa(base_query, lead)
                except Exception as e:
                    exa_data = {"error": str(e), "results": []}
                e_results = exa_data.get("results", []) if isinstance(exa_data, dict) else []
                if e_results:
                    provider_used = "exa"
                    for item in e_results:
                        if isinstance(item, dict):
                            highlights = item.get("highlights") or []
                            snippet = " ".join(highlights) if highlights else item.get("text") or ""
                            sources.append(
                                {
                                    "title": item.get("title") or "Exa Result",
                                    "url": item.get("url") or "",
                                    "snippet": snippet[:500],
                                    "highlights": highlights,
                                    "provider": "exa",
                                    "published_date": item.get("published_date"),
                                }
                            )
                elif isinstance(exa_data, dict) and exa_data.get("error"):
                    raise AppError(
                        code="RESEARCH_FAILED",
                        message=(
                            f"Both research tools failed. Tavily limit/error: {primary_error}. "
                            f"Exa error: {exa_data.get('error')}."
                        ),
                        status_code=502,
                    )
            else:
                try:
                    tavily_data = self._search_tavily(base_query, lead)
                except Exception as e:
                    tavily_data = {"error": str(e), "results": []}
                t_results = tavily_data.get("results", []) if isinstance(tavily_data, dict) else []
                if t_results:
                    provider_used = "tavily"
                    for item in t_results:
                        if isinstance(item, dict):
                            sources.append(
                                {
                                    "title": item.get("title") or "Tavily Result",
                                    "url": item.get("url") or "",
                                    "snippet": item.get("content") or "",
                                    "provider": "tavily",
                                    "score": item.get("score"),
                                }
                            )
                elif isinstance(tavily_data, dict) and tavily_data.get("error"):
                    raise AppError(
                        code="RESEARCH_FAILED",
                        message=(
                            f"Both research tools failed. Exa limit/error: {primary_error}. "
                            f"Tavily error: {tavily_data.get('error')}."
                        ),
                        status_code=502,
                    )

        return sources, provider_used, fallback_used, fallback_reason, tavily_data, exa_data

    def _search_tavily(self, query: str, lead: Lead) -> dict[str, Any]:
        api_key = self.settings.tavily_api_key.strip()
        if not api_key:
            return {"error": "Missing Tavily API key", "results": []}

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            res = client.search(
                query=f"{query} overview services customer reviews",
                search_depth="advanced",
                max_results=8,
            )
            if not isinstance(res, dict):
                return {"error": "Invalid Tavily response", "results": []}
            if "error" in res:
                return {"error": str(res["error"]), "results": []}
            return res
        except Exception as exc:
            logger.warning("tavily_search_error: %s", exc)
            return {"error": str(exc), "results": []}

    def _search_exa(self, query: str, lead: Lead) -> dict[str, Any]:
        api_key = self.settings.exa_api_key.strip()
        if not api_key:
            return {"error": "Missing Exa API key", "results": []}

        try:
            from exa_py import Exa

            exa = Exa(api_key=api_key)
            res = exa.search(
                f"{query} news updates market positioning",
                num_results=6,
                type="auto",
                contents={"highlights": True},
            )
            results = []
            for item in getattr(res, "results", []):
                results.append(
                    {
                        "title": getattr(item, "title", None) or "",
                        "url": getattr(item, "url", None) or "",
                        "highlights": getattr(item, "highlights", []) or [],
                        "published_date": getattr(item, "published_date", None) or "",
                    }
                )
            return {"results": results}
        except Exception as exc:
            logger.warning("exa_search_error: %s", exc)
            return {"error": str(exc), "results": []}

    def _synthesize(
        self,
        lead: Lead,
        sources: list[dict[str, Any]],
        query: str,
    ) -> tuple[dict[str, Any], str]:
        """Synthesize web intelligence into 2 comprehensive sections: Research and Summary."""
        llm_result = self._call_llm_synthesis(lead, sources, query)
        if llm_result is not None:
            return llm_result

        return self._heuristic_synthesis(lead, sources, query)

    def _call_llm_synthesis(
        self,
        lead: Lead,
        sources: list[dict[str, Any]],
        query: str,
    ) -> tuple[dict[str, Any], str] | None:
        gemini_ready = bool(self.settings.gemini_api_key.strip())
        groq_ready = bool(self.settings.groq_api_key.strip())
        if not (gemini_ready or groq_ready):
            return None

        # Build context from sources
        source_texts = []
        for idx, src in enumerate(sources[:10], 1):
            source_texts.append(
                f"[{idx}] {src.get('title')} ({src.get('url')} - {src.get('provider')})\n"
                f"Excerpt: {src.get('snippet') or ''}\n"
            )
        gathered_context = "\n".join(source_texts) or "No web search snippets returned."

        loc_str = f"{lead.city or ''} {lead.country or ''}".strip()
        prompt = (
            "You are a Senior B2B Intelligence & Sales Strategy Analyst.\n"
            f"Analyze research for '{lead.business_name}' "
            f"(Industry: {lead.industry or 'Unknown'}, Location: {loc_str}, "
            f"Website: {lead.website_url or 'None'}).\n\n"
            f"RESEARCHED WEB INTELLIGENCE:\n{gathered_context}\n\n"
            "Generate TWO COMPREHENSIVE SECTIONS:\n"
            "SECTION 1: COMPREHENSIVE RESEARCH\n"
            "- Company Profile: What the company does, primary value proposition, customers.\n"
            "- Core Offerings: Products, services, specialties.\n"
            "- Online & Digital Presence: Web presence quality, reputation, reviews, gaps.\n"
            "- Pain Points & Gaps: Concrete operational, marketing, CX, or digital gaps.\n"
            "- Competitors & Market: Market positioning and local/industry competitive landscape.\n"
            "- Recent News / Updates: Recent developments, milestones, or press.\n\n"
            "SECTION 2: SUMMARY & PROACTIVE SOLUTIONS\n"
            "- Executive Summary: Strategic assessment of the business and bottlenecks.\n"
            "- High-Impact Opportunities: Untapped revenue or conversion opportunities.\n"
            "- Proactive Solutions We Can Offer: 3-5 concrete solutions we can pitch "
            "to solve their pain points (e.g., lead funnel, mobile redesign, social proof).\n\n"
            "Respond with clean JSON matching this exact structure:\n"
            "{\n"
            '  "company_profile": "...",\n'
            '  "services_and_offerings": "...",\n'
            '  "digital_presence": "...",\n'
            '  "pain_points_and_gaps": ["pain point 1", "pain point 2", ...],\n'
            '  "competitors_and_market": "...",\n'
            '  "recent_news": ["update 1", ...],\n'
            '  "executive_summary": "...",\n'
            '  "high_impact_opportunities": ["opportunity 1", "opportunity 2", ...],\n'
            '  "proactive_solutions": ["solution 1", "solution 2", ...]\n'
            "}\n"
        )

        try:
            with httpx.Client(timeout=45.0) as client:
                raw_json = None
                if gemini_ready:
                    raw_json = self._gemini_call(client, prompt)
                if not raw_json and groq_ready:
                    raw_json = self._groq_call(client, prompt)

                if raw_json:
                    data = json.loads(raw_json)
                    return self._format_synthesis(lead, data)
        except Exception as exc:
            logger.warning("llm_synthesis_failed: %s", exc)

        return None

    def _gemini_call(self, client: httpx.Client, prompt: str) -> str | None:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent?key={self.settings.gemini_api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }
        resp = client.post(url, json=payload)
        if resp.status_code == 200:
            result = resp.json()
            candidates = result.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text")
        return None

    def _groq_call(self, client: httpx.Client, prompt: str) -> str | None:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a professional B2B intelligence analyst. "
                        "Always respond in valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }
        resp = client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content")
        return None

    def _heuristic_synthesis(
        self,
        lead: Lead,
        sources: list[dict[str, Any]],
        query: str,
    ) -> tuple[dict[str, Any], str]:
        pain_points = [
            f"Limited online direct conversion channels for {lead.business_name}.",
            "Missing modern mobile-first interactive experience for prospective clients.",
            "Underutilized digital trust signals and automated inquiry follow-up.",
        ]
        if not lead.website_url:
            pain_points.insert(
                0,
                "Business has no dedicated website, relying on third-party directories.",
            )

        proactive_solutions = [
            f"Launch a modern homepage tailored for {lead.industry or 'their target market'}.",
            "Deploy an automated 1-click consultation or appointment request flow.",
            "Showcase verified customer testimonials and badges prominently above the fold.",
            "Implement high-speed Core Web Vitals optimization and local SEO schema.",
        ]

        site_status = (
            f"Website present at {lead.website_url}"
            if lead.website_url
            else "No dedicated official website discovered"
        )
        data = {
            "company_profile": (
                f"{lead.business_name} provides {lead.industry or 'specialized services'} in "
                f"{lead.city or 'their local region'}. Researched from {len(sources)} sources."
            ),
            "services_and_offerings": (
                f"Core operations centered on {lead.industry or 'commercial services'} with "
                "direct client engagements."
            ),
            "digital_presence": (
                f"Current status: {site_status}. "
                "Web intelligence retrieved across search engines."
            ),
            "pain_points_and_gaps": pain_points,
            "competitors_and_market": (
                f"Competes in {lead.industry or 'local business'} sector against established "
                "regional and digital-first providers."
            ),
            "recent_news": [f"Active business presence identified for {lead.business_name}."],
            "executive_summary": (
                f"{lead.business_name} is an established {lead.industry or 'business'} based in "
                f"{lead.city or 'their market'}. While they maintain operational activity, their "
                "digital customer acquisition and presence have notable room for modernization. "
                "Addressing their current digital gaps presents a strong opportunity."
            ),
            "high_impact_opportunities": [
                "Direct lead conversion optimization via frictionless contact pathways.",
                "Elevating brand credibility through modern digital aesthetics and social proof.",
            ],
            "proactive_solutions": proactive_solutions,
        }
        return self._format_synthesis(lead, data)

    def _format_synthesis(self, lead: Lead, data: dict[str, Any]) -> tuple[dict[str, Any], str]:
        company_profile = data.get("company_profile") or f"{lead.business_name} overview."
        offerings = data.get("services_and_offerings") or "Commercial offerings and services."
        digital = data.get("digital_presence") or "Digital presence overview."
        pain_points = data.get("pain_points_and_gaps") or []
        competitors = data.get("competitors_and_market") or "Competitive landscape."
        news = data.get("recent_news") or []

        exec_summary = (
            data.get("executive_summary") or f"Strategic assessment of {lead.business_name}."
        )
        opportunities = data.get("high_impact_opportunities") or []
        solutions = data.get("proactive_solutions") or []

        pain_md = (
            "\n".join(f"- {p}" for p in pain_points)
            if pain_points
            else "- Noted general operational gaps."
        )
        news_md = "\n".join(f"- {n}" for n in news) if news else "- No major recent press."
        opps_md = (
            "\n".join(f"- {o}" for o in opportunities)
            if opportunities
            else "- Modern digital customer acquisition."
        )
        solutions_md = (
            "\n".join(f"- {s}" for s in solutions)
            if solutions
            else "- Tailored digital customer engagement."
        )

        summary_markdown = (
            f"## SECTION 1: COMPREHENSIVE RESEARCH\n\n"
            f"### Company Profile\n{company_profile}\n\n"
            f"### Services & Offerings\n{offerings}\n\n"
            f"### Digital & Online Presence\n{digital}\n\n"
            f"### Identified Pain Points & Bottlenecks\n{pain_md}\n\n"
            f"### Competitive & Market Positioning\n{competitors}\n\n"
            f"### Recent Developments & News\n{news_md}\n\n"
            f"---\n\n"
            f"## SECTION 2: EXECUTIVE SUMMARY & PROACTIVE SOLUTIONS\n\n"
            f"### Strategic Assessment\n{exec_summary}\n\n"
            f"### High-Impact Opportunities\n{opps_md}\n\n"
            f"### Proactive Solutions to Pitch\n{solutions_md}\n"
        )

        structured_data = {
            "company_profile": company_profile,
            "services_and_offerings": offerings,
            "digital_presence": digital,
            "pain_points_and_gaps": pain_points,
            "competitors_and_market": competitors,
            "recent_news": news,
            "executive_summary": exec_summary,
            "high_impact_opportunities": opportunities,
            "proactive_solutions": solutions,
        }

        return structured_data, summary_markdown
