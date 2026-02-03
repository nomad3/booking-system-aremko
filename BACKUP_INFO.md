# Información de Backup - Sistema Aremko

## Fecha del Backup
- **Fecha**: 03 de Febrero 2026
- **Hora**: 11:24 (Chile)
- **Archivo**: `backup-aremko-20260203.tar.gz` (1.3GB)

## Contenido del Backup

### ✅ INCLUYE:
- Todo el código fuente de la aplicación
- Templates HTML
- Archivos estáticos (CSS, JS)
- Configuraciones
- Migraciones de base de datos
- Scripts de utilidad
- Documentación

### ❌ NO INCLUYE (debe respaldar por separado):
- Base de datos PostgreSQL (respaldada en Render)
- Archivos media/uploads (en Cloudinary/GCS)
- Variables de entorno (.env)
- Archivos de logs
- Caché y archivos temporales

## Cómo Restaurar

### 1. Extraer el backup:
```bash
tar -xzf backup-aremko-20260203.tar.gz
```

### 2. Instalar dependencias:
```bash
cd booking-system-aremko
pip install -r requirements.txt
```

### 3. Configurar variables de entorno:
- Copiar `.env.example` a `.env`
- Configurar las variables necesarias (DB, APIs, etc.)

### 4. Aplicar migraciones:
```bash
python manage.py migrate
```

### 5. Restaurar base de datos:
- Importar el dump de PostgreSQL desde Render

### 6. Recolectar archivos estáticos:
```bash
python manage.py collectstatic --noinput
```

## Cambios Recientes Incluidos

### Agenda Operativa:
- ✅ Filtro de productos de descuento
- ✅ Productos aparecen solo en primer servicio
- ✅ Contador de cantidades correcto
- ✅ Estado de pago con colores (verde/naranja/rojo)
- ✅ Productos inteligentes (tinas > cabañas > masajes)

### Correcciones:
- ✅ Campo `precio_base` en lugar de `precio`
- ✅ Número WhatsApp corregido: +56957902525

### Nuevas Funcionalidades:
- Sistema de doble reserva para masajes
- Herramientas de diagnóstico (`python manage.py diagnose_agenda`)
- Inventario con stock actual vs cierre anterior

## Notas Importantes

1. **GitHub**: Todo el código está respaldado en: https://github.com/nomad3/booking-system-aremko
2. **Render**: La base de datos está en producción en Render
3. **Cloudinary/GCS**: Las imágenes están en la nube

## Contacto
Para dudas sobre la restauración, contactar al equipo de desarrollo.