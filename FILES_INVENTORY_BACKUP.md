# 📂 INVENTARIO DE ARCHIVOS CRÍTICOS
**Fecha**: 02 de Diciembre 2024
**Total de Migraciones**: 65

## 🎯 ARCHIVOS ESENCIALES (No perder nunca)

### Configuración Principal
```
✅ manage.py
✅ requirements.txt
✅ requirements-snapshot-2024-12-02.txt
✅ .env (NO SUBIR A GIT)
✅ .env.backup.example
```

### Proyecto Django (aremko_project/)
```
✅ aremko_project/__init__.py
✅ aremko_project/settings.py
✅ aremko_project/urls.py
✅ aremko_project/wsgi.py
✅ aremko_project/asgi.py
```

### App Principal (ventas/)
```
✅ ventas/models.py (8000+ líneas - CRÍTICO)
✅ ventas/admin.py (configuración completa del admin)
✅ ventas/urls.py
✅ ventas/apps.py
```

### Views (ventas/views/)
```
✅ ventas/views/__init__.py
✅ ventas/views/admin_views.py
✅ ventas/views/public_views.py
✅ ventas/views/checkout_views.py
✅ ventas/views/giftcard_views.py
✅ ventas/views/api_views.py
✅ ventas/views/report_views.py
```

### Services (ventas/services/)
```
✅ ventas/services/giftcard_pdf_service.py
✅ ventas/services/communication_triggers.py
✅ ventas/services/email_service.py
✅ ventas/services/redvoiss_service.py
```

### Signals (ventas/signals/)
```
✅ ventas/signals/main_signals.py
✅ ventas/signals/giftcard_signals.py
```

### Templates Críticos (ventas/templates/)
```
✅ ventas/templates/ventas/base_public.html
✅ ventas/templates/ventas/homepage.html
✅ ventas/templates/ventas/category_detail.html
✅ ventas/templates/ventas/checkout.html
✅ ventas/templates/ventas/cart.html
✅ ventas/templates/ventas/giftcard_wizard.html
✅ ventas/templates/ventas/giftcard_menu.html
```

### Templates Admin
```
✅ ventas/templates/admin/base_site.html
✅ ventas/templates/admin/dashboard.html
✅ ventas/templates/admin/section_*.html (todos)
```

### Migraciones Importantes (ventas/migrations/)
```
✅ 0001_initial.py (inicial)
✅ 0061_giftcardexperiencia.py (sistema giftcards)
✅ 0062_homepageconfig_text_fields.py (configuración homepage)
✅ 0063_populate_newsletter_subscriber.py (newsletter)
✅ 0064_visual_campaign_system.py (campañas visuales)
✅ 0065_seocontent.py (SEO - última)
```

## 📊 ESTADÍSTICAS DE ARCHIVOS

### Totales
- **Python Files (.py)**: 110+
- **HTML Templates**: 35+
- **CSS Files**: 10+
- **JavaScript Files**: 15+
- **Migration Files**: 65
- **Static Files**: 25+

### Tamaños Aproximados
- **models.py**: ~300 KB
- **admin.py**: ~150 KB
- **Total proyecto**: ~5 MB (sin media files)

## 🔒 ARCHIVOS SENSIBLES (No incluir en backups públicos)

```
❌ .env
❌ *.sqlite3
❌ credentials.json
❌ serviceAccountKey.json
❌ __pycache__/
❌ *.pyc
❌ media/
❌ staticfiles/
```

## 📦 DIRECTORIOS COMPLETOS A RESPALDAR

```bash
# Estructura de directorios críticos
booking-system-aremko/
├── aremko_project/       # Configuración Django
├── ventas/              # App principal
│   ├── migrations/      # 65 archivos de migración
│   ├── templates/       # Todas las plantillas
│   ├── static/         # Archivos estáticos
│   ├── views/          # Todas las vistas
│   ├── services/       # Servicios
│   └── signals/        # Señales
├── scripts/            # Scripts útiles
├── static/            # Estáticos globales
└── templates/         # Templates globales
```

## 🔄 ARCHIVOS AGREGADOS RECIENTEMENTE

### Últimos 7 días
```
✅ ventas/models.py (SEOContent agregado)
✅ ventas/migrations/0065_seocontent.py
✅ populate_seo_content.py
✅ SEO_IMPLEMENTATION_GUIDE.md
✅ BACKUP_INFO_2024.md
✅ .env.backup.example
✅ requirements-snapshot-2024-12-02.txt
✅ scripts/run_migrations.sh
```

## 🛠️ SCRIPTS DE UTILIDAD

```
✅ populate_seo_content.py - Poblar datos SEO
✅ scripts/run_migrations.sh - Ejecutar migraciones
✅ manage.py - Gestión Django
```

## 📝 DOCUMENTACIÓN

```
✅ README.md
✅ SEO_IMPLEMENTATION_GUIDE.md
✅ BACKUP_INFO_2024.md
✅ FILES_INVENTORY_BACKUP.md (este archivo)
```

---
**NOTA**: Este inventario debe actualizarse cada vez que se agreguen archivos críticos al proyecto.