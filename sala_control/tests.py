# -*- coding: utf-8 -*-
"""Pruebas de la sala de control.

Lo que se cuida acá son los umbrales y el silencio. Una alerta que se
dispara cuando no corresponde enseña a ignorar el correo, y entonces el día
que la alerta sea real tampoco se va a leer. Por eso hay tantas pruebas de
«esto NO debe alertar» como de «esto sí».

El otro cuidado es no inventar números: cuando falta un dato, el resultado
tiene que ser None y no un cero — un cero se lee como un hecho.
"""
from datetime import date, timedelta

from django.test import SimpleTestCase, TestCase

from sala_control import alertas, render
from sala_control.resumen import variacion


def _cuenta(nombre, rezago, ultima=date(2026, 8, 16)):
    return {'clave': 'x', 'nombre': nombre, 'saldo': 1,
            'ultima_cartola': ultima, 'dias_rezago': rezago}


class CajaBaja(SimpleTestCase):
    def test_bajo_el_umbral_alerta(self):
        a = alertas.alerta_caja_baja(9_000_000, 15_000_000)
        self.assertIsNotNone(a)
        self.assertEqual(a['nivel'], alertas.ALTA)
        self.assertIn('6.000.000', a['texto'])   # lo que falta

    def test_justo_en_el_umbral_no_alerta(self):
        self.assertIsNone(alertas.alerta_caja_baja(15_000_000, 15_000_000))

    def test_sobre_el_umbral_no_alerta(self):
        self.assertIsNone(alertas.alerta_caja_baja(20_000_000, 15_000_000))

    def test_sin_caja_verificable_no_alerta(self):
        """Falta un ancla de saldo: no sabemos cuánto hay.

        Alertar acá sería una alarma falsa por un dato faltante, que es la
        forma más rápida de que se dejen de mirar las alarmas.
        """
        self.assertIsNone(alertas.alerta_caja_baja(None, 15_000_000))


class CartolasAtrasadas(SimpleTestCase):
    def test_al_dia_no_alerta(self):
        self.assertEqual(alertas.alertas_cartola_atrasada(
            [_cuenta('BancoEstado', 2)]), [])

    def test_en_el_tope_no_alerta(self):
        self.assertEqual(alertas.alertas_cartola_atrasada(
            [_cuenta('BancoEstado', 7)]), [])

    def test_pasado_el_tope_alerta(self):
        a = alertas.alertas_cartola_atrasada([_cuenta('BancoEstado', 12)])
        self.assertEqual(len(a), 1)
        self.assertIn('12 días', a[0]['texto'])

    def test_nunca_cargada_es_alta(self):
        a = alertas.alertas_cartola_atrasada([_cuenta('Scotiabank', 9999)])
        self.assertEqual(a[0]['nivel'], alertas.ALTA)
        self.assertIn('nunca', a[0]['texto'])

    def test_cuentas_sin_cartola_se_ignoran(self):
        """Mercado Pago y efectivo no se alimentan de cartola: un día sin
        movimientos no es un vacío de información."""
        self.assertEqual(alertas.alertas_cartola_atrasada(
            [{'nombre': 'Mercado Pago', 'dias_rezago': None,
              'ultima_cartola': None}]), [])


class PublicacionesPendientes(SimpleTestCase):
    def test_todas_publicadas_no_alerta(self):
        self.assertIsNone(alertas.alerta_publicaciones_pendientes(
            [{'estado': 'publicada'}, {'estado': 'publicada'}]))

    def test_dia_sin_publicaciones_no_alerta(self):
        self.assertIsNone(alertas.alerta_publicaciones_pendientes([]))

    def test_pendiente_alerta_con_detalle(self):
        a = alertas.alerta_publicaciones_pendientes([
            {'estado': 'publicada', 'hora': '09:00', 'canal': 'IG'},
            {'estado': 'pendiente', 'hora': '19:00', 'canal': 'IG Stories'},
        ])
        self.assertIn('1 publicación', a['texto'])
        self.assertIn('19:00', a['texto'])


