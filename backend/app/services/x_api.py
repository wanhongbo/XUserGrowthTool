from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.config import get_settings


DEFAULT_QUERIES = [
    '("private photos" OR "photo vault" OR "secure photo storage" OR "encrypted photos") lang:en place_country:US -is:retweet',
    '("encrypted gallery" OR "private gallery" OR "secure gallery" OR "hidden photos") lang:en place_country:US -is:retweet',
    '("Google Photos alternative" OR "iCloud Photos privacy" OR "photo backup privacy") lang:en place_country:US -is:retweet',
    '("EXIF privacy" OR "metadata removal" OR "remove location from photos") lang:en place_country:US -is:retweet',
    '("end-to-end encrypted photos" OR "encrypted photo backup" OR "cloud photo privacy") lang:en place_country:US -is:retweet',
]


class XApiError(RuntimeError):
    pass


class XApiClient:
    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token
        self.base_url = "https://api.x.com/2"

    async def recent_search(self, query: str, max_results: int = 25) -> dict[str, Any]:
        if not self.bearer_token:
            raise XApiError("X_BEARER_TOKEN is not configured")

        params = {
            "query": query,
            "max_results": max(10, min(max_results, 100)),
            "tweet.fields": "author_id,created_at,public_metrics,lang,conversation_id,referenced_tweets",
            "expansions": "author_id",
            "user.fields": "id,name,username,description,public_metrics,verified,verified_type,receives_your_dm,created_at,protected,url,location,profile_image_url",
        }
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        try:
            proxy = get_settings().outbound_proxy or None
            async with httpx.AsyncClient(timeout=30, proxy=proxy) as client:
                response = await client.get(f"{self.base_url}/tweets/search/recent", params=params, headers=headers)
        except httpx.ConnectTimeout as exc:
            raise XApiError("Timed out connecting to X API. Check network/VPN/proxy access to api.x.com.") from exc
        except httpx.TimeoutException as exc:
            raise XApiError("Timed out waiting for X API response. Retry later or reduce query volume.") from exc
        except httpx.HTTPError as exc:
            raise XApiError(f"Could not reach X API: {exc}") from exc
        if response.status_code == 429:
            raise XApiError("X API rate limit reached; retry later")
        if response.status_code >= 400:
            raise XApiError(f"X API error {response.status_code}: {response.text[:300]}")
        return response.json()


def parse_x_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()
