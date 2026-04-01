# 🌿 Luna API - Sistema de Reservas WhatsApp para Aremko Spa

## Resumen

**Luna API** permite al agente conversacional Luna crear reservas completas directamente desde WhatsApp, sin que el cliente necesite visitar la web o llamar por teléfono.

**Status:** ✅ **EN PRODUCCIÓN**
**Fecha de lanzamiento:** 31 de Marzo, 2026
**URL Base:** `https://aremko.cl/ventas/api/luna/`

---

## 🎯 Objetivo

Automatizar completamente el proceso de reservas a través de conversaciones naturales en WhatsApp, proporcionando una experiencia fluida y sin fricciones para los clientes de Aremko Spa.

---

## ✨ Características

### Para el Cliente
✅ Reserva completa por WhatsApp en minutos
✅ Verificación de disponibilidad en tiempo real
✅ Descuentos automáticos por packs
✅ Confirmación inmediata con número de reserva
✅ Sin necesidad de visitar la web o llamar

### Para Aremko
✅ Creación automática de reservas en el sistema
✅ Gestión inteligente de clientes (crear/actualizar)
✅ Prevención de duplicados con idempotencia
✅ Aplicación automática de descuentos
✅ Logging completo para auditoría
✅ Validación exhaustiva de datos

---

## 📊 Resultados de Tests

### Fase 1: Infraestructura
```
Total: 6 tests
✅ Exitosos: 6
❌ Fallidos: 0
```

### Fase 2: Validaciones
```
Total: 5 tests
✅ Exitosos: 5
❌ Fallidos: 0
```

### Fase 3: Creación de Reservas
```
Total: 4 tests
✅ Exitosos: 4
❌ Fallidos: 0
```

**🎉 15/15 tests pasando = 100% de éxito**

---

## 🚀 Endpoints Disponibles

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| GET | `/api/luna/health/` | Health check | No |
| GET | `/api/luna/test/` | Test autenticación | Sí |
| GET | `/api/luna/regiones/` | Listar regiones/comunas | Sí |
| POST | `/api/luna/reservas/validar/` | Validar disponibilidad | Sí |
| POST | `/api/luna/reservas/create/` | Crear reserva completa | Sí |

---

## 📖 Documentación

### Para Implementadores de Luna (Agente AI)
📄 **[LUNA_AGENT_PROMPT.md](./LUNA_AGENT_PROMPT.md)**
- Prompt completo para configurar el agente Luna
- Flujos de conversación detallados
- Ejemplos de interacciones cliente-agente
- Mejores prácticas para crear reservas
- Manejo de errores y casos especiales

### Para Desarrolladores (API Técnica)
📄 **[LUNA_API_DOCUMENTATION.md](./LUNA_API_DOCUMENTATION.md)**
- Especificación completa de endpoints
- Request/Response con ejemplos
- Códigos de error y troubleshooting
- Validaciones y reglas de negocio
- Ejemplos de código en Python

### Para Configuración Inicial
📄 **[LUNA_API_SETUP.md](./LUNA_API_SETUP.md)**
- Configuración en Render
- Variables de entorno
- Procedimientos de testing
- Troubleshooting común

---

## 🔐 Autenticación

```http
X-Luna-API-Key: wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms
```

Configurado en Render como variable de entorno:
```bash
LUNA_API_KEY=wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms
```

---

## 💡 Ejemplo Rápido

### 1. Validar Disponibilidad

```bash
curl -X POST https://aremko.cl/ventas/api/luna/reservas/validar/ \
  -H "X-Luna-API-Key: wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms" \
  -H "Content-Type: application/json" \
  -d '{
    "servicios": [{
      "servicio_id": 12,
      "fecha": "2026-04-15",
      "hora": "14:30",
      "cantidad_personas": 4
    }]
  }'
```

**Respuesta:**
```json
{
  "success": true,
  "disponibilidad": [{
    "servicio_nombre": "Tina Calbuco",
    "disponible": true,
    "precio_estimado": 100000.0
  }],
  "total_estimado": 100000.0,
  "descuentos_aplicables": [],
  "total_con_descuentos": 100000.0
}
```

### 2. Crear Reserva

