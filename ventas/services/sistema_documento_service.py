"""Generador del Documento Maestro del Sistema Aremko.

Combina:
- Narrativa cacheada (generada por LLM, regenerable desde admin).
- Inventarios técnicos live (introspectados al momento de cada descarga).

El cuerpo narrativo (resumen ejecutivo, descripciones de dominio, valor
diferenciador) se regenera explícitamente desde el botón en admin cuando hay
cambios significativos al sistema. Los inventarios técnicos siempre reflejan
el estado actual del código.

Flujo:
1. introspect_sistema() recolecta data del código (modelos, URLs, commands, etc.)
2. regenerar_narrativa(introspect) llama a Claude Sonnet con prompt editorial
   y persiste la narrativa en DocumentoSistemaCache (singleton).
3. componer_documento_md() combina narrativa cacheada + introspect live.
4. generar_pdf() renderiza el markdown a PDF tamaño Letter con WeasyPrint.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Prompt editorial — define el tono, audiencia y estilo del documento.
# Si en el futuro queremos cambiar el estilo, editar acá.
PROMPT_EDITORIAL = """\
Eres un consultor experto en sistemas empresariales que escribe documentación
formal de productos. Tu tarea: escribir secciones del documento maestro del
Sistema Aremko Spa Boutique.

AUDIENCIA: compradores potenciales (CTOs, gerentes), equipos técnicos que se
integran al sistema, agentes IA futuros que consultarán este documento como
referencia.

TONO: formal pero accesible. Cita números reales del sistema cuando los tengas.
Evita marketing vacío ("solución innovadora", "líder en su categoría").
Prefiere descripciones concretas de qué hace y cómo funciona.

ESTRUCTURA: usa markdown con encabezados ##, ###. Tablas para comparativas.
Listas con bullets concretos. Cero emojis salvo en estados (✅ ❌ ⚠️).

LONGITUD: cada sección de "dominio funcional" debe tener 200-400 palabras.
Resumen ejecutivo: 600-900 palabras. Valor diferenciador: 5-8 puntos concretos.

PROHIBIDO: inventar datos. Si no tienes información sobre algo, omítelo. No
hagas suposiciones sobre roadmap futuro a menos que esté explícito en los datos.

