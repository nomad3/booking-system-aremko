"""
Vista de diagnóstico para verificar el sistema de bloqueo de slots
"""
import os
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.template.loader import get_template
from django.contrib.admin.views.decorators import staff_member_required


@staff_member_required
def diagnostic_slot_template(request):
    """
    Diagnóstico del template de ServicioSlotBloqueo
    """
    diagnostics = {
        'template_path': 'admin/ventas/servicioslotbloqueo/change_form.html',
        'base_dir': str(settings.BASE_DIR),
        'template_dirs': [str(d) for d in settings.TEMPLATES[0]['DIRS']],
        'app_dirs_enabled': settings.TEMPLATES[0]['APP_DIRS'],
    }

    # Verificar si el archivo existe físicamente
    template_file_path = os.path.join(
        settings.BASE_DIR,
        'ventas',
        'templates',
        'admin',
        'ventas',
        'servicioslotbloqueo',
        'change_form.html'
    )

    diagnostics['file_exists'] = os.path.exists(template_file_path)
    diagnostics['file_path_checked'] = template_file_path

    if diagnostics['file_exists']:
        diagnostics['file_size'] = os.path.getsize(template_file_path)
        with open(template_file_path, 'r') as f:
            diagnostics['file_content_preview'] = f.read(200)

    # Intentar cargar el template con Django
    try:
        template = get_template('admin/ventas/servicioslotbloqueo/change_form.html')
        diagnostics['template_loadable'] = True
        diagnostics['template_name'] = template.template.name
    except Exception as e:
        diagnostics['template_loadable'] = False
        diagnostics['template_error'] = str(e)

    # Verificar modelo
    try:
        from ventas.models import ServicioSlotBloqueo
        diagnostics['model_imported'] = True
        diagnostics['model_fields'] = [f.name for f in ServicioSlotBloqueo._meta.fields]
    except Exception as e:
        diagnostics['model_imported'] = False
        diagnostics['model_error'] = str(e)

    # Verificar admin
    try:
        from django.contrib import admin
        from ventas.models import ServicioSlotBloqueo

        if ServicioSlotBloqueo in admin.site._registry:
            admin_class = admin.site._registry[ServicioSlotBloqueo]
            diagnostics['admin_registered'] = True
            diagnostics['admin_class'] = str(admin_class.__class__.__name__)
            diagnostics['admin_template'] = getattr(admin_class, 'change_form_template', 'Not set')
        else:
            diagnostics['admin_registered'] = False
    except Exception as e:
        diagnostics['admin_check_error'] = str(e)

    # Formato HTML legible
    html = "<html><head><title>Diagnostic: ServicioSlotBloqueo</title></head><body>"
    html += "<h1>Diagnóstico: Admin ServicioSlotBloqueo</h1>"
    html += "<pre style='background:#f5f5f5; padding:20px; border-radius:5px;'>"

    for key, value in diagnostics.items():
        html += f"\n<strong>{key}:</strong>\n{value}\n"
        html += "-" * 60 + "\n"

    html += "</pre></body></html>"

    return HttpResponse(html)