```bash
curl -X POST https://aremko.cl/ventas/api/luna/reservas/create/ \
  -H "X-Luna-API-Key: wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "luna-conv123-1234567890",
    "cliente": {
      "nombre": "Juan Pérez",
      "email": "juan@example.com",
      "telefono": "+56987654321",
      "region_id": 14,
      "comuna_id": 318
    },
    "servicios": [{
      "servicio_id": 12,
      "fecha": "2026-04-15",
      "hora": "14:30",
      "cantidad_personas": 4
    }],
    "metodo_pago": "pendiente",
    "notas": "Reserva desde WhatsApp"
  }'
```

**Respuesta:**
```json
{
  "success": true,
  "reserva": {
    "id": 5403,
    "numero": "RES-5403",
    "total": 100000.0,
    "estado_pago": "pendiente",
    "fecha_creacion": "2026-03-31T22:07:59Z"
  },
  "mensaje": "Reserva creada exitosamente: 5403"
}
```

---

## 🎁 Descuentos Automáticos

Los descuentos se aplican **automáticamente** cuando se cumplen condiciones:

### Pack Tina + Masaje
**Descuento:** $35,000
**Condiciones:**
- Mínimo 2 personas en tina
- Mínimo 2 masajes
- Misma fecha

**Ejemplo:**
```
Tina 2 personas: $50,000
2 Masajes:       $70,000
──────────────────────────
Subtotal:       $120,000
Descuento:      -$35,000
──────────────────────────
TOTAL:           $85,000
```

---

## 🧪 Testing

### Ejecutar Tests en Render

```bash
# Fase 1: Infraestructura
python scripts/test_luna_api_phase1.py

# Fase 2: Validaciones
python scripts/test_luna_api_phase2.py

# Fase 3: Creación de Reservas
python scripts/test_luna_api_phase3.py
```

### Scripts Auxiliares

```bash
# Ver servicios activos
python scripts/check_active_services.py

# Ver regiones y comunas
python scripts/check_regions.py
```

---

## 📁 Archivos Clave

### Backend (Django)
```
ventas/views/luna_api_views.py  # Endpoints API
ventas/services/
  ├── cliente_service.py         # Gestión de clientes
  ├── pack_descuento_service.py  # Descuentos automáticos
  └── phone_service.py           # Normalización teléfonos
ventas/models.py                 # Modelos de datos
ventas/urls.py                   # Rutas API
```

### Documentación
```
LUNA_AGENT_PROMPT.md            # Prompt para agente Luna
LUNA_API_DOCUMENTATION.md       # Doc técnica API
LUNA_API_SETUP.md               # Setup inicial
LUNA_README.md                  # Este archivo
```

### Tests
```
scripts/
  ├── test_luna_api_phase1.py   # Tests infraestructura
  ├── test_luna_api_phase2.py   # Tests validaciones
  ├── test_luna_api_phase3.py   # Tests reservas
  ├── check_active_services.py  # Listar servicios
  └── check_regions.py          # Listar regiones
```

---

## 🔧 Arquitectura

### Flujo Completo

```
┌─────────────┐
│   Cliente   │ "Quiero reservar tina"
│  (WhatsApp) │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│           Agente Luna (AI)                  │
│  - Conversa naturalmente                    │
│  - Recopila datos                           │
│  - Valida disponibilidad                    │
└──────┬──────────────────────────────────────┘
       │
       │ API Request
       ▼
┌─────────────────────────────────────────────┐
│        Luna API (Django REST)               │
│  ┌───────────────────────────────────────┐  │
│  │ 1. Autenticación (API Key)            │  │
│  └───────────────────────────────────────┘  │
│  ┌───────────────────────────────────────┐  │
│  │ 2. Validar Disponibilidad             │  │
│  │    - Servicio existe y activo         │  │
│  │    - Fecha/hora válidas               │  │
│  │    - Capacidad disponible             │  │
│  │    - Sin bloqueos                     │  │
│  └───────────────────────────────────────┘  │
│  ┌───────────────────────────────────────┐  │
│  │ 3. Validar Cliente                    │  │
│  │    - Email válido                     │  │
│  │    - Teléfono normalizado             │  │
│  │    - Región/Comuna coinciden          │  │
│  └───────────────────────────────────────┘  │
│  ┌───────────────────────────────────────┐  │
│  │ 4. Crear Reserva (Transacción)        │  │
│  │    - Buscar/Crear Cliente             │  │
│  │    - Crear VentaReserva               │  │
│  │    - Crear ReservaServicio(s)         │  │
│  │    - Aplicar Descuentos               │  │
│  │    - Guardar en Cache (idempotencia)  │  │
│  └───────────────────────────────────────┘  │
└──────┬──────────────────────────────────────┘
       │
       │ JSON Response
       ▼
┌─────────────────────────────────────────────┐
│           Agente Luna                       │
│  - Recibe número de reserva                 │
│  - Informa al cliente                       │
└──────┬──────────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   Cliente   │ "Tu reserva RES-5403 confirmada"
│  (WhatsApp) │ "Total: $100,000"
└─────────────┘
```