VOZ: español latinoamericano (tuteo: "tú", "tienes", "puedes"). Nunca voseo
argentino.
"""


def introspect_sistema() -> dict:
    """Recolecta el estado actual del sistema desde el código y la BD."""
    from django.apps import apps
    from django.urls import get_resolver

    data = {
        'timestamp': timezone.now().isoformat(),
        'modelos': _introspect_modelos(),
        'endpoints': _introspect_endpoints(),
        'management_commands': _introspect_commands(),
        'dependencies': _introspect_dependencies(),
        'git_info': _introspect_git(),
        'apps_internas': _introspect_apps(),
        'metricas': _introspect_metricas(),
        'contexto_operativo_resumen': _introspect_contexto_operativo(),
    }
    return data


def _introspect_modelos() -> list:
    """Lista todos los modelos Django de la app ventas con count de campos."""
    from django.apps import apps
    out = []
    for model in apps.get_models():
        if model._meta.app_label != 'ventas':
            continue
        out.append({
            'nombre': model.__name__,
            'tabla': model._meta.db_table,
            'verbose_name': str(model._meta.verbose_name),
            'campos_count': len(model._meta.fields),
            'doc': (model.__doc__ or '').strip().split('\n')[0][:200] if model.__doc__ else '',
        })
    return sorted(out, key=lambda x: x['nombre'])


def _introspect_endpoints() -> list:
    """Lista las URLs registradas en ventas/urls.py y otros."""
    from django.urls import get_resolver
    out = []
    resolver = get_resolver()
    _walk_urls(resolver.url_patterns, '', out)
    # Filtrar a las más relevantes (api/, admin no, sitemap no)
    relevantes = [u for u in out if (
        u['pattern'].startswith('api/')
        or '/cron/' in u['pattern']
        or u['pattern'].startswith('payment/')
        or u['pattern'].startswith('cotizacion/')
        or u['name'] in ('homepage', 'flow_confirmation', 'flow_return')
    )]
    return relevantes[:80]  # cap por tamaño


def _walk_urls(patterns, prefix, out):
    from django.urls.resolvers import URLPattern, URLResolver
    for p in patterns:
        if isinstance(p, URLResolver):
            try:
                new_prefix = prefix + str(p.pattern)
                _walk_urls(p.url_patterns, new_prefix, out)
            except Exception:
                pass
        elif isinstance(p, URLPattern):
            pat = prefix + str(p.pattern)
            out.append({
                'pattern': pat,
                'name': p.name or '',
                'callback': p.callback.__name__ if p.callback else '',
            })


def _introspect_commands() -> list:
    """Lista los management commands disponibles."""
    cmds_dir = os.path.join(settings.BASE_DIR, 'ventas', 'management', 'commands')
    if not os.path.isdir(cmds_dir):
        return []
    out = []
    for f in sorted(os.listdir(cmds_dir)):
        if not f.endswith('.py') or f.startswith('_'):
            continue
        nombre = f[:-3]
        # Categorizar para el LLM
        categoria = 'otro'
        for prefix, cat in [
            ('send_', 'comunicaciones'),
            ('snapshot_', 'analytics'),
            ('analyze_', 'analytics'),
            ('generate_', 'reporting'),
            ('cleanup_', 'mantenimiento'),
            ('report_', 'reporting'),
            ('scrape_', 'scraping'),
            ('import_', 'datos'),
            ('importar_', 'datos'),
            ('diagnose_', 'diagnostico'),
            ('diagnostico_', 'diagnostico'),
            ('diagnosticar_', 'diagnostico'),
            ('test_', 'testing'),
            ('create_', 'setup'),
            ('crear_', 'setup'),
            ('migrate_', 'migracion'),
            ('migrar_', 'migracion'),
            ('normalize_', 'datos'),
            ('normalizar_', 'datos'),
            ('check_', 'diagnostico'),
            ('fix_', 'correccion'),
            ('corregir_', 'correccion'),
            ('procesar_', 'operacion'),
            ('enviar_', 'comunicaciones'),
        ]:
            if nombre.startswith(prefix):
                categoria = cat
                break
        out.append({'nombre': nombre, 'categoria': categoria})
    return out


def _introspect_dependencies() -> list:
    """Lee requirements.txt y devuelve dependencias clave."""
    req_path = os.path.join(settings.BASE_DIR, 'requirements.txt')
    if not os.path.exists(req_path):
        return []
    deps_clave = []
    with open(req_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Solo nombre y versión, sin comentarios
            pkg = line.split('#')[0].strip()
            if pkg:
                deps_clave.append(pkg)
    return deps_clave


def _introspect_git() -> dict:
    """Hash y fecha del último commit (si git disponible)."""
    try:
        rev = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=settings.BASE_DIR, text=True, timeout=3,
        ).strip()
        msg = subprocess.check_output(
            ['git', 'log', '-1', '--pretty=%s'],
            cwd=settings.BASE_DIR, text=True, timeout=3,
        ).strip()
        fecha = subprocess.check_output(
            ['git', 'log', '-1', '--pretty=%ci'],
            cwd=settings.BASE_DIR, text=True, timeout=3,
        ).strip()
        return {'hash': rev, 'mensaje': msg, 'fecha': fecha}
    except Exception:
        return {}


def _introspect_apps() -> list:
    """Lista apps Django propias."""
    propias = ['ventas', 'control_gestion', 'api', 'destino_puerto_varas', 'kits', 'aremko_blog']
    out = []
    for nombre in propias:
        path = os.path.join(settings.BASE_DIR, nombre)
        if os.path.isdir(path):
            out.append(nombre)
    return out


def _introspect_metricas() -> dict:
    """Métricas básicas del sistema (counts, no datos sensibles)."""
    out = {}
    try:
        from ..models import (
            Cliente, VentaReserva, Servicio, Producto, GiftCard, Comanda,
            EncuestaSatisfaccion, MetaSnapshot, GA4Snapshot, CotizacionFormal,
            Campaign, SMSTemplate, EmailTemplate, PackDescuento,
        )
        out['clientes_total'] = Cliente.objects.count()
        out['ventas_reserva_total'] = VentaReserva.objects.count()
        out['servicios_activos'] = Servicio.objects.filter(publicado_web=True).count()
        out['productos_total'] = Producto.objects.count()
        out['giftcards_emitidas'] = GiftCard.objects.count()
        out['comandas_total'] = Comanda.objects.count()
        out['encuestas_total'] = EncuestaSatisfaccion.objects.count()
        out['meta_snapshots'] = MetaSnapshot.objects.count()
        out['ga4_snapshots'] = GA4Snapshot.objects.count()
        out['cotizaciones_formales'] = CotizacionFormal.objects.count()
        out['campaigns_total'] = Campaign.objects.count()
        out['sms_templates_activas'] = SMSTemplate.objects.filter(is_active=True).count()
        out['email_templates_activas'] = EmailTemplate.objects.filter(is_active=True).count()
        out['packs_descuento_activos'] = PackDescuento.objects.filter(activo=True).count()
    except Exception as exc:
        logger.warning(f'introspect_metricas error: {exc}')
        out['_error'] = str(exc)
    return out


def _introspect_contexto_operativo() -> str:
    """Trae la sección automática del ContextoOperativo (markdown)."""
    try:
        from ..contexto_operativo import generar_seccion_automatica
        return generar_seccion_automatica()
    except Exception as exc:
        logger.warning(f'introspect_contexto_operativo error: {exc}')
        return ''


# ───────────────────────── LLM: generación de narrativa ─────────────────────────

def regenerar_narrativa() -> tuple[str, dict]:
    """Llama al LLM con el introspect del sistema y produce la narrativa completa.

    Devuelve (narrativa_md, metadata) donde metadata incluye tokens y costo.
    Persiste en DocumentoSistemaCache.
    """
    from openai import OpenAI

    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    base_url = getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    if not api_key:
        raise ValueError('OPENROUTER_API_KEY no configurada en settings/env')
    logger.info(f'Sistema doc: OPENROUTER_API_KEY presente ({len(api_key)} chars)')

    model = getattr(settings, 'SISTEMA_DOC_LLM_MODEL', 'anthropic/claude-sonnet-4.6')
    max_tokens = int(getattr(settings, 'SISTEMA_DOC_LLM_MAX_TOKENS', 16000))

    logger.info('Sistema doc: introspectando sistema...')
    try:
        introspect = introspect_sistema()
    except Exception as exc:
        logger.exception(f'Sistema doc: introspect_sistema falló: {exc!r}')
        raise
    logger.info(
        f'Sistema doc: introspect OK. '
        f'{len(introspect.get("modelos", []))} modelos, '
        f'{len(introspect.get("endpoints", []))} endpoints, '
        f'{len(introspect.get("management_commands", []))} commands'
    )

    try:
        user_prompt = _construir_user_prompt(introspect)
    except Exception as exc:
        logger.exception(f'Sistema doc: _construir_user_prompt falló: {exc!r}')
        raise
    logger.info(f'Sistema doc: prompt construido ({len(user_prompt):,} chars). Llamando a {model} (timeout 300s)...')

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=300.0)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': PROMPT_EDITORIAL},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.4,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        logger.exception(f'Sistema doc: llamada al LLM falló: {exc!r}')
        raise
    logger.info('Sistema doc: LLM respondió. Procesando y persistiendo...')

    narrativa = response.choices[0].message.content or ''
    usage = response.usage
    tokens_input = getattr(usage, 'prompt_tokens', 0) if usage else 0
    tokens_output = getattr(usage, 'completion_tokens', 0) if usage else 0
    # Aproximación de costo Claude Sonnet 4.6 ($3/M input, $15/M output)
    costo = Decimal(tokens_input) * Decimal('0.000003') + Decimal(tokens_output) * Decimal('0.000015')

    # Persistir en cache singleton
    from ..models import DocumentoSistemaCache
    cache = DocumentoSistemaCache.get_solo()
    cache.narrativa_md = narrativa
    cache.actualizado_en = timezone.now()
    cache.generado_por_modelo = model
    cache.tokens_input = tokens_input
    cache.tokens_output = tokens_output
    cache.costo_usd_aprox = costo.quantize(Decimal('0.0001'))
    cache.introspect_snapshot = {
        'timestamp': introspect['timestamp'],
        'metricas': introspect['metricas'],
        'git': introspect.get('git_info', {}),
        'modelos_count': len(introspect['modelos']),
        'endpoints_count': len(introspect['endpoints']),
        'commands_count': len(introspect['management_commands']),
    }
    cache.save()

    logger.info(
        f'Sistema doc: narrativa regenerada. {tokens_input + tokens_output} tokens '
        f'(${costo:.4f} USD aprox)'
    )

    return narrativa, {
        'tokens_input': tokens_input,
        'tokens_output': tokens_output,
        'costo_usd_aprox': float(costo),
        'modelo': model,
    }


def _construir_user_prompt(introspect: dict) -> str:
    """Arma el user prompt con todo el contexto introspectado."""
    metricas = introspect.get('metricas', {})
    git = introspect.get('git_info', {})

    # Modelos agrupados por dominio (heurística por nombre)
    modelos_str = '\n'.join(
        f'- {m["nombre"]} ({m["campos_count"]} campos): {m["doc"] or m["verbose_name"]}'
        for m in introspect.get('modelos', [])[:80]
    )

    endpoints_str = '\n'.join(
        f'- {e["pattern"]} → {e["callback"]} (name={e["name"]})'
        for e in introspect.get('endpoints', [])[:50]
    )

    cmds_por_categoria = {}
    for c in introspect.get('management_commands', []):
        cmds_por_categoria.setdefault(c['categoria'], []).append(c['nombre'])
    cmds_str = '\n'.join(
        f'  - {cat} ({len(items)} comandos): {", ".join(items[:8])}{"..." if len(items) > 8 else ""}'
        for cat, items in sorted(cmds_por_categoria.items())
    )

    deps_destacadas = [d for d in introspect.get('dependencies', []) if any(
        k in d.lower() for k in [
            'django', 'psycopg', 'openai', 'weasyprint', 'sendgrid', 'requests',
            'google-', 'rest_framework', 'gunicorn', 'whitenoise', 'cloudinary',
            'celery', 'redis', 'solo', 'anymail', 'beautifulsoup', 'phonenumbers',
        ]
    )][:20]

    contexto_op = introspect.get('contexto_operativo_resumen', '')[:6000]

    return f"""Genera el cuerpo narrativo del documento maestro del Sistema Aremko.

