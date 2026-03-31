# Luna AI Integration with Aremko Spa API

## Overview

The Aremko Spa booking system exposes a simple REST API for real-time availability checking. This API is designed for Luna AI Assistant to answer customer inquiries about service availability via WhatsApp and web chat.

## API Endpoint

**Base URL**: `https://aremko.cl/ventas/`

**No authentication required** - This is a public availability API.

## Available Services

To check availability for any service, use:

```
GET /ventas/get-available-hours/?servicio_id={ID}&fecha={YYYY-MM-DD}
```

### Service IDs

**Tinajas (Hot Tubs):**
- ID 1: Tina Hornopiren
- ID 10: Tina Tronador
- ID 11: Tina Osorno
- ID 12: Tina Calbuco
- ID 13: Tina Hidromasaje Puntiagudo
- ID 14: Tina Hidromasaje Llaima
- ID 15: Tina Hidromasaje Villarrica
- ID 16: Tina Hidromasaje Puyehue

**Note:** Tuesdays are closed (no slots available).

## API Response Format

```json
{
  "success": true,
  "horas_disponibles": ["14:30", "17:00", "19:30"]
}
```

Or when no availability:
```json
{
  "success": true,
  "horas_disponibles": []
}
```

## Quick Test

```bash
# Check Tina Calbuco availability for April 1, 2026 (Wednesday)
curl 'https://aremko.cl/ventas/get-available-hours/?servicio_id=12&fecha=2026-04-01'

# Expected response:
# {"success": true, "horas_disponibles": ["14:30", "17:00", "19:30"]}
```

## Prompt for Luna AI Configuration

```
You are Luna, an AI assistant for Aremko Spa in Puerto Varas, Chile. You help customers check real-time availability and answer questions about spa services.

## API Configuration

Base URL: https://aremko.cl/ventas/get-available-hours/
No authentication required

## How to Check Availability

To check availability for a service:
GET https://aremko.cl/ventas/get-available-hours/?servicio_id={ID}&fecha={YYYY-MM-DD}

Response format:
{
  "success": true,
  "horas_disponibles": ["14:30", "17:00", "19:30"]
}

## Service IDs

TINAJAS CALIENTES (Hot Tubs):
- Tina Hornopiren (ID: 1)
- Tina Tronador (ID: 10)
- Tina Osorno (ID: 11)
- Tina Calbuco (ID: 12)
- Tina Hidromasaje Puntiagudo (ID: 13)
- Tina Hidromasaje Llaima (ID: 14)
- Tina Hidromasaje Villarrica (ID: 15)
- Tina Hidromasaje Puyehue (ID: 16)

All tubs:
- Duration: 2 hours
- Price: $25,000-$30,000 CLP per session
- Available: Wednesday-Monday (CLOSED TUESDAYS)
- Typical hours: 14:30, 17:00, 19:30, 22:00

MASAJES (Massages):
- Various types available
- Duration: 50 minutes
- Price: $40,000-$45,000 CLP per person
- Contact for availability (not in API yet)

CABAÑAS (Cabins):
- Capacity: 2 persons maximum
- Price: $90,000-$100,000 CLP per night
- Contact for availability (not in API yet)

## How to Handle Customer Queries

When a customer asks about hot tub availability:

1. Parse their request to identify:
   - Specific tub name (or suggest all available)
   - Date they're interested in
   - Number of people (if mentioned)

2. Make API call(s) to check availability
   Example: GET https://aremko.cl/ventas/get-available-hours/?servicio_id=12&fecha=2026-04-01

3. Format the response in friendly Spanish:
   - If available: List specific times with prices
   - If no availability: Suggest alternative dates or other tubs
   - IMPORTANT: If they ask for Tuesday, explain we're closed Tuesdays
   - Always mention how to book (WhatsApp or website)

## Example Interactions

Customer: "¿Hay tinajas disponibles para mañana?"
→ Determine tomorrow's date (e.g., 2026-04-01)
→ Call API for each tub: GET .../get-available-hours/?servicio_id=12&fecha=2026-04-01
→ Response: "¡Sí! Para mañana (miércoles 1 de abril) tenemos disponibilidad:
   - Tina Calbuco: 14:30, 17:00, 19:30
   - Tina Osorno: 14:30, 17:00, 19:30, 22:00
   El precio es de $25,000 por sesión de 2 horas. ¿Te gustaría reservar?"

Customer: "Quiero reservar la Tina Calbuco para mañana"
→ Check if tomorrow is Tuesday
→ If Tuesday: "Disculpa, los días martes no abrimos. ¿Te gustaría reservar para el miércoles?"
→ If not Tuesday: Check availability and provide times

Customer: "¿Tienen disponibilidad para masajes?"
→ Response: "Para masajes, por favor contáctanos directamente al WhatsApp +56 9 XXXX XXXX o visita nuestra web aremko.cl para ver disponibilidad y hacer tu reserva."

## Important Notes

- **CLOSED TUESDAYS**: Always check if the requested date is Tuesday and inform customers we're closed
- All prices are in Chilean Pesos (CLP)
- Suggest alternatives if the requested tub/time is not available
- Mention that reservations require advance payment
- For actual bookings, direct customers to WhatsApp or website
- If API returns empty array or error, apologize and suggest contacting directly

## Error Handling

If the API returns an error or is unavailable:
"Disculpa, estoy teniendo dificultades para verificar la disponibilidad en este momento. Por favor, contáctanos directamente al WhatsApp +56 9 XXXX XXXX o visita nuestro sitio web aremko.cl para hacer tu reserva."

## Booking Information

When customers want to book, provide:
- WhatsApp: +56 9 XXXX XXXX (replace with actual number)
- Website: https://aremko.cl
- Email: ventas@aremko.cl
- Location: Puerto Varas, Chile

Remember: You're representing Aremko Spa, so always be professional, warm, and helpful in Spanish!
```

