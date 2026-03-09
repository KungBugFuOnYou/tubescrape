from __future__ import annotations

import logging

from tubescrape._filters import SearchFilter
from tubescrape._http import HTTPClient
from tubescrape._innertube import InnerTube
from tubescrape._parsers import ResponseParser
from tubescrape.models import SearchResult

logger = logging.getLogger('tubescrape.search')


class YouTubeSearch:
    """Search YouTube videos via the InnerTube search API.

    No API key required. Uses the same endpoint the YouTube web client uses.

    Args:
        http_client: HTTPClient instance for making requests.
    """

    def __init__(self, http_client: HTTPClient):
        self._http = http_client

    def search(
        self,
        query: str,
        max_results: int = 20,
        params: str = '',
        sort_by: str | None = None,
        upload_date: str | None = None,
        type: str | None = None,
        duration: str | None = None,
        features: str | list[str] | None = None,
    ) -> SearchResult:
        """Search YouTube and return video results.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return.
            params: Raw protobuf-encoded search filter (base64 string).
                    Ignored if any named filter is provided.
            sort_by: Sort order — 'relevance', 'upload_date', 'view_count', 'rating'.
            upload_date: Time filter — 'last_hour', 'today', 'this_week', 'this_month', 'this_year'.
            type: Content type — 'video', 'channel', 'playlist', 'movie'.
            duration: Duration filter — 'short' (<4min), 'medium' (4-20min), 'long' (>20min).
            features: Feature filter(s) — 'live', '4k', 'hd', 'subtitles', etc.

        Returns:
            SearchResult containing matched videos.
        """
        filter_params = self._build_params(
            params, sort_by, upload_date, type, duration, features,
        )
        payload = InnerTube.build_search_payload(query, params=filter_params)

        logger.info('Searching: %r (max_results=%d)', query, max_results)
        response = self._http.post(
            InnerTube.SEARCH_URL,
            json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()

        result = ResponseParser.parse_search_response(data, query, max_results)
        logger.info('Found %d videos for %r', len(result.videos), query)
        return result

    async def asearch(
        self,
        query: str,
        max_results: int = 20,
        params: str = '',
        sort_by: str | None = None,
        upload_date: str | None = None,
        type: str | None = None,
        duration: str | None = None,
        features: str | list[str] | None = None,
    ) -> SearchResult:
        """Async version of search."""
        filter_params = self._build_params(
            params, sort_by, upload_date, type, duration, features,
        )
        payload = InnerTube.build_search_payload(query, params=filter_params)

        logger.info('Searching (async): %r (max_results=%d)', query, max_results)
        response = await self._http.apost(
            InnerTube.SEARCH_URL,
            json=payload,
            params={'prettyPrint': 'false'},
        )
        data = response.json()

        result = ResponseParser.parse_search_response(data, query, max_results)
        logger.info('Found %d videos for %r', len(result.videos), query)
        return result

    @staticmethod
    def _build_params(
        raw_params: str,
        sort_by: str | None,
        upload_date: str | None,
        type: str | None,
        duration: str | None,
        features: str | list[str] | None,
    ) -> str:
        """Build protobuf filter from named params, falling back to raw."""
        has_named = any([sort_by, upload_date, type, duration, features])
        if has_named:
            return SearchFilter.build(
                sort_by=sort_by,
                upload_date=upload_date,
                type=type,
                duration=duration,
                features=features,
            )
        return raw_params