# DATA DEL SISTEMA EN VIVO (al {introspect['timestamp']})

## Métricas reales actuales
{json.dumps(metricas, indent=2, ensure_ascii=False)}

## Versión del código
- Hash del commit: {git.get('hash', '?')}
- Último mensaje: {git.get('mensaje', '?')}
- Fecha: {git.get('fecha', '?')}

## Apps Django propias
{', '.join(introspect.get('apps_internas', []))}

## Modelos (primeros 80, agrupar mentalmente por dominio)
{modelos_str}

## Endpoints HTTP relevantes
{endpoints_str}

## Management commands por categoría
{cmds_str}

## Dependencias destacadas
{chr(10).join('- ' + d for d in deps_destacadas)}

## Contexto Operativo actual (auto-descubierto)
{contexto_op}

# TAREA

Escribe el cuerpo narrativo del documento maestro. ESTRUCTURA OBLIGATORIA:

```
# Sistema Aremko Spa Boutique — Documento Funcional y Técnico Completo

## Resumen Ejecutivo
(600-900 palabras: qué es el sistema, problema que resuelve, pilares funcionales en tabla,
stack técnico resumido, métricas reales de escala usando los counts de arriba, valor
diferenciador en 5-8 puntos concretos)

## Parte 1 — Arquitectura técnica
(Stack tecnológico, apps Django internas y sus responsabilidades, modelo de datos
agrupado por dominio, integraciones externas activas según el código. Usar tablas.)

## Parte 2 — Funcionalidades por dominio
(Para cada dominio del sistema, una sección de 200-400 palabras explicando qué hace,
cómo funciona, qué automatizaciones tiene. Dominios sugeridos según los modelos:
Reservas, Pagos, CRM/Fidelización, Comunicaciones, Marketing inteligente, Operaciones,
Cotizaciones empresariales, Gift Cards, VoC/Encuestas, Reviews, Competencia, DPV/Blog,
APIs para integradores, Contexto IA. Adapta a lo que realmente existe en los modelos.)

## Parte 3 — Automatizaciones e Inteligencia Artificial
(Cron jobs activos, signals Django, sistemas IA implementados, memoria persistente
para agentes futuros.)

## Parte 4 — Extensibilidad y futuras integraciones
(Cómo agregar nuevas funcionalidades, convenciones del proyecto, APIs disponibles
para consumidores externos.)

## Parte 5 — Información de contacto y soporte
(Equipo Aremko, proveedores tecnológicos, documentación adicional.)
```

