# 🔄 ESTADO DE MIGRACIONES - RESPALDO
**Fecha**: 02 de Diciembre 2024
**Total de Migraciones**: 65
**Última Migración Aplicada en Producción**: 0065_seocontent

## 📊 RESUMEN DE MIGRACIONES

### Migraciones Base (0001-0020)
- `0001_initial.py` - Estructura inicial de la base de datos
- Modelos básicos: Cliente, Proveedor, Servicio, Reserva

### Migraciones de Features (0021-0040)
- Sistema de pagos
- Gestión de inventario
- Calendario de proveedores
- Sistema de premios y puntos

### Migraciones Recientes (0041-0060)
- `0057_emailcontenttemplate_whatsapp_button.py` - Botón WhatsApp
- `0058_add_tramo_hito_to_premio.py` - Sistema de tramos
- `0059_add_tramos_validos.py` - Validación de tramos
- `0060_add_giftcard_wizard_fields.py` - Wizard de GiftCards

### Últimas Migraciones (0061-0065)
```
✅ 0061_giftcardexperiencia.py        - Sistema de experiencias GiftCard
✅ 0062_homepageconfig_text_fields.py  - Configuración de textos homepage
✅ 0063_populate_newsletter_subscriber.py - Población de suscriptores
✅ 0064_visual_campaign_system.py      - Sistema de campañas visuales
✅ 0065_seocontent.py                  - Contenido SEO (última)
```

## 🔧 COMANDOS ÚTILES

### Ver estado de migraciones
```bash
python manage.py showmigrations ventas
```

### Aplicar todas las migraciones
```bash
python manage.py migrate
```

### Aplicar migración específica
```bash
python manage.py migrate ventas 0065
```

### Revertir a migración anterior
```bash
python manage.py migrate ventas 0064
```

### Crear nueva migración
```bash
python manage.py makemigrations ventas
```

## ⚠️ MIGRACIONES CRÍTICAS

### No revertir nunca:
- `0001_initial` - Base del sistema
- `0025_*` - Sistema de pagos
- `0040_*` - Estructura de clientes

### Migraciones con datos:
- `0063_populate_newsletter_subscriber` - Contiene datos
- `0065_seocontent` - Requiere script populate_seo_content.py

## 📝 NOTAS IMPORTANTES

### Dependencias de Migraciones
- 0065 depende de 0064
- 0064 depende de 0063
- Mantener orden secuencial

### Scripts Asociados
```bash
# Después de 0065_seocontent:
python populate_seo_content.py
```

### Estado en Diferentes Ambientes
- **Producción (Render)**: Hasta 0065 ✅
- **Local/Desarrollo**: Verificar con showmigrations

## 🚨 TROUBLESHOOTING

### Error: "Migration dependencies reference nonexistent parent"
```bash
# Verificar dependencias
python manage.py showmigrations --plan

# Si hay conflicto, editar dependencies en el archivo de migración
```

### Error: "Table already exists"
```bash
# Fake la migración si ya existe
python manage.py migrate ventas 0065 --fake
```

### Error con WeasyPrint
```bash
# Desinstalar temporalmente
pip uninstall weasyprint

# Ejecutar migraciones
python manage.py migrate

# Reinstalar cuando se resuelvan dependencias
pip install weasyprint
```

## 📋 CHECKLIST PARA RESTAURACIÓN

1. ✅ Clonar repositorio
2. ✅ Instalar dependencias
3. ✅ Configurar base de datos
4. ✅ Ejecutar migraciones en orden:
   ```bash
   python manage.py migrate contenttypes
   python manage.py migrate auth
   python manage.py migrate admin
   python manage.py migrate sessions
   python manage.py migrate ventas
   ```
5. ✅ Ejecutar scripts de población:
   ```bash
   python populate_seo_content.py
   ```
6. ✅ Crear superusuario:
   ```bash
   python manage.py createsuperuser
   ```

## 🔐 RESPALDO DE MIGRACIONES

Todas las migraciones están respaldadas en:
- GitHub: `/ventas/migrations/`
- Backup local: `backups/aremko_backup_*/ventas/migrations/`

---
**IMPORTANTE**: Nunca eliminar archivos de migración en producción.
Siempre hacer backup antes de aplicar nuevas migraciones.