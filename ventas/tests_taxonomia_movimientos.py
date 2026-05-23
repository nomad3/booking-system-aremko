"""
Tests para Operación Vuelta a Casa, Etapas 5.1 y 5.2.

Etapa 5.1 (este archivo): tests de detectar_cambios + taxonomia_a_dict.
Etapa 5.2: se ampliará con DetectarCelebracionesTests y
           GenerarMovimientosCelebracionesTests cuando llegue ese commit.

Ejecutar:
    python manage.py test ventas.tests_taxonomia_movimientos
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

from django.test import TestCase
from django.utils import timezone

from ventas.models import (
    Cliente,
    ClienteTaxonomia,
    ContactoWhatsApp,
    EventoCelebracion,
    ScriptWhatsApp,
    TaxonomiaMovimiento,
)
from ventas.services.taxonomia_movimientos_service import (
    CELEBRACION_TEMPLATES,
    Cambio,
    EJES,
    detectar_cambios,
    detectar_celebraciones,
    generar_mensaje_celebracion,
    generar_movimientos_y_celebraciones,
    taxonomia_a_dict,
)


# ============================================================================
# Helpers para construir snapshots en los tests
# ============================================================================

def _snap(valor='', estilo='', contexto=''):
    """Crea un dict snapshot rápido para usar en tests."""
    return {
        'eje_valor': valor,
        'eje_estilo': estilo,
        'eje_contexto': contexto,
    }


# ============================================================================
# TaxonomiaADict — normalización
# ============================================================================

class TaxonomiaADictTests(TestCase):
    def test_none_devuelve_dict_de_strings_vacios(self):
        r = taxonomia_a_dict(None)
        self.assertEqual(r, {'eje_valor': '', 'eje_estilo': '', 'eje_contexto': ''})

    def test_dict_passes_through(self):
        d = _snap('En Riesgo', 'Amante de las Tinas', 'Visitante Pareja')
        self.assertEqual(taxonomia_a_dict(d), d)

    def test_dict_con_keys_faltantes_llena_con_vacios(self):
        r = taxonomia_a_dict({'eje_valor': 'Dormido'})
        self.assertEqual(r, {'eje_valor': 'Dormido', 'eje_estilo': '', 'eje_contexto': ''})

    def test_dict_con_valores_None_los_convierte_a_vacio(self):
        r = taxonomia_a_dict({'eje_valor': None, 'eje_estilo': 'X', 'eje_contexto': None})
        self.assertEqual(r, {'eje_valor': '', 'eje_estilo': 'X', 'eje_contexto': ''})

    def test_objeto_con_atributos(self):
        obj = MagicMock()
        obj.eje_valor = 'Leal'
        obj.eje_estilo = 'Amante de las Tinas'
        obj.eje_contexto = 'Visitante Pareja'
        r = taxonomia_a_dict(obj)
        self.assertEqual(r, {
            'eje_valor': 'Leal',
            'eje_estilo': 'Amante de las Tinas',
            'eje_contexto': 'Visitante Pareja',
        })

    def test_objeto_con_atributos_None(self):
        obj = MagicMock(spec=['eje_valor', 'eje_estilo', 'eje_contexto'])
        obj.eje_valor = None
        obj.eje_estilo = 'Devoto del Masaje'
        obj.eje_contexto = None
        r = taxonomia_a_dict(obj)
        self.assertEqual(r, {
            'eje_valor': '',
            'eje_estilo': 'Devoto del Masaje',
            'eje_contexto': '',
        })


# ============================================================================
# DetectarCambios — la función pura central
# ============================================================================

class DetectarCambiosTests(TestCase):
    def test_ambos_none_no_hay_cambios(self):
        self.assertEqual(detectar_cambios(None, None), [])

    def test_mismos_valores_no_hay_cambios(self):
        antes = _snap('Regular', 'Amante de las Tinas', 'Visitante Pareja')
        despues = _snap('Regular', 'Amante de las Tinas', 'Visitante Pareja')
        self.assertEqual(detectar_cambios(antes, despues), [])

    def test_solo_eje_valor_cambia(self):
        antes = _snap('Dormido', 'Amante de las Tinas', 'Visitante Pareja')
        despues = _snap('En Prueba', 'Amante de las Tinas', 'Visitante Pareja')
        cambios = detectar_cambios(antes, despues)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0], Cambio(
            eje='valor', valor_antes='Dormido', valor_despues='En Prueba',
        ))

    def test_solo_eje_estilo_cambia(self):
        antes = _snap('Regular', 'Probador Esporádico', 'Visitante Solo')
        despues = _snap('Regular', 'Devoto del Masaje', 'Visitante Solo')
        cambios = detectar_cambios(antes, despues)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0].eje, 'estilo')
        self.assertEqual(cambios[0].valor_despues, 'Devoto del Masaje')

    def test_solo_eje_contexto_cambia(self):
        antes = _snap('Regular', 'Amante de las Tinas', 'Visitante Solo')
        despues = _snap('Regular', 'Amante de las Tinas', 'Visitante Pareja')
        cambios = detectar_cambios(antes, despues)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0].eje, 'contexto')

    def test_los_tres_ejes_cambian(self):
        antes = _snap('Dormido', 'Probador Esporádico', 'Visitante Solo')
        despues = _snap('En Prueba', 'Devoto del Masaje', 'Visitante Pareja')
        cambios = detectar_cambios(antes, despues)
        self.assertEqual(len(cambios), 3)
        # Orden estable según constante EJES
        self.assertEqual([c.eje for c in cambios], list(EJES))

    def test_taxo_anterior_None_cliente_nuevo(self):
        # Cliente recién clasificado: todos los ejes parten de ''
        despues = _snap('En Prueba', 'Probador Esporádico', 'Sin clasificar')
        cambios = detectar_cambios(None, despues)
        self.assertEqual(len(cambios), 3)
        self.assertTrue(all(c.valor_antes == '' for c in cambios))

    def test_taxo_nuevo_None_no_genera_cambios_si_anterior_tambien_vacio(self):
        # Caso edge raro: pasar de un objeto con todo '' a None debería ser []
        antes = _snap('', '', '')
        self.assertEqual(detectar_cambios(antes, None), [])

    def test_acepta_modelo_django_via_atributos(self):
        # Simula ClienteTaxonomia con MagicMock
        antes_obj = MagicMock(spec=['eje_valor', 'eje_estilo', 'eje_contexto'])
        antes_obj.eje_valor = 'Regular'
        antes_obj.eje_estilo = 'Amante de las Tinas'
        antes_obj.eje_contexto = 'Visitante Pareja'

        despues_dict = _snap('Leal', 'Amante de las Tinas', 'Visitante Pareja')

        cambios = detectar_cambios(antes_obj, despues_dict)
        self.assertEqual(len(cambios), 1)
        self.assertEqual(cambios[0].eje, 'valor')
        self.assertEqual(cambios[0].valor_antes, 'Regular')
        self.assertEqual(cambios[0].valor_despues, 'Leal')

    def test_cambio_es_hashable(self):
        # @dataclass(frozen=True) → permite usar en set
        c1 = Cambio(eje='valor', valor_antes='Dormido', valor_despues='En Prueba')
        c2 = Cambio(eje='valor', valor_antes='Dormido', valor_despues='En Prueba')
        c3 = Cambio(eje='valor', valor_antes='Dormido', valor_despues='Regular')
        s = {c1, c2, c3}
        self.assertEqual(len(s), 2)  # c1==c2

    def test_cambio_str_es_legible(self):
        c = Cambio(eje='valor', valor_antes='Dormido', valor_despues='En Prueba')
        self.assertEqual(str(c), 'valor: Dormido → En Prueba')

    def test_cambio_str_cliente_nuevo_muestra_sin_clasificar(self):
        c = Cambio(eje='valor', valor_antes='', valor_despues='En Prueba')
        self.assertEqual(str(c), 'valor: (sin clasificar) → En Prueba')


# ============================================================================
# DetectarCelebraciones — la matriz de 6 tipos
# ============================================================================

class DetectarCelebracionesTests(TestCase):
    """Pura, sin DB. Cubre cada tipo de celebración + casos combinados."""

    # ---- recuperado_dormido ----
    def test_recuperado_dormido_a_en_prueba(self):
        antes = _snap('Dormido', 'Amante de las Tinas', 'Visitante Pareja')
        despues = _snap('En Prueba', 'Amante de las Tinas', 'Visitante Pareja')
        self.assertEqual(detectar_celebraciones(antes, despues), ['recuperado_dormido'])

    def test_recuperado_dormido_a_regular(self):
        antes = _snap('Dormido', 'X', 'Y')
        despues = _snap('Regular', 'X', 'Y')
        self.assertIn('recuperado_dormido', detectar_celebraciones(antes, despues))

    def test_recuperado_dormido_a_campeon(self):
        antes = _snap('Dormido', 'X', 'Y')
        despues = _snap('Campeón', 'X', 'Y')
        self.assertIn('recuperado_dormido', detectar_celebraciones(antes, despues))

    def test_no_recuperado_si_dormido_a_en_riesgo(self):
        # En Riesgo no está en VALORES_MEJORA_DESDE_DORMIDO (peor que Dormido? No,
        # pero tampoco una "mejora celebrable" — el cliente sigue inactivo).
        antes = _snap('Dormido', 'X', 'Y')
        despues = _snap('En Riesgo', 'X', 'Y')
        self.assertNotIn('recuperado_dormido', detectar_celebraciones(antes, despues))

    # ---- consolidacion_regular ----
    def test_consolidacion_regular(self):
        antes = _snap('En Prueba', 'X', 'Y')
        despues = _snap('Regular', 'X', 'Y')
        self.assertEqual(detectar_celebraciones(antes, despues), ['consolidacion_regular'])

    def test_no_consolidacion_si_en_prueba_a_otra_cosa(self):
        antes = _snap('En Prueba', 'X', 'Y')
        despues = _snap('Leal', 'X', 'Y')
        self.assertNotIn('consolidacion_regular', detectar_celebraciones(antes, despues))

    # ---- migracion_devoto ----
    def test_migracion_devoto_a_amante_tinas(self):
        antes = _snap('Regular', 'Probador Esporádico', 'Visitante Pareja')
        despues = _snap('Regular', 'Amante de las Tinas', 'Visitante Pareja')
        self.assertEqual(detectar_celebraciones(antes, despues), ['migracion_devoto'])

    def test_migracion_devoto_a_devoto_masaje(self):
        antes = _snap('Regular', 'Probador Esporádico', 'Y')
        despues = _snap('Regular', 'Devoto del Masaje', 'Y')
        self.assertIn('migracion_devoto', detectar_celebraciones(antes, despues))

    def test_no_migracion_si_estilo_se_mantiene(self):
        antes = _snap('Regular', 'Probador Esporádico', 'Y')
        despues = _snap('Regular', 'Probador Esporádico', 'Y')
        self.assertEqual(detectar_celebraciones(antes, despues), [])

    # ---- trajo_acompanante ----
    def test_trajo_acompanante_solo_a_pareja(self):
        antes = _snap('Regular', 'X', 'Visitante Solo')
        despues = _snap('Regular', 'X', 'Visitante Pareja')
        self.assertEqual(detectar_celebraciones(antes, despues), ['trajo_acompanante'])

    def test_trajo_acompanante_solo_a_grupal(self):
        antes = _snap('Regular', 'X', 'Auto-cuidado Solo')
        despues = _snap('Regular', 'X', 'Visitante Grupal')
        self.assertIn('trajo_acompanante', detectar_celebraciones(antes, despues))

    def test_no_trajo_acompanante_si_pareja_a_pareja(self):
        antes = _snap('Regular', 'X', 'Visitante Pareja')
        despues = _snap('Regular', 'X', 'Visitante Grupal')
        # Ya venía acompañado — no es "trajo acompañante por primera vez"
        self.assertEqual(detectar_celebraciones(antes, despues), [])

    # ---- subio_a_leal ----
    def test_subio_a_leal_desde_regular(self):
        antes = _snap('Regular', 'X', 'Y')
        despues = _snap('Leal', 'X', 'Y')
        self.assertEqual(detectar_celebraciones(antes, despues), ['subio_a_leal'])

    def test_subio_a_leal_desde_gg_ocasional(self):
        antes = _snap('Gran Gastador Ocasional', 'X', 'Y')
        despues = _snap('Leal', 'X', 'Y')
        self.assertIn('subio_a_leal', detectar_celebraciones(antes, despues))

    def test_no_subio_a_leal_desde_en_prueba(self):
        # Por diseño: En Prueba → Leal no dispara (debería ser En Prueba → Regular
        # primero y luego → Leal en otra recalibración)
        antes = _snap('En Prueba', 'X', 'Y')
        despues = _snap('Leal', 'X', 'Y')
        self.assertNotIn('subio_a_leal', detectar_celebraciones(antes, despues))

    # ---- subio_a_campeon ----
    def test_subio_a_campeon(self):
        antes = _snap('Leal', 'X', 'Y')
        despues = _snap('Campeón', 'X', 'Y')
        self.assertEqual(detectar_celebraciones(antes, despues), ['subio_a_campeon'])

    def test_no_subio_a_campeon_desde_otro(self):
        antes = _snap('Regular', 'X', 'Y')
        despues = _snap('Campeón', 'X', 'Y')
        # No es "campeón desde Leal", es salto raro — no celebramos
        self.assertNotIn('subio_a_campeon', detectar_celebraciones(antes, despues))

    # ---- Múltiples celebraciones a la vez ----
    def test_multiples_celebraciones_dormido_a_leal(self):
        # Cliente que saltó muchos tramos de una: Dormido → Leal con cambio de
        # estilo Y trajo acompañante. Debe disparar las 3.
        antes = _snap('Dormido', 'Probador Esporádico', 'Visitante Solo')
        despues = _snap('Leal', 'Devoto del Masaje', 'Visitante Pareja')
        tipos = detectar_celebraciones(antes, despues)
        self.assertIn('recuperado_dormido', tipos)
        self.assertIn('migracion_devoto', tipos)
        self.assertIn('trajo_acompanante', tipos)
        # NOT subio_a_leal porque antes era Dormido, no Regular/GG Ocasional
        self.assertNotIn('subio_a_leal', tipos)

    # ---- Cliente sin clasificar (anterior None) NO genera celebraciones ----
    def test_cliente_recien_clasificado_no_celebra(self):
        # Por diseño: las celebraciones son "mejoras desde un estado conocido"
        tipos = detectar_celebraciones(None, _snap('Leal', 'Amante de las Tinas', 'Visitante Pareja'))
        self.assertEqual(tipos, [])


# ============================================================================
# GenerarMensajeCelebracion
# ============================================================================

class GenerarMensajeCelebracionTests(TestCase):
    def test_renderiza_con_nombre(self):
        msg = generar_mensaje_celebracion('recuperado_dormido', 'María González')
        self.assertIn('María', msg)
        self.assertNotIn('González', msg)  # solo primer nombre

    def test_tipo_invalido_devuelve_vacio(self):
        self.assertEqual(generar_mensaje_celebracion('not_a_real_type', 'X'), '')

    def test_nombre_vacio_usa_fallback(self):
        msg = generar_mensaje_celebracion('subio_a_leal', '')
        self.assertIn('amigo/a', msg)

    def test_todos_los_tipos_tienen_template(self):
        # Garantiza que la lista de tipos y los templates están sincronizados
        tipos_modelo = [c[0] for c in EventoCelebracion.TIPO_CHOICES]
        for tipo in tipos_modelo:
            self.assertIn(tipo, CELEBRACION_TEMPLATES,
                          f"Falta template para tipo {tipo!r}")


# ============================================================================
# GenerarMovimientosYCelebraciones — la función orquestadora con DB
# ============================================================================

class GenerarMovimientosCelebracionesTests(TestCase):
    def setUp(self):
        self.cli = Cliente.objects.create(
            nombre='María González Espinoza', telefono='+56987654321',
        )
        self.snap_dormido = _snap('Dormido', 'Amante de las Tinas', 'Visitante Pareja')
        self.snap_en_prueba = _snap('En Prueba', 'Amante de las Tinas', 'Visitante Pareja')

    def test_sin_cambios_no_crea_nada(self):
        mov, eventos = generar_movimientos_y_celebraciones(
            self.cli, self.snap_dormido, self.snap_dormido, 'recalculo_features',
        )
        self.assertIsNone(mov)
        self.assertEqual(eventos, [])
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 0)
        self.assertEqual(EventoCelebracion.objects.count(), 0)

    def test_con_cambios_crea_movimiento_unico(self):
        mov, eventos = generar_movimientos_y_celebraciones(
            self.cli, self.snap_dormido, self.snap_en_prueba, 'recalculo_features',
        )
        self.assertIsNotNone(mov)
        self.assertEqual(TaxonomiaMovimiento.objects.count(), 1)
        self.assertEqual(mov.eje_valor_antes, 'Dormido')
        self.assertEqual(mov.eje_valor_despues, 'En Prueba')
        self.assertEqual(mov.evento_origen, 'recalculo_features')

    def test_dormido_a_en_prueba_dispara_celebracion(self):
        _, eventos = generar_movimientos_y_celebraciones(
            self.cli, self.snap_dormido, self.snap_en_prueba, 'reserva',
        )
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0].tipo, 'recuperado_dormido')
        self.assertIn('María', eventos[0].mensaje_sugerido)
        self.assertEqual(eventos[0].mostrado_en_bandeja, False)

    def test_multiples_celebraciones_se_crean_todas(self):
        # Dormido + Probador + Solo → Leal + Devoto + Pareja:
        # recuperado_dormido + migracion_devoto + trajo_acompanante (no subio_a_leal)
        antes = _snap('Dormido', 'Probador Esporádico', 'Visitante Solo')
        despues = _snap('Leal', 'Devoto del Masaje', 'Visitante Pareja')

        mov, eventos = generar_movimientos_y_celebraciones(
            self.cli, antes, despues, 'reserva',
        )
        tipos = {e.tipo for e in eventos}
        self.assertEqual(tipos, {'recuperado_dormido', 'migracion_devoto', 'trajo_acompanante'})
        # Todos enlazados al MISMO movimiento
        for e in eventos:
            self.assertEqual(e.movimiento_relacionado_id, mov.id)

    def test_atribuye_contacto_whatsapp_si_existe_en_30d(self):
        # Crear script + contacto enviado hace 10 días
        script = ScriptWhatsApp.objects.create(
            script_id='X.1', nombre='Test', estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1, plantilla_texto='x',
        )
        hace_10d = timezone.now() - timedelta(days=10)
        contacto = ContactoWhatsApp.objects.create(
            cliente=self.cli, script=script,
            eje_valor_snapshot='Dormido', eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=200, salva=1, mensaje_renderizado='x',
            fecha_sugerido=hace_10d.date(), fecha_envio=hace_10d,
            estado='enviado', convirtio=False,
        )
        mov, _ = generar_movimientos_y_celebraciones(
            self.cli, self.snap_dormido, self.snap_en_prueba, 'reserva',
        )
        self.assertEqual(mov.contacto_whatsapp_atribuido_id, contacto.id)

    def test_no_atribuye_si_contacto_mas_de_30d(self):
        script = ScriptWhatsApp.objects.create(
            script_id='X.2', nombre='Old', estado_valor_target='Dormido',
            cohorte_estilo='', cohorte_contexto='', salva=1, plantilla_texto='x',
        )
        hace_45d = timezone.now() - timedelta(days=45)
        ContactoWhatsApp.objects.create(
            cliente=self.cli, script=script,
            eje_valor_snapshot='Dormido', eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=200, salva=1, mensaje_renderizado='x',
            fecha_sugerido=hace_45d.date(), fecha_envio=hace_45d,
            estado='enviado', convirtio=False,
        )
        mov, _ = generar_movimientos_y_celebraciones(
            self.cli, self.snap_dormido, self.snap_en_prueba, 'reserva',
        )
        self.assertIsNone(mov.contacto_whatsapp_atribuido)

    def test_no_atribuye_si_contacto_ya_convirtio(self):
        # Si el contacto ya tiene convirtio=True (de otra reserva atribuida antes),
        # NO debemos atribuir otra vez al mismo contacto.
        script = ScriptWhatsApp.objects.create(
            script_id='X.3', nombre='Already converted',
            estado_valor_target='Dormido', cohorte_estilo='', cohorte_contexto='',
            salva=1, plantilla_texto='x',
        )
        hace_5d = timezone.now() - timedelta(days=5)
        ContactoWhatsApp.objects.create(
            cliente=self.cli, script=script,
            eje_valor_snapshot='Dormido', eje_estilo_snapshot='', eje_contexto_snapshot='',
            dias_sin_venir_snapshot=200, salva=1, mensaje_renderizado='x',
            fecha_sugerido=hace_5d.date(), fecha_envio=hace_5d,
            estado='enviado', convirtio=True,  # ya convirtió
        )
        mov, _ = generar_movimientos_y_celebraciones(
            self.cli, self.snap_dormido, self.snap_en_prueba, 'reserva',
        )
        self.assertIsNone(mov.contacto_whatsapp_atribuido)

    def test_evento_origen_y_reserva_relacionada_se_persisten(self):
        # Crear una VentaReserva real para usar como FK
        from ventas.models import VentaReserva
        vr = VentaReserva.objects.create(cliente=self.cli, total=80000)

        mov, _ = generar_movimientos_y_celebraciones(
            self.cli, self.snap_dormido, self.snap_en_prueba,
            evento_origen='reserva',
            reserva_relacionada=vr,
        )
        self.assertEqual(mov.evento_origen, 'reserva')
        self.assertEqual(mov.reserva_relacionada_id, vr.id)

    def test_acepta_hoy_inyectado(self):
        ayer = date.today() - timedelta(days=1)
        mov, _ = generar_movimientos_y_celebraciones(
            self.cli, self.snap_dormido, self.snap_en_prueba, 'reserva', hoy=ayer,
        )
        self.assertEqual(mov.fecha, ayer)

    def test_cliente_nuevo_no_genera_celebraciones_pero_si_movimiento(self):
        # Cliente que estrena taxonomía: anterior=None
        mov, eventos = generar_movimientos_y_celebraciones(
            self.cli, None, self.snap_en_prueba, 'recalculo_features',
        )
        self.assertIsNotNone(mov)
        self.assertEqual(mov.eje_valor_antes, '')
        self.assertEqual(eventos, [])  # sin celebraciones para primera clasificación