REGLAS CRÍTICAS:
- Usa los NÚMEROS REALES de las métricas arriba (cantidad de clientes, modelos, etc.).
- NO inventes funcionalidades que no estén respaldadas por modelos o endpoints o commands listados.
- Si un dominio tiene pocos modelos en la lista, dale tratamiento más breve. Si tiene muchos, descríbelo en profundidad.
- Cita el commit hash al final del documento.
- El documento se renderizará a PDF tamaño Letter. Cuida que las tablas no sean demasiado anchas.

Genera el documento completo en markdown. Empieza directamente con `# Sistema Aremko...`, sin preámbulo.
"""


# ───────────────────────── Composición final del documento ─────────────────────────

def componer_documento_md() -> str:
    """Combina la narrativa cacheada + anexos auto-introspectados.

    Si no hay narrativa cacheada todavía, devuelve un placeholder.
    """
    from ..models import DocumentoSistemaCache
    cache = DocumentoSistemaCache.get_solo()
    introspect = introspect_sistema()

    narrativa = cache.narrativa_md.strip() if cache.narrativa_md else (
        '_(La narrativa aún no se ha generado. Usa el botón "Regenerar narrativa" '
        'en el admin para crear el cuerpo del documento.)_'
    )

    anexo = _generar_anexo_introspect(introspect, cache)
    return f'{narrativa}\n\n{anexo}'


def _generar_anexo_introspect(introspect: dict, cache) -> str:
    """Anexo final con datos técnicos siempre live."""
    lineas = []
    lineas.append('---\n')
    lineas.append('# Anexo Técnico — Inventario en Vivo\n')
    lineas.append(
        f'_(Esta sección se genera dinámicamente en cada descarga del PDF, '
        f'reflejando el estado actual del código. Snapshot tomado a las '
        f'{introspect["timestamp"]}.)_\n'
    )

    # Estado de la narrativa cacheada
    if cache.actualizado_en:
        lineas.append(f'**Narrativa principal generada:** {cache.actualizado_en.strftime("%Y-%m-%d %H:%M")} '
                      f'con modelo `{cache.generado_por_modelo}`.\n')
    else:
        lineas.append('**Narrativa principal:** no generada aún (descarga sin narrativa).\n')

    git = introspect.get('git_info', {})
    if git.get('hash'):
        lineas.append(f'**Versión del código:** commit `{git["hash"]}` — "{git.get("mensaje", "")}" ({git.get("fecha", "")})\n')

    # Métricas actuales
    metricas = introspect.get('metricas', {})
    if metricas:
        lineas.append('\n## Métricas del Sistema (live)\n')
        lineas.append('| Métrica | Valor |')
        lineas.append('|---|---|')
        nombres = {
            'clientes_total': 'Clientes registrados',
            'ventas_reserva_total': 'Total de ventas/reservas',
            'servicios_activos': 'Servicios publicados en web',
            'productos_total': 'Productos en catálogo',
            'giftcards_emitidas': 'Gift Cards emitidas',
            'comandas_total': 'Comandas registradas',
            'encuestas_total': 'Encuestas VoC recibidas',
            'meta_snapshots': 'Snapshots Meta acumulados',
            'ga4_snapshots': 'Snapshots GA4 acumulados',
            'cotizaciones_formales': 'Cotizaciones formales emitidas',
            'campaigns_total': 'Campañas creadas',
            'sms_templates_activas': 'Plantillas SMS activas',
            'email_templates_activas': 'Plantillas Email activas',
            'packs_descuento_activos': 'Packs de descuento vigentes',
        }
        for key, label in nombres.items():
            if key in metricas:
                lineas.append(f'| {label} | {metricas[key]:,} |')

    # Inventario de modelos
    modelos = introspect.get('modelos', [])
    if modelos:
        lineas.append(f'\n## Inventario de Modelos de Datos ({len(modelos)} entidades)\n')
        lineas.append('| Modelo | Verbose name | Campos |')
        lineas.append('|---|---|---|')
        for m in modelos:
            lineas.append(f'| `{m["nombre"]}` | {m["verbose_name"]} | {m["campos_count"]} |')

    # Endpoints relevantes
    endpoints = introspect.get('endpoints', [])
    if endpoints:
        lineas.append(f'\n## Endpoints HTTP Relevantes ({len(endpoints)})\n')
        for e in endpoints:
            name = f' (name=`{e["name"]}`)' if e['name'] else ''
            lineas.append(f'- `{e["pattern"]}` → `{e["callback"]}`{name}')

    # Management commands
    cmds = introspect.get('management_commands', [])
    if cmds:
        cmds_por_cat = {}
        for c in cmds:
            cmds_por_cat.setdefault(c['categoria'], []).append(c['nombre'])
        lineas.append(f'\n## Management Commands ({len(cmds)} totales, por categoría)\n')
        for cat in sorted(cmds_por_cat.keys()):
            items = cmds_por_cat[cat]
            lineas.append(f'**{cat}** ({len(items)}): {", ".join(f"`{n}`" for n in items)}')
            lineas.append('')

    # Dependencias
    deps = introspect.get('dependencies', [])
    if deps:
        lineas.append(f'\n## Dependencias Python ({len(deps)} paquetes)\n')
        for d in deps[:40]:
            lineas.append(f'- `{d}`')
        if len(deps) > 40:
            lineas.append(f'- _(... y {len(deps) - 40} más)_')

    # Contexto operativo
    contexto_op = introspect.get('contexto_operativo_resumen', '')
    if contexto_op:
        lineas.append('\n## Contexto Operativo Auto-descubierto (en vivo)\n')
        lineas.append(contexto_op)

    lineas.append(f'\n---\n')
    lineas.append(f'_Documento generado el {datetime.now().strftime("%Y-%m-%d a las %H:%M")}._\n')
    lineas.append(f'_Sistema Aremko Spa Boutique — Puerto Varas, Chile._\n')

    return '\n'.join(lineas)


# ───────────────────────── PDF ─────────────────────────

def generar_pdf() -> bytes:
    """Genera el PDF del documento maestro (narrativa cacheada + anexo live)."""
    import markdown
    from weasyprint import HTML, CSS

    md = componer_documento_md()
    html_body = markdown.markdown(md, extensions=['extra', 'tables', 'toc', 'sane_lists'])

    css_styles = '''
        @page { size: Letter; margin: 1.5cm 2cm; }
        body { font-family: Helvetica, Arial, sans-serif; line-height: 1.5; color: #2a2a2a; }
        h1 { color: #2a2a2a; border-bottom: 3px solid #b78b5b; padding-bottom: 8px; margin-top: 40px; }
        h1:first-of-type { margin-top: 0; }
        h2 { color: #2a2a2a; border-bottom: 1px solid #b78b5b; padding-bottom: 4px; margin-top: 28px; }
        h3 { color: #b78b5b; margin-top: 22px; }
        h4 { color: #555; margin-top: 18px; }
        p, li { font-size: 12px; }
        table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 11px; }
        th { background: #faf6ee; color: #b78b5b; text-align: left; padding: 6px 8px; border-bottom: 2px solid #b78b5b; }
        td { padding: 6px 8px; border-bottom: 1px solid #eee; vertical-align: top; }
        code { background: #f5f5f5; padding: 1px 4px; border-radius: 3px; font-size: 10px; }
        pre { background: #fafafa; border-left: 3px solid #b78b5b; padding: 10px; font-size: 10px; line-height: 1.4; }
        hr { border: none; border-top: 1px solid #ddd; margin: 30px 0; }
        h1, h2, h3 { page-break-after: avoid; }
        table { page-break-inside: avoid; }
    '''
    html_str = (
        f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
        f'<title>Sistema Aremko Spa Boutique</title></head><body>{html_body}</body></html>'
    )
    return HTML(string=html_str).write_pdf(stylesheets=[CSS(string=css_styles)])
