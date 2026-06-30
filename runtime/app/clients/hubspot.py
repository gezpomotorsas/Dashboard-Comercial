"""Cliente HTTP asíncrono para HubSpot API."""

import asyncio
import logging
from typing import Any

import httpx

from app.clients.hubspot_exceptions import (
    HubSpotAuthenticationError,
    HubSpotNotFoundError,
    HubSpotPermissionError,
    HubSpotRateLimitError,
    HubSpotRequestError,
)
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class HubSpotClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "HubSpotClient":
        await self.open()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def open(self) -> None:
        if self._client is None:
            concurrency = self._settings.association_sync_hubspot_concurrency
            pool_size = concurrency + 10
            self._client = httpx.AsyncClient(
                base_url=self._settings.hubspot_base_url,
                timeout=self._settings.hubspot_timeout_seconds,
                headers={
                    "Authorization": f"Bearer {self._settings.hubspot_access_token.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                limits=httpx.Limits(
                    max_connections=pool_size,
                    max_keepalive_connections=concurrency,
                ),
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("HubSpot client is not initialized")
        return self._client

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return

        retry_after_header = response.headers.get("Retry-After")
        retry_after = float(retry_after_header) if retry_after_header else None
        message = self._extract_error_message(response)

        if response.status_code == 401:
            raise HubSpotAuthenticationError(message)
        if response.status_code == 403:
            raise HubSpotPermissionError(message)
        if response.status_code == 404:
            raise HubSpotNotFoundError(message)
        if response.status_code == 429:
            raise HubSpotRateLimitError(message, retry_after=retry_after)
        if response.status_code >= 500:
            raise HubSpotRequestError(message, status_code=response.status_code)
        raise HubSpotRequestError(message, status_code=response.status_code)

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict) and payload.get("message"):
                return str(payload["message"])
        except Exception:
            pass
        return f"HubSpot request failed with status {response.status_code}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        max_retries = self._settings.hubspot_max_retries
        attempt = 0

        while True:
            attempt += 1
            try:
                response = await self.client.request(method, path, params=params, json=json_body)
                self._raise_for_status(response)
                if response.status_code == 204:
                    return {}
                return response.json()
            except HubSpotRateLimitError as exc:
                if attempt > max_retries:
                    raise
                wait_seconds = exc.retry_after or min(2**attempt, 30)
                logger.warning("HubSpot rate limit, retrying in %ss", wait_seconds)
                await asyncio.sleep(wait_seconds)
            except HubSpotRequestError as exc:
                if exc.status_code and exc.status_code >= 500 and attempt <= max_retries:
                    wait_seconds = min(2**attempt, 30)
                    logger.warning("HubSpot server error %s, retrying", exc.status_code)
                    await asyncio.sleep(wait_seconds)
                    continue
                raise

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.request("GET", path, params=params)

    async def post(
        self,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.request("POST", path, params=params, json_body=json_body)

    async def paginate(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        current_params = dict(params or {})
        if "limit" not in current_params:
            current_params["limit"] = self._settings.hubspot_default_limit

        while True:
            payload = await self.get(path, params=current_params)
            results = payload.get("results", [])
            collected.extend(results)

            if limit is not None and len(collected) >= limit:
                return collected[:limit]

            paging = payload.get("paging") or {}
            next_page = paging.get("next") or {}
            after = next_page.get("after")
            if not after:
                break
            current_params["after"] = after

        return collected

    async def search_objects(
        self,
        object_type: str,
        *,
        filter_groups: list[dict[str, Any]],
        properties: list[str] | None = None,
        limit: int = 100,
        after: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "filterGroups": filter_groups,
            "limit": limit,
        }
        if properties:
            body["properties"] = properties
        if after:
            body["after"] = after
        return await self.post(f"/crm/v3/objects/{object_type}/search", json_body=body)

    async def batch_read_objects(
        self,
        object_type: str,
        *,
        object_ids: list[str],
        properties: list[str],
    ) -> dict[str, Any]:
        if not object_ids:
            return {"results": [], "status": "COMPLETE"}
        body = {
            "inputs": [{"id": str(object_id)} for object_id in object_ids],
            "properties": properties,
        }
        return await self.post(f"/crm/v3/objects/{object_type}/batch/read", json_body=body)

    async def batch_read_associations(
        self,
        from_object_type: str,
        to_object_type: str,
        object_ids: list[str],
    ) -> dict[str, Any]:
        if not object_ids:
            return {"results": [], "errors": []}
        body = {"inputs": [{"id": str(obj_id)} for obj_id in object_ids]}
        return await self.post(
            f"/crm/v4/associations/{from_object_type}/{to_object_type}/batch/read",
            json_body=body,
        )

    async def get_association_labels(
        self,
        from_object_type: str,
        to_object_type: str,
    ) -> list[dict[str, Any]]:
        payload = await self.get(f"/crm/v4/associations/{from_object_type}/{to_object_type}/labels")
        return payload.get("results", [])


_hubspot_client: HubSpotClient | None = None


async def get_hubspot_client() -> HubSpotClient:
    global _hubspot_client
    if _hubspot_client is None:
        _hubspot_client = HubSpotClient()
        await _hubspot_client.open()
    return _hubspot_client


async def close_hubspot_client() -> None:
    global _hubspot_client
    if _hubspot_client is not None:
        await _hubspot_client.close()
        _hubspot_client = None