### Modelos de Datos

```
Cliente
  └─── VentaReserva
         ├─── ReservaServicio (1..N)
         │      └─── Servicio
         └─── Pago (0..N)

Region
  └─── Comuna
```

---

## 🛡️ Seguridad

✅ HTTPS obligatorio
✅ API Key en headers (nunca en URL)
✅ Validación exhaustiva de datos
✅ Logging de intentos de acceso
✅ Transacciones atómicas
✅ Idempotencia contra duplicados
✅ Rate limiting (Render)

---

## 📈 Monitoreo

### Logs en Render

**Buscar:** `[Luna API]`

**Ejemplos:**
```
INFO [Luna API] Cliente creado: Juan Pérez (+56987654321)
INFO [Luna API] VentaReserva creada: ID 5403
INFO [Luna API] Reserva completada: Total $100000
WARNING [Luna API] Intento con API Key inválida
ERROR [Luna API] Error creando reserva: ...
```

### Métricas Clave
- Reservas creadas por día
- Tasa de éxito (%)
- Descuentos aplicados
- Errores más comunes
- Tiempo de respuesta promedio

---

## ⚠️ Troubleshooting Común

### "API Key inválida"
**Solución:** Verificar variable `LUNA_API_KEY` en Render Environment

### "Servicio no existe"
**Solución:** Ejecutar `python scripts/check_active_services.py` para ver IDs

### "Comuna no pertenece a región"
**Solución:** Ejecutar `python scripts/check_regions.py` y usar IDs correctos

### "RUT inválido"
**Solución:** Usar RUT válido o omitir (es opcional)

---

## 🗺️ Roadmap

### ✅ Completado
- [x] Infraestructura base y autenticación
- [x] Validación de disponibilidad
- [x] Creación de reservas completas
- [x] Gestión de clientes
- [x] Descuentos automáticos
- [x] Idempotencia
- [x] Tests automatizados
- [x] Documentación completa

### 🔜 Próximamente
- [ ] Consultar reservas existentes por cliente
- [ ] Cancelar reservas desde WhatsApp
- [ ] Modificar reservas existentes
- [ ] Integración con Flow.cl para pagos
- [ ] Envío automático de confirmaciones (SMS/Email)
- [ ] Recordatorios 24h antes
- [ ] Webhook para cambios de estado
- [ ] Sistema de lista de espera

---

## 📞 Contacto

### Soporte Técnico
- **GitHub:** https://github.com/nomad3/booking-system-aremko
- **Email:** dev@aremko.cl

### Aremko Spa
- **WhatsApp:** +56 9 5336 1647
- **Email:** reservas@aremko.cl
- **Web:** www.aremko.cl
- **Dirección:** Camino Volcán Calbuco Km 4, Puerto Varas

---

## 📄 Licencia

Propiedad de Aremko Spa Puerto Varas, Chile.

---

## 🙏 Créditos

**Desarrollado por:** Claude Code (Anthropic)
**Fecha:** 31 de Marzo, 2026
**Versión:** 1.0.0
**Cliente:** Aremko Spa Puerto Varas

---

## 🎉 Resultado Final

```
╔══════════════════════════════════════════════════════╗
║                                                      ║
║          🌿 LUNA API COMPLETAMENTE FUNCIONAL 🌿      ║
║                                                      ║
║  ✅ 5 Endpoints operacionales                        ║
║  ✅ 15/15 Tests pasando (100%)                       ║
║  ✅ Validaciones completas                           ║
║  ✅ Descuentos automáticos                           ║
║  ✅ Gestión de clientes                              ║
║  ✅ Idempotencia                                     ║
║  ✅ Documentación completa                           ║
║  ✅ En producción en Render                          ║
║                                                      ║
║  🚀 LISTO PARA CREAR RESERVAS DESDE WHATSAPP 🚀      ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

**¡Luna ya puede crear reservas completas desde WhatsApp! 🎊**
