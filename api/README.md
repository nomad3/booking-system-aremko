# Aremko Spa Availability API

REST API for real-time availability checking of Aremko Spa services in Puerto Varas, Chile.

## Authentication

All endpoints require API Key authentication via the `X-API-Key` header.

```bash
X-API-Key: your-api-key-here
```

## Base URL

```
https://aremko.cl/api/v1/
```

## Endpoints

### 1. Hot Tubs (Tinajas) Availability

Get available time slots for hot tubs on a specific date.

**Endpoint:** `GET /api/v1/availability/tinajas/`

**Query Parameters:**
- `date` (required): Date in YYYY-MM-DD format
- `persons` (optional): Number of persons (default: 1)

**Example Request:**
```bash
curl -X GET "https://aremko.cl/api/v1/availability/tinajas/?date=2026-04-01&persons=2" \
  -H "X-API-Key: your-api-key-here"
```

**Example Response:**
```json
{
  "date": "2026-04-01",
  "service": "tinajas",
  "available_slots": [
    {
      "tub_name": "Osorno",
      "tub_id": 3,
      "slots": ["09:00", "11:00", "14:00", "17:00", "19:00"],
      "price_per_person": 28000,
      "duration_minutes": 120
    },
    {
      "tub_name": "Llaima",
      "tub_id": 1,
      "slots": ["10:00", "13:00", "16:00"],
      "price_per_person": 30000,
      "duration_minutes": 120
    }
  ]
}
```

### 2. Massages (Masajes) Availability

Get available time slots for massages on a specific date.

**Endpoint:** `GET /api/v1/availability/masajes/`

**Query Parameters:**
- `date` (required): Date in YYYY-MM-DD format
- `type` (optional): Type of massage
  - Options: `relajacion`, `deportivo`, `piedras`, `thai`, `drenaje`, `reflexologia`

**Example Request:**
```bash
curl -X GET "https://aremko.cl/api/v1/availability/masajes/?date=2026-04-01&type=relajacion" \
  -H "X-API-Key: your-api-key-here"
```

**Example Response:**
```json
{
  "date": "2026-04-01",
  "service": "masajes",
  "available_slots": [
    {
      "type": "relajacion",
      "type_id": 10,
      "slots": ["09:00", "10:00", "11:00", "14:00", "15:00"],
      "price": 42000,
      "duration_minutes": 50
    },
    {
      "type": "deportivo",
      "type_id": 11,
      "slots": ["10:00", "15:00", "17:00"],
      "price": 45000,
      "duration_minutes": 50
    }
  ]
}
```

### 3. Cabins (Cabañas) Availability

Get available cabins for a date range.

**Endpoint:** `GET /api/v1/availability/cabanas/`

**Query Parameters:**
- `checkin` (required): Check-in date in YYYY-MM-DD format
- `checkout` (required): Check-out date in YYYY-MM-DD format
- `persons` (optional): Number of persons (default: 2)

**Example Request:**
```bash
curl -X GET "https://aremko.cl/api/v1/availability/cabanas/?checkin=2026-04-01&checkout=2026-04-03&persons=2" \
  -H "X-API-Key: your-api-key-here"
```

**Example Response:**
```json
{
  "checkin": "2026-04-01",
  "checkout": "2026-04-03",
  "service": "cabanas",
  "available_cabins": [
    {
      "cabin_id": 20,
      "cabin_name": "Cabaña Río",
      "max_persons": 2,
      "price_per_night": 95000,
      "nights": 2,
      "total_price": 190000,
      "addons_available": [
        {"name": "Desayuno", "price": 20000},
        {"name": "Tinaja privada", "price": 25000},
        {"name": "Masaje", "price": 40000}
      ]
    }
  ]
}
```

### 4. Availability Summary

Get a quick summary of all services availability for a specific date.

**Endpoint:** `GET /api/v1/availability/summary/`

**Query Parameters:**
- `date` (required): Date in YYYY-MM-DD format

**Example Request:**
```bash
curl -X GET "https://aremko.cl/api/v1/availability/summary/?date=2026-04-01" \
  -H "X-API-Key: your-api-key-here"
```

**Example Response:**
```json
{
  "date": "2026-04-01",
  "summary": {
    "tinajas": {
      "available": true,
      "slots_count": 24
    },
    "masajes": {
      "available": true,
      "slots_count": 18
    },
    "cabanas": {
      "available": true,
      "cabins_count": 2
    }
  }
}
```

## Error Responses

### 400 Bad Request
Missing or invalid parameters:
```json
{
  "error": "Date parameter is required"
}
```

### 401 Unauthorized
Invalid or missing API key:
```json
{
  "detail": "Invalid API Key"
}
```

### 404 Not Found
No availability or service category not found:
```json
{
  "error": "Hot tubs category not found"
}
```

### 500 Internal Server Error
Server error with descriptive message:
```json
{
  "error": "Internal server error message"
}
```

## Service Information

### Hot Tubs (Tinajas Calientes)
- **Duration:** 2 hours
- **Price:** $25,000 - $30,000 CLP per person
- **Available Tubs:** Llaima, Hornopiren, Puntiagudo, Calbuco, Osorno, Tronador, Villarrica, Puyehue

### Massages (Masajes)
- **Duration:** 50 minutes
- **Price:** $40,000 - $45,000 CLP per person
- **Types Available:**
  - Relajación (Relaxation)
  - Deportivo (Sports)
  - Piedras Calientes (Hot Stones)
  - Thai
  - Drenaje Linfático (Lymphatic Drainage)
  - Reflexología (Reflexology)

### Cabins (Cabañas)
- **Capacity:** 2 persons maximum
- **Price:** $90,000 - $100,000 CLP per night
- **Available Add-ons:**
  - Breakfast: $20,000 CLP
  - Private Hot Tub: $25,000 CLP
  - Massage: $40,000 CLP

### Operating Hours
- **Daily:** 9:00 AM - 9:00 PM
- **All services subject to availability**

## Rate Limiting

- API calls are limited to 100 requests per minute per API key
- Bulk queries should be cached when possible

## Notes for Luna AI Assistant

- All prices are in Chilean Pesos (CLP)
- Dates should be in YYYY-MM-DD format
- Times are in 24-hour format (HH:MM)
- Services may be blocked for maintenance or special events
- Real-time availability is subject to change
- Consider caching responses for 5 minutes to reduce API load

## Python Example

```python
import requests
from datetime import date

API_KEY = "your-api-key-here"
BASE_URL = "https://aremko.cl/api/v1"

headers = {
    "X-API-Key": API_KEY
}

# Check hot tub availability
response = requests.get(
    f"{BASE_URL}/availability/tinajas/",
    params={"date": "2026-04-01", "persons": 2},
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    for tub in data["available_slots"]:
        print(f"{tub['tub_name']}: {len(tub['slots'])} slots available")
else:
    print(f"Error: {response.status_code}")
```

## Contact

For API access or technical support, contact: desarrollo@aremko.cl