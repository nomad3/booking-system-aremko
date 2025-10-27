# Phone Normalization Solution

## Problem

The system had duplicate client records with the same phone number in different formats:
- Client A: `+56975544661`
- Client B: `56975544661`

### Root Cause
- The `Cliente` model had `unique=True` on the telefono field
- However, `"+56975544661"` and `"56975544661"` are treated as different strings by the database
- No normalization was applied before saving, allowing duplicates to exist
- CRM search would find both variants, confusing users

## Solution

### 1. Model-Level Phone Normalization

**File**: `ventas/models.py`

Added phone normalization to the `Cliente` model:

```python
@staticmethod
def normalize_phone(phone_str):
    """
    Normaliza número de teléfono a formato estándar sin '+'
    Para Chile: 56XXXXXXXXX (11-12 dígitos)
    """
    # Removes all non-numeric characters (including +)
    # Adds country code 56 for Chilean numbers if needed
    # Returns normalized format: 56XXXXXXXXX

def save(self, *args, **kwargs):
    """
    Override save para normalizar teléfono antes de guardar
    """
    if self.telefono:
        normalized = self.normalize_phone(self.telefono)
        if normalized:
            self.telefono = normalized
        else:
            raise ValidationError(f"Formato de teléfono inválido")
    super().save(*args, **kwargs)
```

**Benefits**:
- All new clients will have normalized phone numbers
- Prevents future duplicates from being created
- Validates phone format on save

### 2. Management Command to Fix Existing Data

**File**: `ventas/management/commands/normalize_client_phones.py`

Created management command with two functions:
1. **Normalize all existing phone numbers**
2. **Merge duplicate clients** (optional)

#### Usage

**Dry-run (preview changes without applying them)**:
```bash
python manage.py normalize_client_phones --dry-run
```

**Normalize phones only**:
```bash
python manage.py normalize_client_phones
```

**Normalize AND merge duplicates**:
```bash
python manage.py normalize_client_phones --merge-duplicates
```

**Dry-run with merge preview**:
```bash
python manage.py normalize_client_phones --dry-run --merge-duplicates
```

#### What the Command Does

**Phase 1: Normalize Phones**
- Scans all Cliente records
- Normalizes telefono field using `Cliente.normalize_phone()`
- Updates database directly (bypassing save() to avoid constraint errors)
- Shows progress and changes made

**Phase 2: Merge Duplicates** (if --merge-duplicates flag is used)
- Identifies clients with identical normalized phone numbers
- Keeps the oldest client (based on created_at)
- Merges data from duplicates:
  - Moves all VentaReserva records to the principal client
  - Moves all ServiceHistory records to the principal client
  - Copies missing data (email, ciudad, pais) if principal doesn't have it
  - Deletes the duplicate client records

### 3. Improved CRM Search

**File**: `ventas/services/crm_service.py`

Updated `buscar_clientes()` method to normalize search queries:

```python
# If the query looks like a phone, normalize it
normalized_phone = Cliente.normalize_phone(query)

# Search by both original and normalized format
q_filter = (
    Q(nombre__icontains=query) |
    Q(email__icontains=query) |
    Q(telefono__icontains=query)
)

if normalized_phone and normalized_phone != query:
    q_filter |= Q(telefono__icontains=normalized_phone)

clientes = Cliente.objects.filter(q_filter).distinct()
```

**Benefits**:
- Searching for `"+56975544661"` will find clients with `"56975544661"`
- Searching for `"975544661"` will normalize to `"56975544661"` and find matches
- More intuitive search experience

### 4. Database Migration

**File**: `ventas/migrations/0056_cliente_created_at.py`

Added `created_at` field to Cliente model:
- Used by merge command to determine which duplicate to keep (oldest = principal)
- Nullable and blank to handle existing records

## Deployment Steps

1. **Apply migration** (adds created_at field):
   ```bash
   python manage.py migrate
   ```

2. **Preview changes** (recommended first):
   ```bash
   python manage.py normalize_client_phones --dry-run --merge-duplicates
   ```

3. **Normalize phones**:
   ```bash
   python manage.py normalize_client_phones
   ```

4. **Check for duplicates**:
   ```bash
   python manage.py normalize_client_phones --dry-run --merge-duplicates
   ```

5. **Merge duplicates** (if any found):
   ```bash
   python manage.py normalize_client_phones --merge-duplicates
   ```

## Standard Phone Format

**Chile (country code 56)**:
- Mobile: `56XXXXXXXXX` (11 digits)
  - Example: `56975544661`
- Landline Santiago: `562XXXXXXXX` (12 digits)
  - Example: `56222334455`

**Other countries**:
- Minimum 8 digits, no symbols
- Country code should be included if available

## Prevention

With this solution:
- ✅ All new clients will have normalized phones automatically
- ✅ Duplicate prevention via save() override
- ✅ Search works with any phone format
- ✅ Existing duplicates can be identified and merged
- ✅ Data quality improves over time

## Example Scenario

**Before**:
- Search "56975544661" → Returns 2 clients:
  - "Marjorie Melo Valenzuela" (+56975544661)
  - "Mark Burkar" (56975544661)

**After normalization**:
- Both phones normalized to `56975544661`
- Merge command identifies them as duplicates
- Keeps oldest client, merges data from newer one
- Search "56975544661" → Returns 1 client with complete history

## Testing

Test the normalization function:
```python
from ventas.models import Cliente

# Chilean mobile (9 digits)
Cliente.normalize_phone("975544661")  # → "56975544661"

# Chilean mobile with spaces
Cliente.normalize_phone("9 7554 4661")  # → "56975544661"

# With country code
Cliente.normalize_phone("56975544661")  # → "56975544661"

# With + prefix
Cliente.normalize_phone("+56975544661")  # → "56975544661"

# Chilean landline
Cliente.normalize_phone("22334455")  # → "56222334455"
```
