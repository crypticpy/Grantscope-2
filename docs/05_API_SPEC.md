# GrantScope2: API Specification

## Overview

RESTful API built with FastAPI. All endpoints require authentication via Supabase JWT unless marked as public.

**Base URL:** `https://{host}/api/v1`

**Authentication:** Bearer token in Authorization header

```
Authorization: Bearer {supabase_jwt}
```

---

## Cards

### List Cards (Discovery Feed)

```
GET /cards
```

Query Parameters:
| Param | Type | Description |
|-------|------|-------------|
| `pillars` | string[] | Filter by pillar codes |
| `horizons` | string[] | Filter by horizon (H1, H2, H3) |
| `min_stage` | int | Minimum stage (1-8) |
| `max_stage` | int | Maximum stage (1-8) |
| `search` | string | Full-text search query |
| `sort` | string | `updated`, `velocity`, `followers` |
| `page` | int | Page number (default: 1) |
| `limit` | int | Items per page (default: 20, max: 100) |

Response:

```json
{
  "cards": [
    {
      "id": "uuid",
      "name": "Solid State Batteries",
      "slug": "solid-state-batteries",
      "summary": "AI-generated summary...",
      "horizon": "H2",
      "stage": 4,
      "pillars": ["MC", "CH"],
      "velocity_score": 8.5,
      "follower_count": 12,
      "source_count": 47,
      "new_sources_24h": 3,
      "updated_at": "2024-12-20T15:30:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "pages": 8
}
```

### Get Card Detail

```
GET /cards/{card_id}
```

Response:

```json
{
  "id": "uuid",
  "name": "Solid State Batteries",
  "slug": "solid-state-batteries",
  "description": "Extended description...",
  "summary": "Current AI summary...",

  "classification": {
    "horizon": "H2",
    "stage": 4,
    "triage_score": 5,
    "pillars": ["MC", "CH"],
    "goals": ["MC.3", "CH.3"],
    "steep_categories": ["T", "E"],
    "anchors": ["Innovation", "Sustainability & Resiliency"],
    "top25_relevance": ["Climate Revolving Fund"]
  },

  "scoring": {
    "credibility": 4.2,
    "novelty": 4.5,
    "likelihood": 6.0,
    "impact": 4.0,
    "relevance": 4.5,
    "time_to_awareness_months": 18,
    "time_to_prepare_months": 36
  },

  "metrics": {
    "velocity_score": 8.5,
    "follower_count": 12,
    "source_count": 47
  },

  "user_context": {
    "is_following": true,
    "followed_at": "2024-11-15T10:00:00Z",
    "workstream_id": "uuid",
    "workstream_name": "Fleet Electrification"
  },

  "created_at": "2024-03-15T08:00:00Z",
  "updated_at": "2024-12-20T15:30:00Z"
}
```

### Get Card Timeline

```
GET /cards/{card_id}/timeline
```

Query Parameters:
| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | Items to return (default: 50) |
| `before` | datetime | Cursor for pagination |

Response:

```json
{
  "events": [
    {
      "id": "uuid",
      "event_type": "stage_change",
      "event_description": "Stage changed from 3 to 4",
      "previous_value": { "stage": 3 },
      "new_value": { "stage": 4 },
      "triggered_by_source": {
        "id": "uuid",
        "title": "Denver announces pilot program"
      },
      "created_at": "2024-12-15T09:00:00Z"
    }
  ],
  "has_more": true,
  "next_cursor": "2024-12-01T00:00:00Z"
}
```

### Get Card Sources

```
GET /cards/{card_id}/sources
```

Query Parameters:
| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | Items to return (default: 20) |
| `page` | int | Page number |

Response:

```json
{
  "sources": [
    {
      "id": "uuid",
      "url": "https://example.com/article",
      "title": "Toyota Announces Solid State Battery Production",
      "publication": "Reuters",
      "author": "Jane Doe",
      "published_at": "2024-12-18T14:00:00Z",
      "ai_summary": "Short summary...",
      "relevance_to_card": 0.92,
      "ingested_at": "2024-12-18T16:00:00Z"
    }
  ],
  "total": 47
}
```

