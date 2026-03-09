from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from tubescrape.api.deps import get_youtube
from tubescrape.api.schemas import SearchResponse
from tubescrape.client import YouTube

router = APIRouter()


@router.get('/search', response_model=SearchResponse)
async def search_videos(
    q: str = Query(..., description='Search query'),
    max_results: int = Query(20, ge=1, le=50, description='Maximum results'),
    sort_by: str | None = Query(None, description='Sort: relevance, upload_date, view_count, rating'),
    upload_date: str | None = Query(None, description='Filter: last_hour, today, this_week, this_month, this_year'),
    type: str | None = Query(None, description='Type: video, channel, playlist, movie'),
    duration: str | None = Query(None, description='Duration: short, medium, long'),
    features: str | None = Query(None, description='Features (comma-separated): live, 4k, hd, subtitles, hdr'),
    params: str = Query('', description='Raw protobuf-encoded search filter (base64)'),
    yt: YouTube = Depends(get_youtube),
) -> SearchResponse:
    """Search YouTube videos with optional filters."""
    feature_list = [f.strip() for f in features.split(',')] if features else None
    result = await yt.asearch(
        q,
        max_results=max_results,
        params=params,
        sort_by=sort_by,
        upload_date=upload_date,
        type=type,
        duration=duration,
        features=feature_list,
    )
    return SearchResponse(
        query=result.query,
        videos=[v.to_dict() for v in result.videos],
    )
