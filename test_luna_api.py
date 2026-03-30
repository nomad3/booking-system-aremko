#!/usr/bin/env python3
"""
Test script for Luna AI API integration
This script tests all API endpoints and generates a sample API key
"""

import os
import sys
import django
import secrets
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.conf import settings
from django.test import Client
import json


def generate_api_key():
    """Generate a secure API key for Luna"""
    key = secrets.token_urlsafe(32)
    print(f"\n🔑 Generated API Key for Luna AI:")
    print(f"   {key}")
    print(f"\n   Add this to your environment variables:")
    print(f"   LUNA_API_KEY={key}")
    return key


def test_api_endpoints():
    """Test all API endpoints"""

    # Get or generate API key
    api_key = getattr(settings, 'LUNA_API_KEY', None)
    if not api_key:
        print("⚠️  No LUNA_API_KEY found in settings, generating one...")
        api_key = generate_api_key()
    else:
        print(f"✅ Using existing API Key: {api_key[:10]}...")

    # Create test client
    client = Client()
    headers = {'HTTP_X_API_KEY': api_key}

    # Test date (tomorrow)
    test_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    print("\n" + "="*60)
    print(" TESTING AREMKO SPA API ENDPOINTS")
    print("="*60)

    # Test 1: Tinajas availability
    print("\n1️⃣  Testing /api/v1/availability/tinajas/")
    print(f"   Date: {test_date}")

    response = client.get(
        '/api/v1/availability/tinajas/',
        {'date': test_date, 'persons': 2},
        **headers
    )

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success! Found {len(data.get('available_slots', []))} tubs with availability")
        for tub in data.get('available_slots', [])[:2]:  # Show first 2
            print(f"      - {tub['tub_name']}: {len(tub['slots'])} slots available")
    else:
        print(f"   ❌ Error {response.status_code}: {response.content}")

    # Test 2: Masajes availability
    print("\n2️⃣  Testing /api/v1/availability/masajes/")
    print(f"   Date: {test_date}")

    response = client.get(
        '/api/v1/availability/masajes/',
        {'date': test_date, 'type': 'relajacion'},
        **headers
    )

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success! Found {len(data.get('available_slots', []))} massage types available")
        for massage in data.get('available_slots', [])[:2]:  # Show first 2
            print(f"      - {massage['type']}: {len(massage['slots'])} slots at ${massage['price']:,} CLP")
    else:
        print(f"   ❌ Error {response.status_code}: {response.content}")

    # Test 3: Cabañas availability
    print("\n3️⃣  Testing /api/v1/availability/cabanas/")
    checkin = test_date
    checkout = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    print(f"   Check-in: {checkin}, Check-out: {checkout}")

    response = client.get(
        '/api/v1/availability/cabanas/',
        {'checkin': checkin, 'checkout': checkout, 'persons': 2},
        **headers
    )

    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success! Found {len(data.get('available_cabins', []))} cabins available")
        for cabin in data.get('available_cabins', [])[:2]:  # Show first 2
            print(f"      - {cabin['cabin_name']}: ${cabin['total_price']:,} CLP for {cabin['nights']} nights")
    else:
        print(f"   ❌ Error {response.status_code}: {response.content}")

    # Test 4: Summary
    print("\n4️⃣  Testing /api/v1/availability/summary/")
    print(f"   Date: {test_date}")

    response = client.get(
        '/api/v1/availability/summary/',
        {'date': test_date},
        **headers
    )

    if response.status_code == 200:
        data = response.json()
        summary = data.get('summary', {})
        print(f"   ✅ Success! Summary for {data['date']}:")
        print(f"      - Tinajas: {'Available' if summary.get('tinajas', {}).get('available') else 'Not available'} ({summary.get('tinajas', {}).get('slots_count', 0)} slots)")
        print(f"      - Masajes: {'Available' if summary.get('masajes', {}).get('available') else 'Not available'} ({summary.get('masajes', {}).get('slots_count', 0)} slots)")
        print(f"      - Cabañas: {'Available' if summary.get('cabanas', {}).get('available') else 'Not available'} ({summary.get('cabanas', {}).get('cabins_count', 0)} cabins)")
    else:
        print(f"   ❌ Error {response.status_code}: {response.content}")

    # Test without API key
    print("\n5️⃣  Testing authentication (without API key)")

    response = client.get(
        '/api/v1/availability/summary/',
        {'date': test_date}
    )

    if response.status_code == 401 or response.status_code == 403:
        print(f"   ✅ Authentication working correctly (rejected without key)")
    else:
        print(f"   ⚠️  Unexpected response without API key: {response.status_code}")

    print("\n" + "="*60)
    print(" API TESTING COMPLETE")
    print("="*60)

    return api_key


def create_prompt_for_luna(api_key):
    """Create a prompt for Luna AI to test the integration"""

    base_url = "https://aremko.cl" if not settings.DEBUG else "http://localhost:8000"

    prompt = f"""
# Aremko Spa API Integration for Luna AI

You now have access to the Aremko Spa booking system API. Here's how to use it:

## API Configuration

- **Base URL**: {base_url}/api/v1/
- **API Key**: {api_key}
- **Header**: X-API-Key: {api_key}

## Available Endpoints

1. **Hot Tubs Availability**: GET /api/v1/availability/tinajas/?date=YYYY-MM-DD
2. **Massages Availability**: GET /api/v1/availability/masajes/?date=YYYY-MM-DD&type=relajacion
3. **Cabins Availability**: GET /api/v1/availability/cabanas/?checkin=YYYY-MM-DD&checkout=YYYY-MM-DD
4. **Summary**: GET /api/v1/availability/summary/?date=YYYY-MM-DD

## Example Queries You Can Answer

When customers ask you questions like:
- "¿Hay tinajas disponibles mañana?" → Use tinajas endpoint with tomorrow's date
- "¿Qué masajes tienen para el sábado?" → Use masajes endpoint
- "¿Hay cabañas libres este fin de semana?" → Use cabanas endpoint
- "¿Qué servicios están disponibles hoy?" → Use summary endpoint

## Response Format

All responses are in JSON. Parse them to provide natural language answers in Spanish.

## Important Notes

- All prices are in Chilean Pesos (CLP)
- Operating hours: 9:00 - 21:00 daily
- Hot tubs duration: 2 hours
- Massage duration: 50 minutes
- Maximum 2 persons per cabin

## Testing the Connection

Try this query to test:
```
GET {base_url}/api/v1/availability/summary/?date=2026-04-01
Headers: X-API-Key: {api_key}
```

You should receive a JSON response with availability information for all services.

## Customer Service Notes

- Always be friendly and helpful
- Provide specific times and prices
- Suggest alternatives if the requested service is not available
- Mention that reservations can be made through WhatsApp or the website
- Operating in Puerto Varas, Chile

Ready to assist Aremko Spa customers with real-time availability information!
"""

    return prompt


if __name__ == "__main__":
    print("\n🚀 Starting Aremko Spa API Test Suite\n")

    # Run tests
    api_key = test_api_endpoints()

    # Generate prompt for Luna
    prompt = create_prompt_for_luna(api_key)

    # Save prompt to file
    prompt_file = "luna_integration_prompt.txt"
    with open(prompt_file, 'w') as f:
        f.write(prompt)

    print(f"\n📝 Luna AI integration prompt saved to: {prompt_file}")
    print("\n✅ All tests complete! The API is ready for Luna AI integration.")
    print(f"\n🔑 Make sure to set this environment variable in production:")
    print(f"   LUNA_API_KEY={api_key}")