### Semantic Search Cards

```
POST /cards/search
```

Request:

```json
{
  "query": "municipal drone delivery regulations",
  "limit": 10,
  "filters": {
    "pillars": ["MC"],
    "min_stage": 3
  }
}
```

Response:

```json
{
  "cards": [
    {
      "id": "uuid",
      "name": "Urban Air Mobility Regulation",
      "similarity_score": 0.89,
      ...
    }
  ],
  "query_embedding_tokens": 8
}
```

---

## Card Following

### Follow a Card

```
POST /cards/{card_id}/follow
```

Request:

```json
{
  "workstream_id": "uuid" // optional
}
```

Response:

```json
{
  "success": true,
  "followed_at": "2024-12-20T16:00:00Z"
}
```

### Unfollow a Card

```
DELETE /cards/{card_id}/follow
```

Response:

```json
{
  "success": true
}
```

### Get Followed Cards

```
GET /me/following
```

Query Parameters:
| Param | Type | Description |
|-------|------|-------------|
| `workstream_id` | uuid | Filter by workstream |
| `has_updates` | bool | Only cards with recent updates |

Response:

```json
{
  "cards": [
    {
      "id": "uuid",
      "name": "Solid State Batteries",
      "followed_at": "2024-11-15T10:00:00Z",
      "workstream_name": "Fleet Electrification",
      "updates_since_follow": 5,
      "last_update": "2024-12-20T15:30:00Z"
    }
  ]
}
```

---

## Card Notes

### Add Note to Card

```
POST /cards/{card_id}/notes
```

Request:

```json
{
  "content": "Discuss with Budget in Q2 planning",
  "is_private": false
}
```

Response:

```json
{
  "id": "uuid",
  "content": "Discuss with Budget in Q2 planning",
  "is_private": false,
  "created_at": "2024-12-20T16:00:00Z"
}
```

### Get Card Notes

```
GET /cards/{card_id}/notes
```

Response includes user's private notes and all public notes.

---

## Workstreams

### List User Workstreams

```
GET /me/workstreams
```

Response:

```json
{
  "workstreams": [
    {
      "id": "uuid",
      "name": "Fleet Electrification",
      "description": "Tracking EV and charging infrastructure trends",
      "pillars": ["MC", "CH"],
      "goals": ["MC.3", "CH.3"],
      "keywords": ["EV", "battery", "charging"],
      "card_count": 8,
      "is_default": true,
      "created_at": "2024-10-01T08:00:00Z"
    }
  ]
}
```

### Create Workstream

```
POST /me/workstreams
```

Request:

```json
{
  "name": "AI in Government Services",
  "description": "Emerging AI applications for municipal operations",
  "pillars": ["HG"],
  "goals": ["HG.2"],
  "anchors": ["Innovation"],
  "keywords": ["AI", "machine learning", "automation", "chatbot"],
  "horizons": ["H2", "H3"],
  "min_stage": 1,
  "max_stage": 5
}
```

### Update Workstream

```
PATCH /me/workstreams/{workstream_id}
```

### Delete Workstream

```
DELETE /me/workstreams/{workstream_id}
```

### Get Workstream Feed

Cards matching workstream filters.

```
GET /me/workstreams/{workstream_id}/feed
```

---

## Implications Analysis

### Start Analysis

```
POST /cards/{card_id}/analysis
```

Request:

```json
{
  "perspective": "department",
  "perspective_detail": "Austin Transportation Department"
}
```

Response:

```json
{
  "analysis_id": "uuid",
  "card_id": "uuid",
  "perspective": "department",
  "perspective_detail": "Austin Transportation Department",
  "first_orders": [
    {
      "id": "uuid",
      "content": "City commits to pilot in 25 vehicles",
      "order_level": 1
    },
    {
      "id": "uuid",
      "content": "Supply chain delays push timeline 18 months",
      "order_level": 1
    },
    {
      "id": "uuid",
      "content": "Private sector competitors accelerate adoption",
      "order_level": 1
    }
  ],
  "created_at": "2024-12-20T16:00:00Z"
}
```

