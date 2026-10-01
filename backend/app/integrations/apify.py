import logging
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

# Official Apify API v2. The token is sent as a bearer header and is never
# placed in the URL or in error messages returned to the browser.
# Actors the user created or used: GET /v2/actors
# Recent runs: GET /v2/actor-runs
# Start: POST /v2/acts/{actorId}/runs
# Actor: GET /v2/acts/{actorId}
# Build (input schema): GET /v2/acts/{actorId}/builds/default
# Run: GET /v2/actor-runs/{runId}
# Abort: POST /v2/actor-runs/{runId}/abort
# Dataset: GET /v2/actor-runs/{runId}/dataset/items


class ApifyClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.apify.com/v2",
        http: httpx.Client | None = None,
    ) -> None:
        self._token = token
        self._base = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=30.0)
        self._owns_client = http is None

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def list_actors(self) -> list[dict[str, object]]:
        # Created or used actors. Most recently run first.
        return self._pages(
            "/actors",
            {"desc": "1", "sortBy": "stats.lastRunStartedAt"},
            max_items=1000,
        )

    def list_runs(self, *, limit: int = 50) -> list[dict[str, object]]:
        return self._pages("/actor-runs", {"desc": "1"}, max_items=limit)

    def get_actor(self, actor_ref: str) -> dict[str, object]:
        response = self._request("GET", f"/acts/{_path_id(actor_ref)}")
        _raise_for_status(response, not_found="Apify could not find that actor.")
        return _object(response, "Apify returned an unexpected actor record.")

    def get_default_build(self, actor_id: str) -> dict[str, object]:
        response = self._request("GET", f"/acts/{_path_id(actor_id)}/builds/default")
        _raise_for_status(response, not_found="Apify could not find a build for that actor.")
        return _object(response, "Apify returned an unexpected build record.")

    def start_run(
        self,
        actor_id: str,
        run_input: dict[str, object],
        *,
        max_items: int | None = None,
        max_total_charge_usd: float | None = None,
    ) -> dict[str, object]:
        # waitForFinish is left unset so Apify returns immediately (default 0).
        # The synchronous run endpoints can bill a run before this API responds.
        params: dict[str, object] = {}
        if max_items is not None:
            params["maxItems"] = max_items
        if max_total_charge_usd is not None:
            params["maxTotalChargeUsd"] = max_total_charge_usd
        response = self._request(
            "POST",
            f"/acts/{_path_id(actor_id)}/runs",
            params=params or None,
            json_body=run_input,
        )
        _raise_for_status(response, not_found="Apify could not find that actor.")
        return _object(response, "Apify returned an unexpected run record.")

    def get_run(self, run_id: str) -> dict[str, object]:
        response = self._request("GET", f"/actor-runs/{_path_id(run_id)}")
        _raise_for_status(response, not_found="Apify could not find that run.")
        return _object(response, "Apify returned an unexpected run record.")

    def abort_run(self, run_id: str) -> dict[str, object]:
        response = self._request("POST", f"/actor-runs/{_path_id(run_id)}/abort")
        _raise_for_status(response, not_found="Apify could not find that run.")
        return _object(response, "Apify returned an unexpected run record.")

    def dataset_items(
        self,
        run_id: str,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[dict[str, object]], int]:
        response = self._request(
            "GET",
            f"/actor-runs/{_path_id(run_id)}/dataset/items",
            params={
                "format": "json",
                "clean": "true",
                "offset": offset,
                "limit": limit,
            },
        )
        _raise_for_status(response, not_found="Apify could not find results for that run.")
        payload = _json(response)
        if not isinstance(payload, list):
            raise AppError(
                code="APIFY_ERROR",
                message="Apify returned an unexpected results page.",
                status_code=502,
            )
        items = [item for item in payload if isinstance(item, dict)]
        total = _header_int(response.headers.get("X-Apify-Pagination-Total"), len(items))
        return items, total

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
    ) -> httpx.Response:
        try:
            response = self._http.request(
                method,
                f"{self._base}{path}",
                params=params,
                json=json_body,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/json",
                },
            )
        except httpx.TimeoutException as exc:
            logger.warning("apify_timeout method=%s path=%s", method, path)
            raise AppError(
                code="APIFY_TIMEOUT",
                message="Apify took too long to respond.",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("apify_unreachable method=%s path=%s", method, path)
            raise AppError(
                code="APIFY_UNAVAILABLE",
                message="Apify could not be reached.",
                status_code=502,
            ) from exc
        if response.status_code >= 400:
            logger.warning(
                "apify_request_failed method=%s path=%s status=%s",
                method,
                path,
                response.status_code,
            )
        return response

    def _pages(
        self,
        path: str,
        params: dict[str, object],
        *,
        max_items: int,
    ) -> list[dict[str, object]]:
        collected: list[dict[str, object]] = []
        offset = 0
        while len(collected) < max_items:
            page_limit = min(1000, max_items - len(collected))
            response = self._request(
                "GET",
                path,
                params={**params, "offset": offset, "limit": page_limit},
            )
            _raise_for_status(response, not_found="Apify could not list those records.")
            page, total = _page(response)
            collected.extend(page)
            offset += len(page)
            if not page or offset >= total:
                break
        return collected[:max_items]


@contextmanager
def apify_client(settings: Settings) -> Iterator[ApifyClient]:
    if not settings.apify_token:
        raise AppError(
            code="APIFY_NOT_CONFIGURED",
            message="Set APIFY_TOKEN on the server before using Apify.",
            status_code=503,
        )
    client = ApifyClient(settings.apify_token, base_url=settings.apify_api_base)
    try:
        yield client
    finally:
        client.close()


def _path_id(value: str) -> str:
    if value.count("/") == 1:
        value = value.replace("/", "~", 1)
    return quote(value, safe="~")


def _json(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError as exc:
        raise AppError(
            code="APIFY_ERROR",
            message="Apify returned a response that could not be read.",
            status_code=502,
        ) from exc


def _page(response: httpx.Response) -> tuple[list[dict[str, object]], int]:
    payload = _json(response)
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise AppError(
            code="APIFY_ERROR",
            message="Apify returned an unexpected list.",
            status_code=502,
        )
    items = [item for item in data["items"] if isinstance(item, dict)]
    total = data.get("total")
    if not isinstance(total, int):
        total = len(items)
    return items, total


def _object(response: httpx.Response, message: str) -> dict[str, object]:
    payload = _json(response)
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    raise AppError(code="APIFY_ERROR", message=message, status_code=502)


def _raise_for_status(response: httpx.Response, *, not_found: str) -> None:
    if response.is_success:
        return
    error_type = _error_type(response)
    if response.status_code in {401, 403} or error_type in {"token-not-found", "unauthorized"}:
        raise AppError(
            code="APIFY_UNAUTHORIZED",
            message="Apify rejected the API token. Check APIFY_TOKEN on the server.",
            status_code=502,
        )
    if response.status_code == 404 or error_type in {
        "actor-not-found",
        "record-not-found",
        "run-not-found",
    }:
        raise AppError(code="APIFY_NOT_FOUND", message=not_found, status_code=404)
    if response.status_code == 400 or error_type in {"invalid-input", "invalid-request"}:
        raise AppError(
            code="APIFY_REJECTED",
            message="Apify rejected that request.",
            status_code=400,
        )
    raise AppError(
        code="APIFY_ERROR",
        message="Apify returned an unexpected error.",
        status_code=502,
    )


def _error_type(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        error_type = payload["error"].get("type")
        if isinstance(error_type, str):
            return error_type
    return ""


def _header_int(value: str | None, fallback: int) -> int:
    if not value:
        return fallback
    try:
        return int(float(value))
    except ValueError:
        return fallback