class VentasEnBaja(SimpleTestCase):
    def _comp(self, pct):
        return {'totales': {'facturado_pct_cambio': pct}}

    def test_caida_fuerte_alerta(self):
        a = alertas.alerta_ventas_en_baja(self._comp(-30), dia_del_mes=15)
        self.assertIsNotNone(a)
        self.assertEqual(a['nivel'], alertas.ALTA)

    def test_caida_leve_no_alerta(self):
        self.assertIsNone(
            alertas.alerta_ventas_en_baja(self._comp(-5), dia_del_mes=15))

    def test_temprano_en_el_mes_no_alerta(self):
        """El día 3 dos jornadas flojas mueven el porcentaje entero: sería
        una moneda al aire, no una señal."""
        self.assertIsNone(
            alertas.alerta_ventas_en_baja(self._comp(-40), dia_del_mes=3))

    def test_texto_no_numerico_no_alerta(self):
        """La comparativa devuelve 'NUEVO' o 'sin movimiento' cuando no hay
        base: no es un porcentaje y no se puede comparar contra el umbral."""
        self.assertIsNone(
            alertas.alerta_ventas_en_baja(self._comp('NUEVO'), dia_del_mes=20))

    def test_sin_comparativa_no_alerta(self):
        self.assertIsNone(alertas.alerta_ventas_en_baja(None, dia_del_mes=20))


class CampanasSinResultado(SimpleTestCase):
    def test_gasto_sin_resultados_alerta(self):
        a = alertas.alertas_campanas_sin_resultado([
            {'plataforma': 'Meta', 'nombre': 'Pausa', 'gasto': 90_000,
             'resultados': 0, 'unidad': 'conversaciones', 'dias': 22}])
        self.assertEqual(len(a), 1)
        self.assertIn('conversaciones', a[0]['texto'])

    def test_con_resultados_no_alerta(self):
        self.assertEqual(alertas.alertas_campanas_sin_resultado([
            {'gasto': 90_000, 'resultados': 4}]), [])

    def test_gasto_chico_no_alerta(self):
        self.assertEqual(alertas.alertas_campanas_sin_resultado([
            {'gasto': 900, 'resultados': 0}]), [])

    def test_resultado_no_medible_se_omite(self):
        """Google marca 0 conversiones porque el lead de WhatsApp no está
        importado como conversión — no porque la campaña no funcione.
        Alertar ahí llevaría a apagar campañas que están vendiendo."""
        self.assertEqual(alertas.alertas_campanas_sin_resultado([
            {'plataforma': 'Google', 'nombre': 'Ritual', 'gasto': 200_000,
             'resultados': None}]), [])


class ListaDeAlertas(SimpleTestCase):
    def _sano(self, **cambios):
        base = dict(caja_total=30_000_000, umbral_caja=15_000_000,
                    cuentas=[_cuenta('BancoEstado', 1)],
                    publicaciones=[{'estado': 'publicada'}],
                    comparativa={'totales': {'facturado_pct_cambio': 8}},
                    dia_del_mes=20, campanas=[])
        base.update(cambios)
        return base

    def test_todo_en_rango_lista_vacia(self):
        """El caso que hace creíble a la lista cuando NO está vacía."""
        self.assertEqual(alertas.construir_alertas(**self._sano()), [])

    def test_las_graves_van_primero(self):
        lista = alertas.construir_alertas(**self._sano(
            caja_total=1_000_000,                       # alta
            publicaciones=[{'estado': 'pendiente'}]))   # media
        self.assertEqual(len(lista), 2)
        self.assertEqual(lista[0]['nivel'], alertas.ALTA)


class Formato(SimpleTestCase):
    def test_montos_en_pesos_chilenos(self):
        self.assertEqual(render.clp(18_400_000), '$18.400.000')
        self.assertEqual(render.clp(None), '—')

    def test_compacto(self):
        self.assertEqual(render.compacto(18_400_000), '$18,4M')
        self.assertEqual(render.compacto(592_000), '$592k')

    def test_variacion_sin_base_es_none(self):
        """Si el mes anterior fue cero, el cambio no es 0% — no hay base."""
        self.assertIsNone(variacion(100, 0))
        self.assertIsNone(variacion(100, None))
        self.assertAlmostEqual(variacion(110, 100), 10.0)

    def test_pct_usa_menos_tipografico(self):
        self.assertIn('▼', render.pct(-3))
        self.assertIn('▲', render.pct(9))
        self.assertEqual(render.pct(None), '—')


