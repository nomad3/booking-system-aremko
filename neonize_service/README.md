# Neonize Aremko Service

Servicio Python separado que mantiene la conexión WhatsApp (via neonize) para el piloto
Destino Puerto Varas. Vive en el mismo repo que el Django de aremko.cl pero se despliega
como servicio Render independiente.

## Endpoints

- `GET /health` — público, 200 si FastAPI está arriba.
- `GET /status` — requiere `X-Auth-Token`, devuelve estado de la conexión WA.
- `GET /qr` — requiere token (header o query `?token=...`), devuelve el QR como PNG cuando
  la sesión no está autenticada. Uso: solo la primera vez o tras pérdida de sesión.
- `POST /send` — requiere `X-Auth-Token`, body `{"jid": "56912345678@s.whatsapp.net", "text": "hola"}`.

## Variables de entorno

- `NEONIZE_SERVICE_TOKEN` — secreto compartido (32 bytes hex). Generar con `openssl rand -hex 32`.
- `NEONIZE_SESSION_PATH` — ruta al archivo SQLite de sesión (default `/data/session.sqlite`).
- `NEONIZE_LOG_LEVEL` — `INFO` default.

## Operación

La primera vez que arranca sin `session.sqlite`, neonize genera un QR. Jorge lo escanea desde
el celular Aremko (WhatsApp → Dispositivos vinculados → Vincular dispositivo). Desde ahí el
archivo se persiste en el disk de Render y los restart no requieren rescaneo.

Si WhatsApp revoca el device (inactividad prolongada, desvinculación manual), hay que
rescanear el QR. El endpoint `/qr` vuelve a estar disponible automáticamente.
