import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.core.errors import AppError
from app.services.url_safety import assert_public_http_url

logger = logging.getLogger(__name__)

CRUX_URL = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"


@dataclass
class CruxOutcome:
    status: str
    detail: str
    lcp: str = ""
    cls: str = ""
    inp: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "detail": self.detail,
            "lcp": self.lcp,
            "cls": self.cls,
            "inp": self.inp,
        }

    def tool(self) -> dict[str, str]:
        return {"name": "Chrome UX Report", "status": self.status, "detail": self.detail}


def parse_crux(payload: object) -> CruxOutcome | None:
    if not isinstance(payload, dict):
        return None
    record = payload.get("record")
    if not isinstance(record, dict):
        return None
    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    lcp = _p75(metrics.get("largest_contentful_paint"), milliseconds=True)
    inp = _p75(metrics.get("interaction_to_next_paint"), milliseconds=True)
    cls = _p75(metrics.get("cumulative_layout_shift"), milliseconds=False)
    if not any((lcp, inp, cls)):
        return None
    parts = []
    if lcp:
        parts.append(f"LCP {lcp}")
    if cls:
        parts.append(f"CLS {cls}")
    if inp:
        parts.append(f"INP {inp}")
    detail = "Real visitors on phones: " + ", ".join(parts) + "."
    return CruxOutcome(status="used", detail=detail, lcp=lcp, cls=cls, inp=inp)


async def fetch_crux(url: str, api_key: str) -> CruxOutcome:
    if not api_key.strip():
        return CruxOutcome(
            status="skipped",
            detail="Set GOOGLE_PAGESPEED_API_KEY to add real-visitor speed data from Chrome.",
        )
    try:
        safe = assert_public_http_url(url)
    except AppError:
        logger.warning("crux_url_blocked")
        return CruxOutcome(status="failed", detail="Real-visitor data could not be requested.")
    parsed = urlsplit(safe)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                CRUX_URL,
                params={"key": api_key.strip()},
                json={"origin": origin, "formFactor": "PHONE"},
            )
    except httpx.HTTPError:
        logger.warning("crux_failed")
        return CruxOutcome(status="failed", detail="Chrome user data did not respond.")
    if response.status_code == 404:
        return CruxOutcome(
            status="unavailable",
            detail="This site does not have enough Chrome user data yet.",
        )
    if response.status_code != 200:
        logger.warning("crux_failed status=%s", response.status_code)
        return CruxOutcome(status="failed", detail="Chrome user data could not be loaded.")
    try:
        parsed_body = parse_crux(response.json())
    except ValueError:
        logger.warning("crux_failed")
        return CruxOutcome(status="failed", detail="Chrome user data could not be loaded.")
    if parsed_body is None:
        return CruxOutcome(
            status="unavailable",
            detail="This site does not have enough Chrome user data yet.",
        )
    return parsed_body


def _p75(metric: object, *, milliseconds: bool) -> str:
    if not isinstance(metric, dict):
        return ""
    percentiles = metric.get("percentiles")
    if not isinstance(percentiles, dict):
        return ""
    value = percentiles.get("p75")
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return ""
    if isinstance(value, str):
        return value.strip()[:40]
    if milliseconds:
        if value >= 1000:
            return f"{value / 1000:.1f} s"
        return f"{round(value)} ms"
    return f"{value:.2f}".rstrip("0").rstrip(".")