### Expand Implication

Generate child implications.

```
POST /analysis/{analysis_id}/implications/{implication_id}/expand
```

Response:

```json
{
  "children": [
    {
      "id": "uuid",
      "parent_id": "uuid",
      "content": "Budget request for Q3 2027",
      "order_level": 2
    },
    {
      "id": "uuid",
      "parent_id": "uuid",
      "content": "Maintenance team requires retraining",
      "order_level": 2
    }
  ]
}
```

### Score Implication

```
PATCH /analysis/{analysis_id}/implications/{implication_id}
```

Request:

```json
{
  "likelihood_score": 7,
  "desirability_score": -4
}
```

System auto-calculates flag based on scores.

### Get Analysis Detail

```
GET /analysis/{analysis_id}
```

Full analysis tree with all implications and scores.

### List Card Analyses

```
GET /cards/{card_id}/analyses
```

---

## Research Tasks

### Submit Research Task

Trigger expanded research on a topic.

```
POST /research
```

Request:

```json
{
  "query": "AI-powered 311 systems for municipal government",
  "create_cards": true
}
```

Response:

```json
{
  "task_id": "uuid",
  "status": "queued",
  "estimated_completion": "2024-12-20T18:00:00Z"
}
```

### Get Task Status

```
GET /research/{task_id}
```

Response:

```json
{
  "task_id": "uuid",
  "status": "completed", // queued, processing, completed, failed
  "query": "AI-powered 311 systems...",
  "cards_created": [
    { "id": "uuid", "name": "AI 311 Chatbots" },
    { "id": "uuid", "name": "Predictive Service Routing" }
  ],
  "sources_processed": 24,
  "completed_at": "2024-12-20T17:45:00Z"
}
```

---

## User Profile

### Get Current User

```
GET /me
```

Response:

```json
{
  "id": "uuid",
  "email": "user@austintexas.gov",
  "display_name": "Jane Smith",
  "department": "Austin Transportation",
  "role": "Senior Planner",
  "preferences": {
    "digest_frequency": "daily",
    "notification_email": true,
    "default_pillars": ["MC", "CH"]
  }
}
```

### Update Profile

```
PATCH /me
```

---

## Reference Data

### Get Taxonomy

```
GET /taxonomy
```

Response:

```json
{
  "pillars": [
    {
      "code": "CH",
      "name": "Community Health & Sustainability",
      "goals": [
        { "code": "CH.1", "name": "Equitable public health services" },
        { "code": "CH.2", "name": "Parks, trails, recreation access" }
      ]
    }
  ],
  "anchors": [{ "name": "Equity" }, { "name": "Affordability" }],
  "steep_categories": [
    { "code": "S", "name": "Social" },
    { "code": "T", "name": "Technological" }
  ],
  "stages": [
    { "number": 1, "name": "Concept", "horizon": "H3" },
    { "number": 2, "name": "Emerging", "horizon": "H3" }
  ]
}
```

---

## Admin Endpoints

_Requires admin role_

### Trigger Nightly Scan

```
POST /admin/scan
```

### Get Scan Status

```
GET /admin/scan/status
```

### Get System Stats

```
GET /admin/stats
```

Response:

```json
{
  "total_cards": 342,
  "total_sources": 4521,
  "total_users": 38,
  "cards_last_24h": 12,
  "sources_last_24h": 87,
  "active_users_7d": 24
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Card not found",
    "details": {}
  }
}
```

Common error codes:
| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | Missing/invalid auth token |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 422 | Invalid request data |
| `RATE_LIMITED` | 429 | Too many requests |
| `SERVER_ERROR` | 500 | Internal error |

---

## Rate Limits

| Endpoint Type        | Limit      |
| -------------------- | ---------- |
| Read operations      | 100/minute |
| Write operations     | 20/minute  |
| Search/AI operations | 10/minute  |
| Research tasks       | 5/hour     |

---

_Document Version: 1.0_
_Last Updated: December 2024_
