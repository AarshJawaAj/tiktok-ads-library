# TikTok Ads Library Search

Search TikTok Ads Library by keyword or exact phrase through the official Commercial Content API.

You get ad IDs, creatives, reach, advertiser names, and optional detail fields (title, landing URL, targeting).

## Coverage

This library covers ads targeted in **EU / EEA / UK / Switzerland**. It is not a worldwide Ads Library dump.

## Search modes

| Match type | Use when |
|------------|----------|
| Exact phrase | You want the full phrase as typed |
| Fuzzy phrase | You want keyword-style matching (any or all words, any order) |

Search term max length: 50 characters.

## Sign-in

No TikTok user login. The Actor uses a client access token from your approved Commercial Content API app.

Set these Actor environment variables in Console:

- `TIKTOK_CLIENT_KEY`
- `TIKTOK_CLIENT_SECRET`

For a local test you can pass `clientKey` / `clientSecret` in input instead.

## Input example

```json
{
  "searchTerm": "coffee",
  "searchType": "exact_phrase",
  "dateFrom": "20260101",
  "dateTo": "20260301",
  "countryCodes": ["FR", "DE", "IT"],
  "maxAds": 50,
  "includeDetails": true
}
```

## Output fields

Each ad row includes these fields. Title, landing URL, profile, targeting, and rejection info are filled when Fetch ad details is on (the default).

| Field | TikTok source |
|-------|----------------|
| `adId` | ad.id |
| `firstShownDate` | ad.first_shown_date |
| `lastShownDate` | ad.last_shown_date |
| `status` | ad.status |
| `statusStatement` | ad.status_statement |
| `videoUrls` | ad.videos |
| `imageUrls` | ad.image_urls |
| `reach` | ad.reach |
| `uniqueUsersSeen` | ad.reach unique users |
| `title` | ad.title |
| `externalUrl` | ad.external_url |
| `downloadUrl` | ad.download_url |
| `callToAction` | ad.call_to_action |
| `advertisingObjective` | ad.advertising_objective |
| `rejectionInfo` | ad.rejection_info |
| `advertiserCountryCode` | advertiser.country_code |
| `advertiserBusinessId` | advertiser.business_id |
| `advertiserBusinessName` | advertiser.business_name |
| `paidForBy` | advertiser.paid_for_by |
| `advertiserFollowerCount` | advertiser.follower_count |
| `advertiserAvatarUrl` | advertiser.avatar_url |
| `advertiserProfileUrl` | advertiser.profile_url |
| `targetingInfo` | ad_group.targeting_info |
| `searchTerm` | your search |
| `searchType` | exact_phrase or fuzzy_phrase |

## Pricing

$3 per 1,000 ads found ($0.003 each). You pay for ads written to the dataset.

## Limits

- Date `from` must be within the last year
- TikTok returns at most 10 ads per page
- Detail mode uses one extra request per ad
- Respect TikTok Commercial Content API terms for how results may be reused

## Related

Need username existence checks with no Ads Library access? See **TikTok Username Search & Enumeration**.