class ResultadoSegunObjetivo(SimpleTestCase):
    """Medir una campaña con la métrica de otro objetivo da un veredicto
    equivocado: las de Ritual y Pausa son de MENSAJES."""

    def _leer(self, objetivo, acciones):
        from ventas.services.meta_reporter import extraer_resultado_por_objetivo
        return extraer_resultado_por_objetivo(objetivo, acciones)

    def test_mensajes_cuenta_conversaciones(self):
        unidad, n = self._leer('MESSAGES', [
            {'action_type': 'link_click', 'value': '80'},
            {'action_type':
             'onsite_conversion.messaging_conversation_started_7d',
             'value': '7'}])
        self.assertEqual((unidad, n), ('conversaciones', 7))

    def test_leads_no_se_duplican(self):
        """Meta reporta el mismo lead por Pixel y por CAPI: se toma el máximo,
        no la suma."""
        unidad, n = self._leer('OUTCOME_LEADS', [
            {'action_type': 'lead', 'value': '5'},
            {'action_type': 'offsite_conversion.fb_pixel_lead', 'value': '5'}])
        self.assertEqual((unidad, n), ('leads', 5))

    def test_engagement_ambiguo_sin_conversaciones_no_se_mide(self):
        self.assertEqual(
            self._leer('OUTCOME_ENGAGEMENT',
                       [{'action_type': 'post_engagement', 'value': '40'}]),
            (None, None))

    def test_engagement_con_conversaciones_si_se_mide(self):
        unidad, n = self._leer('OUTCOME_ENGAGEMENT', [
            {'action_type':
             'onsite_conversion.messaging_conversation_started_7d',
             'value': '3'}])
        self.assertEqual((unidad, n), ('conversaciones', 3))

    def test_objetivo_desconocido_no_se_mide(self):
        self.assertEqual(self._leer('ALGO_NUEVO', [
            {'action_type': 'link_click', 'value': '9'}]), (None, None))

    def test_sin_acciones_no_inventa_cero(self):
        self.assertEqual(self._leer('MESSAGES', []), (None, None))


class Colchon(SimpleTestCase):
    def test_dias_de_aire(self):
        from finanzas.services import colchon_dias
        self.assertEqual(colchon_dias(3_000_000, 100_000), 30)

    def test_sin_gastos_no_hay_colchon(self):
        from finanzas.services import colchon_dias
        self.assertIsNone(colchon_dias(3_000_000, 0))

    def test_sin_caja_verificable_no_hay_colchon(self):
        from finanzas.services import colchon_dias
        self.assertIsNone(colchon_dias(None, 100_000))


class PrioridadesDeLaSemana(TestCase):
    def test_solo_las_de_la_semana_pedida(self):
        from sala_control.fuentes import lunes_de, prioridades
        from sala_control.models import PrioridadSemana

        lunes = date(2026, 8, 17)
        PrioridadSemana.objects.create(semana_inicio=lunes, orden=1,
                                       texto='Revisar la carta')
        PrioridadSemana.objects.create(semana_inicio=lunes - timedelta(days=7),
                                       orden=1, texto='De la semana pasada')
        self.assertEqual([p.texto for p in prioridades(lunes)],
                         ['Revisar la carta'])
        self.assertEqual(lunes_de(date(2026, 8, 19)), lunes)


class DiaDeLaPresenciaWeb(SimpleTestCase):
    """Las fotos de Analytics y Search Console se toman el lunes, DESPUÉS de
    que este correo ya salió. Por eso el bloque va los martes: mostrarlo el
    lunes sería enseñar la foto de la semana pasada con cara de recién tomada.
    """

    def test_el_dia_elegido_es_martes(self):
        from sala_control.resumen import DIA_PRESENCIA_WEB
        self.assertEqual(DIA_PRESENCIA_WEB, 1)
        self.assertEqual(date(2026, 8, 25).weekday(), DIA_PRESENCIA_WEB)

    def test_el_lunes_no_es_el_dia(self):
        from sala_control.resumen import DIA_PRESENCIA_WEB
        self.assertNotEqual(date(2026, 8, 24).weekday(), DIA_PRESENCIA_WEB)