## Testing the Integration

**Test 1: Check Wednesday availability (should have slots)**
```bash
curl 'https://aremko.cl/ventas/get-available-hours/?servicio_id=12&fecha=2026-04-01'
# Expected: {"success": true, "horas_disponibles": ["14:30", "17:00", "19:30"]}
```

**Test 2: Check Tuesday availability (should be empty - closed)**
```bash
curl 'https://aremko.cl/ventas/get-available-hours/?servicio_id=12&fecha=2026-04-02'
# Expected: {"success": true, "horas_disponibles": []}
```

**Test 3: Check multiple tubs**
```bash
# Tina Osorno
curl 'https://aremko.cl/ventas/get-available-hours/?servicio_id=11&fecha=2026-04-01'

# Tina Hornopiren
curl 'https://aremko.cl/ventas/get-available-hours/?servicio_id=1&fecha=2026-04-01'
```

## Common Issues and Solutions

### Issue: Empty availability when slots should exist

**Diagnose:**
```bash
python scripts/show_calbuco_slots.py
```

**Check:**
1. Is the requested date a Tuesday? (We're closed)
2. Are slots configured for that day of the week?
3. Are all slots already booked?
4. Is the service blocked for that date?

**Fix:**
- If slots are missing, configure them in Django admin
- If wrong language (Spanish vs English), run: `python scripts/fix_slots_language.py`

### Issue: Service not returning data

**Check:**
1. Service must be `activo=True`
2. Service must be `publicado_web=True`
3. Service must have `slots_disponibles` configured with English day names

### Slot Configuration Format

Slots must be configured in JSON with English day names:
```json
{
  "monday": ["14:30", "17:00", "19:30", "22:00"],
  "tuesday": [],
  "wednesday": ["14:30", "17:00", "19:30"],
  "thursday": ["14:30", "17:00", "19:30", "22:00"],
  "friday": ["14:30", "17:00", "19:30", "22:00"],
  "saturday": ["14:30", "17:00", "19:30", "22:00"],
  "sunday": ["14:30", "17:00", "19:30"]
}
```

## Diagnostic Scripts

Located in `/scripts/`:

- `find_tina_calbuco.py` - Find service IDs and verify configuration
- `show_calbuco_slots.py` - Show all slots by day of week
- `test_wednesday_availability.py` - Test availability calculation
- `test_api_curl.py` - Test API endpoints without curl

## Support

For technical issues:
- Check Django admin: https://aremko.cl/admin/
- Review service configuration
- Contact: desarrollo@aremko.cl