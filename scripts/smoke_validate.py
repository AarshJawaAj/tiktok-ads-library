"""Local smoke checks that do not need real TikTok credentials."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.main import (  # noqa: E402
    SUPPORTED_COUNTRIES,
    _flatten_ad,
    _normalize_date,
    _one_year_ago_yyyymmdd,
    get_client_token,
)
import httpx


def test_helpers() -> None:
    assert _normalize_date('2026-01-01', fallback='') == '20260101'
    assert _normalize_date('20260101', fallback='') == '20260101'
    assert len(_one_year_ago_yyyymmdd()) == 8
    assert 'FR' in SUPPORTED_COUNTRIES
    assert 'US' not in SUPPORTED_COUNTRIES

    flat = _flatten_ad(
        {
            'ad': {
                'id': 123,
                'first_shown_date': 20260101,
                'last_shown_date': 20260102,
                'status': 'active',
                'image_urls': ['https://example.com/a.jpg'],
                'videos': [{'url': 'https://example.com/a.mp4'}],
                'reach': {'unique_users_seen': '11K'},
            },
            'advertiser': {
                'business_id': 99,
                'business_name': 'Demo Co',
                'paid_for_by': 'Demo Co',
            },
        },
        search_term='coffee',
        search_type='exact_phrase',
    )
    assert flat['adId'] == 123
    assert flat['advertiserBusinessName'] == 'Demo Co'
    assert flat['videoUrls'] == ['https://example.com/a.mp4']
    print('helpers_ok')


async def test_token_endpoint_reachable() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            await get_client_token(client, 'invalid_key', 'invalid_secret')
            raise AssertionError('expected token failure')
        except RuntimeError as exc:
            msg = str(exc).lower()
            assert 'tiktok token request failed' in msg
            print('token_endpoint_reachable')


if __name__ == '__main__':
    test_helpers()
    asyncio.run(test_token_endpoint_reachable())
    print('smoke_ok')