class EndpointDelCron(TestCase):
    """El endpoint dispara un ENVÍO de correo a la lista de distribución.

    Sin llave no entra nadie: un endpoint de cron abierto es un botón de
    «mandar correo» que cualquiera en internet puede apretar.
    """

    URL = '/ventas/api/cron/resumen-ejecutivo/'

    def test_sin_llave_no_entra(self):
        self.assertEqual(self.client.post(self.URL).status_code, 401)

    def test_llave_errada_no_entra(self):
        r = self.client.post(self.URL, HTTP_X_API_KEY='no-es-la-llave')
        self.assertEqual(r.status_code, 401)

    def test_sin_llave_configurada_no_entra(self):
        """Si la variable quedó vacía en el servidor, el endpoint se cierra en
        vez de abrirse: fallar hacia el lado seguro."""
        from django.test import override_settings
        with override_settings(AUTOMATION_API_KEY=''):
            r = self.client.post(self.URL, HTTP_X_API_KEY='')
            self.assertEqual(r.status_code, 401)

    def test_con_llave_dispara_y_responde_al_tiro(self):
        """Responde sin esperar: cron-job.org corta a los 30 segundos y el
        resumen demora más que eso en armarse."""
        from unittest.mock import patch

        from django.test import override_settings

        with override_settings(AUTOMATION_API_KEY='llave-de-prueba'), \
                patch('ventas.views.api_views.'
                      '_run_resumen_ejecutivo_background') as corrio:
            r = self.client.post(self.URL, HTTP_X_API_KEY='llave-de-prueba')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])
        # El trabajo va en un hilo aparte; puede alcanzar a correr o no antes
        # de que termine el test — lo que se prueba acá es que el endpoint
        # contesta al instante, no cuánto demora el hilo.
        self.assertLessEqual(corrio.call_count, 1)


class TextoQueSeLee(SimpleTestCase):
    """Detalles que no cambian ningún número pero se ven todos los días."""

    def test_una_publicacion_no_dice_publicacion_es(self):
        a = alertas.alerta_publicaciones_pendientes(
            [{'estado': 'pendiente', 'hora': '19:00', 'canal': 'IG'}])
        self.assertIn('1 publicación de hoy', a['texto'])
        self.assertNotIn('(es)', a['texto'])

    def test_varias_van_en_plural(self):
        a = alertas.alerta_publicaciones_pendientes(
            [{'estado': 'pendiente', 'hora': '19:00', 'canal': 'IG'},
             {'estado': 'pendiente', 'hora': '20:00', 'canal': 'IG'}])
        self.assertIn('2 publicaciones de hoy', a['texto'])

    def test_recorta_en_palabra_completa(self):
        """El caso real: cortar a 60 caracteres dejaba «la fa»."""
        largo = ('Catorce días embarcado. Catorce en tierra. En esos '
                 'catorce entra el banco, la familia, todo.')
        corto = render.recortar(largo, 60)
        self.assertTrue(corto.endswith('…'))
        self.assertNotIn('la fa…', corto)
        self.assertTrue(len(corto) <= 61)
        # No corta a mitad de palabra: lo que queda antes de los puntos
        # suspensivos es una palabra entera del original.
        self.assertIn(corto[:-1].split()[-1], largo.split())

    def test_texto_corto_queda_igual_y_sin_puntos(self):
        self.assertEqual(render.recortar('Tina con vapor', 80),
                         'Tina con vapor')

    def test_sin_titulo_no_revienta(self):
        self.assertEqual(render.recortar(None, 20), '')

    def test_no_deja_coma_colgando_antes_de_los_puntos(self):
        self.assertEqual(render.recortar('uno dos, tres cuatro', 10),
                         'uno dos…')


class RecorteSinPalabrasColgando(SimpleTestCase):
    """Cortar en palabra completa no basta: deja artículos huérfanos que se
    leen como un error («…entra el banco, la…»)."""

    REAL = ('Catorce días embarcado. Catorce en tierra. En esos catorce entra '
            'el banco, la familia, todo. Agua a 38. Dos horas.')

    def test_suelta_el_articulo_del_final(self):
        corto = render.recortar(self.REAL, 80)
        self.assertTrue(corto.endswith('banco…'), corto)

    def test_suelta_la_preposicion_del_final(self):
        corto = render.recortar(
            'Vienes al Medio Maratón. Estacionamiento, desayuno a la hora '
            'que necesites. A minutos del recorrido.', 80)
        self.assertTrue(corto.endswith('necesites…'), corto)

    def test_no_se_come_el_texto_entero(self):
        """Si TODO fueran palabras de enlace, igual queda algo."""
        self.assertTrue(render.recortar('de la que en el por a la de', 12))

    def test_conserva_palabras_con_contenido(self):
        corto = render.recortar('Tina caliente junto al río Pescado azul', 22)
        self.assertTrue(corto.endswith('junto…'), corto)


