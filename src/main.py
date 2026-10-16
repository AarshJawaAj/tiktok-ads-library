"""TikTok Ads Library Search — draft Apify Actor.

Uses the official Commercial Content API (scope research.adlib.basic)
to search ads by keyword or exact phrase and write rows to the dataset.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from apify import Actor

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None
else:
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')

TOKEN_URL = 'https://open.tiktokapis.com/v2/oauth/token/'
QUERY_URL = 'https://open.tiktokapis.com/v2/research/adlib/ad/query/'
DETAIL_URL = 'https://open.tiktokapis.com/v2/research/adlib/ad/detail/'
CHARGE_EVENT_FOUND_AD = 'found-ad'

QUERY_FIELDS = ','.join(
    [
        'ad.id',
        'ad.first_shown_date',
        'ad.last_shown_date',
        'ad.status',
        'ad.status_statement',
        'ad.videos',
        'ad.image_urls',
        'ad.reach',
        'advertiser.business_id',
        'advertiser.business_name',
        'advertiser.paid_for_by',
    ]
)

DETAIL_FIELDS = ','.join(
    [
        'ad.id',
        'ad.first_shown_date',
        'ad.last_shown_date',
        'ad.status',
        'ad.status_statement',
        'ad.videos',
        'ad.image_urls',
        'ad.reach',
        'ad.title',
        'ad.external_url',
        'ad.download_url',
        'ad.call_to_action',
        'ad.advertising_objective',
        'ad.rejection_info',
        'advertiser.business_id',
        'advertiser.business_name',
        'advertiser.paid_for_by',
        'advertiser.country_code',
        'advertiser.follower_count',
        'advertiser.avatar_url',
        'advertiser.profile_url',
        'ad_group.targeting_info',
    ]
)

SUPPORTED_COUNTRIES = {
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
    'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'NO', 'IS', 'LI', 'PL',
    'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'GB', 'CH',
}


def _today_yyyymmdd() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%d')


def _latest_query_date() -> str:
    """TikTok rejects a published-date max of today or later."""
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y%m%d')


def _normalize_date(value: str | None, *, fallback: str) -> str:
    raw = (value or '').strip()
    if not raw:
        return fallback
    digits = re.sub(r'\D', '', raw)
    if len(digits) != 8:
        raise ValueError(f'Invalid date `{value}`. Use YYYYMMDD.')
    date(int(digits[0:4]), int(digits[4:6]), int(digits[6:8]))
    return digits


def _one_year_ago_yyyymmdd() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=365)).strftime('%Y%m%d')


def _flatten_ad(row: dict[str, Any], *, search_term: str, search_type: str) -> dict[str, Any]:
    ad = row.get('ad') or {}
    advertiser = row.get('advertiser') or {}
    reach = ad.get('reach') or {}
    videos = ad.get('videos') or []
    video_urls = []
    for item in videos:
        if isinstance(item, dict) and item.get('url'):
            video_urls.append(item['url'])
        elif isinstance(item, str):
            video_urls.append(item)

    tiktok_account = advertiser.get('tiktok_account') or {}
    targeting = (row.get('ad_group') or {}).get('targeting_info')
    business_id = advertiser.get('business_id') or advertiser.get('buisness_id')
    item = {
        'adId': None if ad.get('id') is None else str(ad.get('id')),
        'firstShownDate': ad.get('first_shown_date'),
        'lastShownDate': ad.get('last_shown_date'),
        'status': ad.get('status'),
        'statusStatement': ad.get('status_statement'),
        'videoUrls': video_urls,
        'imageUrls': ad.get('image_urls') or [],
        'reach': reach or None,
        'uniqueUsersSeen': reach.get('unique_users_seen') or reach.get('unique_user_seen'),
        'title': ad.get('title'),
        'externalUrl': ad.get('external_url'),
        'downloadUrl': ad.get('download_url'),
        'callToAction': ad.get('call_to_action'),
        'advertisingObjective': ad.get('advertising_objective'),
        'rejectionInfo': ad.get('rejection_info'),
        'advertiserCountryCode': advertiser.get('country_code'),
        'advertiserBusinessId': None if business_id is None else str(business_id),
        'advertiserBusinessName': advertiser.get('business_name'),
        'paidForBy': advertiser.get('paid_for_by') or advertiser.get('paid_by'),
        'advertiserFollowerCount': advertiser.get('follower_count') or tiktok_account.get('follower_count'),
        'advertiserAvatarUrl': advertiser.get('avatar_url') or tiktok_account.get('avatar_url'),
        'advertiserProfileUrl': advertiser.get('profile_url') or tiktok_account.get('profile_url'),
        'targetingInfo': targeting,
        'searchTerm': search_term,
        'searchType': search_type,
    }
    return {key: value for key, value in item.items() if value is not None}


async def get_client_token(client: httpx.AsyncClient, key: str, secret: str) -> str:
    response = await client.post(
        TOKEN_URL,
        data={
            'client_key': key,
            'client_secret': secret,
            'grant_type': 'client_credentials',
        },
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cache-Control': 'no-cache',
        },
    )
    payload = response.json()
    token = payload.get('access_token')
    if response.status_code >= 400 or not token:
        raise RuntimeError(
            'TikTok token request failed: '
            f'{payload.get("error_description") or payload.get("error") or response.text}'
        )
    Actor.log.info('TikTok client access token issued.')
    return str(token)


async def query_ads_page(
    client: httpx.AsyncClient,
    *,
    token: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    response = await client.post(
        QUERY_URL,
        params={'fields': QUERY_FIELDS},
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        json=body,
    )
    payload = response.json()
    error = payload.get('error') or {}
    if response.status_code >= 400 or error.get('code') not in (None, 'ok', ''):
        raise RuntimeError(
            'TikTok ad query failed: '
            f'{error.get("message") or error.get("code") or response.text}'
        )
    return payload.get('data') or {}


async def fetch_ad_detail(
    client: httpx.AsyncClient,
    *,
    token: str,
    ad_id: Any,
) -> dict[str, Any]:
    response = await client.post(
        DETAIL_URL,
        params={'fields': DETAIL_FIELDS},
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        json={'ad_id': ad_id},
    )
    payload = response.json()
    error = payload.get('error') or {}
    if response.status_code >= 400 or error.get('code') not in (None, 'ok', ''):
        Actor.log.warning(
            f'Detail fetch failed for ad {ad_id}: '
            f'{error.get("message") or error.get("code") or response.text}'
        )
        return {}
    return payload.get('data') or {}


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        search_term = str(actor_input.get('searchTerm') or '').strip()
        if not search_term:
            raise ValueError('searchTerm is required.')
        if len(search_term) > 50:
            raise ValueError('searchTerm must be 50 characters or fewer.')

        search_type = str(actor_input.get('searchType') or 'exact_phrase').strip().lower()
        if search_type not in {'exact_phrase', 'fuzzy_phrase'}:
            raise ValueError('searchType must be exact_phrase or fuzzy_phrase.')

        date_from = _normalize_date(actor_input.get('dateFrom'), fallback='')
        if not date_from:
            raise ValueError('dateFrom is required (YYYYMMDD).')
        if date_from < _one_year_ago_yyyymmdd():
            raise ValueError('dateFrom must be within the last year.')

        date_to = _normalize_date(actor_input.get('dateTo'), fallback=_latest_query_date())
        latest = _latest_query_date()
        if date_to > latest:
            Actor.log.info(
                f'Published-to {date_to} is today or later. TikTok only accepts dates through {latest}.'
            )
            date_to = latest
        if date_to < date_from:
            raise ValueError(
                f'dateTo must be on or after dateFrom, and no later than {latest}. '
                'TikTok rejects today and future dates.'
            )

        countries_raw = actor_input.get('countryCodes') or []
        countries: list[str] = []
        for code in countries_raw:
            normalized = str(code or '').strip().upper()
            if not normalized:
                continue
            if normalized not in SUPPORTED_COUNTRIES:
                raise ValueError(
                    f'Unsupported country `{normalized}`. '
                    'Commercial Content API covers EU / EEA / UK / CH only.'
                )
            countries.append(normalized)

        ad_type = str(actor_input.get('adType') or '').strip().upper()
        ad_status = str(actor_input.get('adStatus') or '').strip().upper()
        max_ads = int(actor_input.get('maxAds') or 50)
        include_details = bool(actor_input.get('includeDetails', True))

        client_key = (
            str(actor_input.get('clientKey') or '').strip()
            or os.getenv('TIKTOK_CLIENT_KEY', '').strip()
        )
        client_secret = (
            str(actor_input.get('clientSecret') or '').strip()
            or os.getenv('TIKTOK_CLIENT_SECRET', '').strip()
        )
        if not client_key or not client_secret:
            raise ValueError(
                'Missing TikTok credentials. Set Actor env TIKTOK_CLIENT_KEY and '
                'TIKTOK_CLIENT_SECRET, or pass clientKey / clientSecret for a local test.'
            )

        filters: dict[str, Any] = {
            'ad_published_date_range': {'min': date_from, 'max': date_to},
        }
        if countries:
            filters['country_code_list'] = countries
        if ad_type:
            filters['ad_type'] = ad_type
        if ad_status:
            filters['ad_status'] = ad_status

        Actor.log.info(
            f'Searching Ads Library for `{search_term}` '
            f'({search_type}) from {date_from} to {date_to}'
        )

        collected = 0
        search_id: str | None = None

        async with httpx.AsyncClient(timeout=60.0) as client:
            token = await get_client_token(client, client_key, client_secret)

            while collected < max_ads:
                page_size = min(10, max_ads - collected)
                body: dict[str, Any] = {
                    'filters': filters,
                    'search_term': search_term,
                    'search_type': search_type,
                    'max_count': page_size,
                }
                if search_id:
                    body['search_id'] = search_id

                data = await query_ads_page(client, token=token, body=body)
                ads = data.get('ads') or []
                if not ads:
                    break

                for row in ads:
                    if collected >= max_ads:
                        break
                    item = _flatten_ad(row, search_term=search_term, search_type=search_type)
                    ad_id = item.get('adId')

                    if include_details and ad_id is not None:
                        detail = await fetch_ad_detail(client, token=token, ad_id=ad_id)
                        if detail:
                            merged = {
                                'ad': {**(row.get('ad') or {}), **(detail.get('ad') or {})},
                                'advertiser': {
                                    **(row.get('advertiser') or {}),
                                    **(detail.get('advertiser') or {}),
                                },
                                'ad_group': detail.get('ad_group') or row.get('ad_group') or {},
                            }
                            item = _flatten_ad(
                                merged,
                                search_term=search_term,
                                search_type=search_type,
                            )

                    await Actor.push_data(item, charged_event_name=CHARGE_EVENT_FOUND_AD)
                    collected += 1

                if not data.get('has_more'):
                    break
                search_id = data.get('search_id')
                if not search_id:
                    break

                Actor.log.info(f'Collected {collected}/{max_ads}. Fetching next page.')

        msg = f'Done. Wrote {collected} ads for `{search_term}`.'
        Actor.log.info(msg)
        await Actor.set_status_message(msg)