class ElPanelPideClave(TestCase):
    """El panel muestra caja, ventas y conversaciones de clientes. Nadie
    entra sin sesión, y no basta con estar logueado."""

    def test_sin_sesion_no_entra(self):
        r = self.client.get('/sala/')
        self.assertIn(r.status_code, (302, 403))

    def test_usuario_comun_no_entra(self):
        from django.contrib.auth.models import User
        User.objects.create_user('pedro', password='x')
        self.client.login(username='pedro', password='x')
        r = self.client.get('/sala/')
        self.assertIn(r.status_code, (302, 403))

    def test_acciones_solo_por_post(self):
        """Un GET no puede marcar nada: los buscadores y los precargadores de
        enlaces siguen GETs, y despejarían la lista solos."""
        from django.contrib.auth.models import User
        User.objects.create_superuser('jorge', 'j@x.cl', 'x')
        self.client.login(username='jorge', password='x')
        for url in ('/sala/marcar-publicacion/', '/sala/agregar-nota/',
                    '/sala/alternar-nota/', '/sala/alternar-prioridad/',
                    '/sala/refrescar-ads/'):
            self.assertEqual(self.client.get(url).status_code, 405, url)


class MarcarPublicaciones(TestCase):
    """Una fila se despeja si el Telar dice «publicada» O si Jorge la marcó:
    son dos preguntas distintas y cualquiera de las dos la resuelve."""

    def setUp(self):
        from django.contrib.auth.models import User
        User.objects.create_superuser('jorge', 'j@x.cl', 'x')
        self.client.login(username='jorge', password='x')

    def _estado(self, publicaciones, marcadas=()):
        from unittest.mock import patch

        from sala_control.models import MarcaPublicacion
        from sala_control.panel import _pendientes_del_dia
        hoy = date.today()
        for pid in marcadas:
            MarcaPublicacion.objects.create(fecha=hoy, publicacion_id=pid)
        with patch('sala_control.fuentes.plan_del_dia',
                   return_value={'publicaciones': publicaciones,
                                 'semana': {'total': 1}}):
            filas, _ = _pendientes_del_dia(hoy)
        return filas

    def test_publicada_en_el_telar_queda_resuelta(self):
        filas = self._estado([{'id': 7, 'estado': 'publicada'}])
        self.assertTrue(filas[0]['resuelta'])
        self.assertTrue(filas[0]['por_telar'])

    def test_marcada_por_jorge_queda_resuelta(self):
        filas = self._estado([{'id': 7, 'estado': 'pendiente'}], marcadas=[7])
        self.assertTrue(filas[0]['resuelta'])
        self.assertTrue(filas[0]['marcada_por_mi'])
        self.assertFalse(filas[0]['por_telar'])

    def test_ni_una_ni_otra_queda_pendiente(self):
        filas = self._estado([{'id': 7, 'estado': 'pendiente'}])
        self.assertFalse(filas[0]['resuelta'])

    def test_telar_caido_no_revienta_el_panel(self):
        from unittest.mock import patch
        from sala_control.panel import _pendientes_del_dia
        with patch('sala_control.fuentes.plan_del_dia', return_value=None):
            filas, semana = _pendientes_del_dia(date.today())
        self.assertIsNone(filas)
        self.assertIsNone(semana)

    def test_marcar_es_un_interruptor(self):
        """Desmarcar importa: equivocarse sin poder deshacer es lo que hace
        que la gente deje de marcar."""
        from sala_control.models import MarcaPublicacion
        for _ in range(2):
            self.client.post('/sala/marcar-publicacion/',
                             {'publicacion_id': '42', 'titulo': 'Tina'})
        self.assertEqual(MarcaPublicacion.objects.count(), 0)

    def test_una_marca_no_pisa_a_la_otra(self):
        from sala_control.models import MarcaPublicacion
        self.client.post('/sala/marcar-publicacion/', {'publicacion_id': '42'})
        self.client.post('/sala/marcar-publicacion/', {'publicacion_id': '43'})
        self.assertEqual(MarcaPublicacion.objects.count(), 2)

    def test_id_basura_no_crea_nada(self):
        from sala_control.models import MarcaPublicacion
        for malo in ('', 'abc', '0'):
            self.client.post('/sala/marcar-publicacion/',
                             {'publicacion_id': malo})
        self.assertEqual(MarcaPublicacion.objects.count(), 0)


class NotasDelDia(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        User.objects.create_superuser('jorge', 'j@x.cl', 'x')
        self.client.login(username='jorge', password='x')

    def test_agregar_y_despejar(self):
        from sala_control.models import NotaDelDia
        self.client.post('/sala/agregar-nota/',
                         {'texto': 'Llamar a Cristóbal',
                          'link': 'https://ejemplo.cl/x',
                          'negocio': 'datamatic'})
        n = NotaDelDia.objects.get()
        self.assertEqual(n.negocio, 'datamatic')
        self.assertFalse(n.hecha)
        self.client.post('/sala/alternar-nota/', {'nota_id': n.id})
        n.refresh_from_db()
        self.assertTrue(n.hecha)

    def test_texto_vacio_no_crea_nota(self):
        from sala_control.models import NotaDelDia
        self.client.post('/sala/agregar-nota/', {'texto': '   '})
        self.assertEqual(NotaDelDia.objects.count(), 0)


class CorteDePublicidad(TestCase):
    def test_guarda_y_declara_su_hora(self):
        from sala_control.models import CorteAds
        from sala_control.panel import guardar_corte_ads
        c = guardar_corte_ads({'meta': 201000, 'google': 310000, 'dias': 22},
                              date(2026, 8, 26))
        self.assertEqual(c.total, 511000)
        self.assertIsNotNone(c.calculado_en)

    def test_no_leido_no_es_cero(self):
        """Un fallo de red deja None. Guardarlo como cero se leería como
        «no gastamos nada» y llevaría a subir presupuesto sin razón."""
        from sala_control.panel import guardar_corte_ads
        c = guardar_corte_ads({'meta': None, 'google': None, 'dias': 22},
                              date(2026, 8, 26))
        self.assertIsNone(c.total)

    def test_el_del_dia_se_actualiza_no_se_duplica(self):
        from sala_control.models import CorteAds
        from sala_control.panel import guardar_corte_ads
        guardar_corte_ads({'meta': 1, 'google': 1}, date(2026, 8, 26))
        guardar_corte_ads({'meta': 2, 'google': 2}, date(2026, 8, 26))
        self.assertEqual(CorteAds.objects.count(), 1)
        self.assertEqual(CorteAds.objects.get().total, 4)


class ElPanelSeDibuja(TestCase):
    """La prueba que atrapa lo que ninguna otra ve: un error de plantilla.

    Todo lo demás se puede probar sin renderizar, y por eso una llave mal
    cerrada o un filtro mal escrito llegaría intacto a producción y el panel
    daría error 500 justo cuando Jorge lo abre por primera vez.
    """

    def setUp(self):
        from django.contrib.auth.models import User
        User.objects.create_superuser('jorge', 'j@x.cl', 'x')
        self.client.login(username='jorge', password='x')

    def test_carga_con_datos(self):
        from sala_control.models import NotaDelDia, PrioridadSemana
        from sala_control.panel import guardar_corte_ads
        from sala_control.fuentes import lunes_de
        hoy = date.today()
        # La vista busca por el LUNES de la semana, no por hoy.
        PrioridadSemana.objects.create(
            semana_inicio=lunes_de(hoy), orden=1, texto='Revisar la carta')
        NotaDelDia.objects.create(fecha=hoy, texto='Llamar a Cristóbal',
                                  link='https://ejemplo.cl/x',
                                  negocio='datamatic')
        guardar_corte_ads({'meta': 201000, 'google': 310000, 'dias': 22}, hoy)

        r = self.client.get('/sala/')
        self.assertEqual(r.status_code, 200)
        cuerpo = r.content.decode()
        self.assertIn('Sala de control', cuerpo)
        self.assertIn('Revisar la carta', cuerpo)
        self.assertIn('Llamar a Cristóbal', cuerpo)
        # Formato chileno: puntos de miles, no el espacio que ponía intcomma.
        self.assertIn('$511.000', cuerpo)
        self.assertNotIn('511\xa0000', cuerpo)

    def test_carga_sin_nada_cargado(self):
        """El día de estreno no hay prioridades, ni notas, ni corte de ads, y
        el Telar puede no responder. Igual tiene que dibujarse."""
        r = self.client.get('/sala/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Sala de control', r.content.decode())

    def test_la_fecha_sale_en_castellano(self):
        r = self.client.get('/sala/')
        cuerpo = r.content.decode()
        self.assertIn(' de ', cuerpo)
        # El escape del filtro de fecha no debe filtrarse crudo al HTML.
        self.assertNotIn('\\d\\e', cuerpo)
