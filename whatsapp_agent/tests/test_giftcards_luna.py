# -*- coding: utf-8 -*-
"""Luna vende gift cards (pedido de Jorge 2026-08-12).

El caso que se caía: «quiero regalar dos masajes para mis papás» — Luna no
tenía camino. Estos tests cubren el camino completo: catálogo vivo → propuesta
(gate de Deborah) → aprobación crea la venta con sus cartas → el Pase las
muestra sin código y sin QR.
"""
from datetime import date

from django.test import TestCase, override_settings
from django.utils import timezone

from ventas.models import (Cliente, GiftCard, GiftCardExperiencia,
                           VentaReserva)
from whatsapp_agent.giftcards import (catalogo_giftcards,
                                      materializar_giftcards,
                                      preparar_giftcard)
from whatsapp_agent.models import PropuestaReserva

CLIENTE = {'nombre': 'María Prueba', 'email': 'maria@prueba.cl',
           'telefono': '+56911111111', 'documento_identidad': '12345678-5'}

# Desde H-094 la herramienta exige que el destinatario y la dedicatoria hayan
# salido de la boca del CLIENTE, así que los tests que prueban otra cosa
# (precios, calce de nombres, dedup) traen este historial de fondo.
HISTORIAL = ('[Cliente]: quiero regalar dos masajes\n'
             '[Aremko]: ¿A nombre de quién van?\n'
             '[Cliente]: para Los papás de María\n'
             '[Aremko]: ¿Quieres dejarles una frase?\n'
             '[Cliente]: pongan que los quiero mucho\n'
             # H-098: el correo y el nombre del comprador también se confirman
             # en voz alta aunque estén en la ficha.
             '[Aremko]: Te enviamos la gift card a maria@prueba.cl — ¿está bien?\n'
             '[Cliente]: sí\n'
             '[Aremko]: La compra queda a nombre de María Prueba, ¿está bien así?\n'
             '[Cliente]: sí\n')


def _experiencia(id_exp='masaje_relajacion', nombre='Masaje de Relajación',
                 monto_fijo=50000, activo=True, **extra):
    return GiftCardExperiencia.objects.create(
        id_experiencia=id_exp, categoria='masajes', nombre=nombre,
        descripcion='Masaje 50 minutos', descripcion_giftcard='Detalle',
        imagen='giftcards/x.jpg', monto_fijo=monto_fijo, activo=activo,
        **extra)


class _SinSenalesDeVenta:
    """Mismo patrón que finanzas.tests: las señales CRM/Meta sobre VentaReserva
    y Pago no son el sujeto de estos tests y arrastran estado ajeno."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._mover_senales(desconectar=True)

    @classmethod
    def tearDownClass(cls):
        cls._mover_senales(desconectar=False)
        super().tearDownClass()

    @staticmethod
    def _mover_senales(desconectar):
        from django.db.models.signals import post_save

        from control_gestion.signals import react_to_reserva_change
        from ventas.models import Pago, VentaReserva
        from ventas.signals.main_signals import actualizar_tramo_y_premios_on_pago

        mover = post_save.disconnect if desconectar else post_save.connect
        for receptor in (actualizar_tramo_y_premios_on_pago,
                         react_to_reserva_change):
            for emisor in (VentaReserva, Pago):
                mover(receptor, sender=emisor)

    def setUp(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().setUp()

    def tearDown(self):
        from ventas import middleware
        middleware._thread_locals.user = None
        super().tearDown()


class CatalogoGiftcardsTest(TestCase):
    def test_lee_de_la_bd_en_vivo_y_solo_activas(self):
        """Jorge agrega «Masaje para dos» en el admin y Luna la ofrece en el
        mensaje siguiente, sin deploy. Las inactivas no existen para Luna."""
        _experiencia()
        _experiencia(id_exp='vieja', nombre='Ya no va', activo=False)
        r = catalogo_giftcards()
        ids = [e['id'] for e in r['experiencias']]
        self.assertIn('masaje_relajacion', ids)
        self.assertNotIn('vieja', ids)

        _experiencia(id_exp='masaje_para_dos', nombre='Masaje para dos',
                     monto_fijo=95000)
        ids = [e['id'] for e in catalogo_giftcards()['experiencias']]
        self.assertIn('masaje_para_dos', ids)

    def test_tarjeta_de_valor_expone_montos_sugeridos(self):
        _experiencia(id_exp='valor', nombre='Tarjeta de Valor', monto_fijo=None,
                     montos_sugeridos=[30000, 50000])
        exp = catalogo_giftcards()['experiencias'][0]
        self.assertIsNone(exp['precio'])
        self.assertEqual(exp['montos_sugeridos'], [30000, 50000])


class PrepararGiftcardTest(TestCase):
    def setUp(self):
        self.exp = _experiencia()

    def _preparar(self, giftcards=None, cliente=None, **kw):
        # La secuencia de preguntas del regalo tiene su clase de tests propia
        # (y test_h094_secuencia_giftcard): acá se prueba OTRA cosa —precios,
        # topes, idempotencia—, así que el destinatario y la dedicatoria se dan
        # por preguntados y se inyectan en cada carta.
        kw.setdefault('sin_datos_regalo', True)
        cartas = giftcards or [{'experiencia_id': 'masaje_relajacion', 'cantidad': 2}]
        for carta in cartas:
            carta.setdefault('destinatario_nombre', 'Los papás de María')
        return preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=cliente or dict(CLIENTE), historial=HISTORIAL,
            giftcards_data=cartas, **kw)

    def test_dos_masajes_para_los_papas(self):
        """El caso exacto de Jorge: 2 masajes = propuesta por $100.000."""
        r = self._preparar()
        self.assertTrue(r['success'])
        self.assertEqual(r['total'], 100000)
        self.assertEqual(r['giftcards_count'], 2)
        prop = PropuestaReserva.objects.get(propuesta_id=r['propuesta_id'])
        self.assertEqual(prop.estado, 'pendiente')
        self.assertEqual(prop.payload['servicios'], [])
        self.assertEqual(prop.payload['giftcards'][0]['precio'], 50000)
        self.assertIn('Los papás', r['resumen_texto'])

    def test_sin_email_no_hay_venta(self):
        """Sin email no hay carta que entregar: se corta antes de proponer."""
        cliente = dict(CLIENTE, email='')
        r = self._preparar(cliente=cliente)
        self.assertFalse(r['success'])
        # H-094: además de negarse, dice qué preguntar.
        self.assertEqual(r['error'], 'falta_email')
        self.assertIn('correo', r['siguiente_pregunta'].lower())

    def test_el_precio_lo_pone_el_catalogo_no_el_llm(self):
        """Aunque el LLM mandara un precio, se ignora: defense in depth."""
        r = self._preparar(giftcards=[{'experiencia_id': 'masaje_relajacion',
                                       'cantidad': 1, 'precio': 1}])
        self.assertTrue(r['success'])
        self.assertEqual(r['total'], 50000)

    def test_experiencia_inactiva_o_inexistente_se_rechaza(self):
        GiftCardExperiencia.objects.filter(pk=self.exp.pk).update(activo=False)
        r = self._preparar()
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'experiencia_no_existe')

    def test_tarjeta_de_valor_exige_monto_dentro_de_rango(self):
        _experiencia(id_exp='valor', nombre='Tarjeta de Valor',
                     monto_fijo=None, montos_sugeridos=[30000])
        sin_monto = self._preparar(giftcards=[{'experiencia_id': 'valor'}])
        self.assertFalse(sin_monto['success'])
        chico = self._preparar(giftcards=[{'experiencia_id': 'valor',
                                           'monto': 500}])
        self.assertFalse(chico['success'])
        ok = self._preparar(giftcards=[{'experiencia_id': 'valor',
                                        'monto': 40000}])
        self.assertTrue(ok['success'])
        self.assertEqual(ok['total'], 40000)

    def test_un_pedido_gigante_pasa_por_humano(self):
        r = self._preparar(giftcards=[{'experiencia_id': 'masaje_relajacion',
                                       'cantidad': 40}])
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'demasiadas_giftcards')

    def test_reintento_del_llm_no_duplica_la_propuesta(self):
        a = self._preparar(idempotency_key='gc-test-1')
        b = self._preparar(idempotency_key='gc-test-1')
        self.assertEqual(a['propuesta_id'], b['propuesta_id'])
        self.assertTrue(b.get('duplicada'))
        self.assertEqual(PropuestaReserva.objects.count(), 1)


class MaterializarGiftcardsTest(_SinSenalesDeVenta, TestCase):
    def test_cada_unidad_es_una_carta_y_el_total_cuadra(self):
        cliente = Cliente.objects.create(nombre='María', telefono='+56911111111')
        venta = VentaReserva.objects.create(cliente=cliente, total=0,
                                            fecha_reserva=timezone.now())
        payload = {'cliente': dict(CLIENTE), 'giftcards': [
            {'experiencia_id': 'masaje_relajacion', 'precio': 50000,
             'cantidad': 2, 'destinatario_nombre': 'Los papás',
             'mensaje': 'Con cariño'}]}
        creadas, monto = materializar_giftcards(venta, payload, cliente)
        self.assertEqual((creadas, monto), (2, 100000))
        cartas = list(venta.giftcards.all())
        self.assertEqual(len(cartas), 2)
        for c in cartas:
            self.assertEqual(int(c.monto_inicial), 50000)
            self.assertEqual(c.estado, 'por_cobrar')
            self.assertEqual(c.comprador_email, 'maria@prueba.cl')
            self.assertEqual(c.destinatario_nombre, 'Los papás')
            self.assertEqual((c.fecha_vencimiento - date.today()).days, 365)
        # La señal recalculó el total de la venta con las cartas.
        venta.refresh_from_db()
        self.assertEqual(int(venta.total), 100000)


@override_settings(LUNA_API_KEY='clave-test')
class AprobarGiftcardTest(_SinSenalesDeVenta, TestCase):
    """El gate de Deborah: aprobar la propuesta crea la venta con sus cartas."""

    def setUp(self):
        super().setUp()
        _experiencia()

    def _aprobar(self, propuesta_id):
        return self.client.post(
            '/api/luna/reservas/create/', {'propuesta_id': propuesta_id},
            content_type='application/json', HTTP_X_API_KEY='clave-test')

    def test_aprobar_crea_venta_con_cartas_y_total(self):
        prep = preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE),
            historial=HISTORIAL, sin_datos_regalo=True,
            giftcards_data=[{'experiencia_id': 'masaje_relajacion',
                             'cantidad': 2,
                             'destinatario_nombre': 'Los papás'}])
        self.assertTrue(prep['success'])
        r = self._aprobar(prep['propuesta_id'])
        self.assertEqual(r.status_code, 201, r.content)
        datos = r.json()
        self.assertTrue(datos['success'])
        venta = VentaReserva.objects.get(id=datos['reserva']['id'])
        self.assertEqual(venta.giftcards.count(), 2)
        self.assertEqual(int(venta.total), 100000)
        self.assertEqual(int(venta.saldo_pendiente), 100000)
        self.assertEqual(venta.reservaservicios.count(), 0)
        # La propuesta quedó consumida.
        prop = PropuestaReserva.objects.get(propuesta_id=prep['propuesta_id'])
        self.assertEqual(prop.estado, 'creada')

    def test_doble_aprobacion_no_duplica_cartas(self):
        """El contrato real del endpoint: una propuesta consumida no se puede
        volver a aprobar (el doble click casi simultáneo lo cubren el caché y
        el lock). Lo que importa acá: NUNCA aparece una segunda carta."""
        prep = preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE), sin_datos_regalo=True,
            historial=HISTORIAL,
            giftcards_data=[{'experiencia_id': 'masaje_relajacion',
                             'destinatario_nombre': 'Los papás'}])
        a = self._aprobar(prep['propuesta_id'])
        b = self._aprobar(prep['propuesta_id'])
        self.assertEqual(a.status_code, 201)
        venta_id = a.json()['reserva']['id']
        cuerpo_b = b.json()
        self.assertTrue(
            cuerpo_b.get('duplicada')
            or (cuerpo_b.get('reserva') or {}).get('duplicada')
            or cuerpo_b.get('error') == 'propuesta_not_found',
            cuerpo_b)
        self.assertEqual(
            VentaReserva.objects.get(id=venta_id).giftcards.count(), 1)
        self.assertEqual(GiftCard.objects.count(), 1)


class PaseConGiftcardsTest(_SinSenalesDeVenta, TestCase):
    """El Pase de una compra solo-giftcard: cartas visibles, sin código, sin QR."""

    def test_el_pase_muestra_las_cartas_y_no_el_qr(self):
        from ventas.views.ficha_reserva_view import token_para_reserva
        _experiencia()
        cliente = Cliente.objects.create(nombre='María', telefono='+56911111111')
        venta = VentaReserva.objects.create(cliente=cliente, total=0,
                                            fecha_reserva=timezone.now())
        GiftCard.objects.create(
            monto_inicial=50000, monto_disponible=50000,
            fecha_vencimiento=date(2027, 8, 12), estado='por_cobrar',
            cliente_comprador=cliente, venta_reserva=venta,
            destinatario_nombre='Los papás',
            servicio_asociado='masaje_relajacion')
        venta.calcular_total()

        r = self.client.get(f'/ventas/reserva/{token_para_reserva(venta.id)}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Gift Card Masaje de Relajación')
        self.assertContains(r, 'para Los papás')
        self.assertContains(r, 'llega por email')
        # Sin QR de llegada: una gift card no tiene llegada que registrar.
        self.assertNotContains(r, 'Tu código de ingreso')
        # El código de la carta NO se publica en una página sin login.
        carta = venta.giftcards.first()
        self.assertNotContains(r, carta.codigo)


class PromptGiftcardsTest(TestCase):
    def test_el_prompt_trae_la_seccion_de_regalo(self):
        import whatsapp_agent.prompt as prompt_mod
        fuente = open(prompt_mod.__file__, encoding='utf-8').read()
        self.assertIn('GIFT CARDS', fuente)
        self.assertIn('catalogo_giftcards', fuente)
        self.assertIn('vale 1 año', fuente)

    def test_el_prompt_prohibe_regalar_lo_no_publicado(self):
        """Política de Jorge (2026-08-12): Luna ofrece SOLO las gift cards
        publicadas; los masajes se regalan dentro de las experiencias."""
        import whatsapp_agent.prompt as prompt_mod
        fuente = open(prompt_mod.__file__, encoding='utf-8').read()
        self.assertIn('Solo existe lo que devuelve', fuente)
        self.assertIn('DENTRO de las experiencias', fuente)

    def test_las_tools_estan_declaradas_y_despachadas(self):
        import whatsapp_agent.agent as agent_mod
        fuente = open(agent_mod.__file__, encoding='utf-8').read()
        self.assertIn("'catalogo_giftcards'", fuente)
        self.assertIn("'preparar_giftcard'", fuente)


class ResolverExperienciaTest(TestCase):
    """Primera prueba real (2026-08-12): Luna reconstruyó el id desde el
    nombre visible y la venta escaló. La tool ahora resuelve por nombre."""

    def setUp(self):
        _experiencia(id_exp='masaje_relajacion',
                     nombre='Masaje Relajación o Descontracturante (50 min)',
                     monto_fijo=40000)

    def _preparar(self, exp_id):
        return preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE), sin_datos_regalo=True,
            historial=HISTORIAL,
            giftcards_data=[{'experiencia_id': exp_id, 'cantidad': 2,
                             'destinatario_nombre': 'Los papás de María'}])

    def test_el_caso_exacto_que_escalo(self):
        """El modelo mandó el nombre tal como lo mostró, no el id."""
        r = self._preparar('Masaje Relajación o Descontracturante (50 min)')
        self.assertTrue(r['success'], r)
        self.assertEqual(r['total'], 80000)

    def test_tambien_resuelve_el_nombre_recortado(self):
        r = self._preparar('Masaje Relajación')
        self.assertTrue(r['success'], r)

    def test_el_id_exacto_sigue_funcionando(self):
        self.assertTrue(self._preparar('masaje_relajacion')['success'])

    def test_ambiguo_no_adivina_y_entrega_el_catalogo(self):
        _experiencia(id_exp='masaje_para_dos', nombre='Masaje para dos',
                     monto_fijo=95000)
        r = self._preparar('Masaje')
        self.assertFalse(r['success'])
        ids = [e['id'] for e in r['experiencias_disponibles']]
        self.assertIn('masaje_relajacion', ids)
        self.assertIn('masaje_para_dos', ids)

    def test_inexistente_entrega_el_catalogo_para_autocorregirse(self):
        """El error trae el catálogo: el modelo se corrige EN el mismo turno,
        sin tener que acordarse de llamar la otra tool."""
        r = self._preparar('algo_que_no_existe')
        self.assertFalse(r['success'])
        self.assertTrue(r['experiencias_disponibles'])
        self.assertIn('volvé a llamar', r['mensaje'])


class ResolverPorPalabrasTest(TestCase):
    """Segundo intento real (2026-08-12, 01:09): el nombre reconstruido y el
    del catálogo diferían en puntuación/tildes y el icontains literal no
    calzó. El calce va por palabras normalizadas."""

    def _preparar(self, exp_id):
        return preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE), sin_datos_regalo=True,
            historial=HISTORIAL,
            giftcards_data=[{'experiencia_id': exp_id, 'cantidad': 2,
                             'destinatario_nombre': 'Los papás de María'}])

    def test_puntuacion_y_tildes_distintas_igual_calzan(self):
        """El catálogo dice «· 50 min» y el modelo mandó «(50 min)»."""
        _experiencia(id_exp='masaje_relax',
                     nombre='Masaje de relajación o descontracturante · 50 min',
                     monto_fijo=40000)
        r = self._preparar('Masaje Relajacion o Descontracturante (50 min)')
        self.assertTrue(r['success'], r)
        self.assertEqual(r['total'], 80000)

    def test_el_orden_de_las_palabras_no_importa(self):
        _experiencia(id_exp='tina_dos', nombre='Tina para dos · junto al río',
                     monto_fijo=50000)
        r = self._preparar('tina junto al rio para dos')
        self.assertTrue(r['success'], r)

    def test_palabras_de_mas_no_calzan_con_cualquiera(self):
        """«masaje con piedras calientes» no debe caer en el masaje normal:
        pedir algo que no existe se responde con el catálogo, no adivinando."""
        _experiencia(id_exp='masaje_relax', nombre='Masaje de relajación',
                     monto_fijo=40000)
        r = self._preparar('masaje con piedras calientes')
        self.assertFalse(r['success'])
        self.assertTrue(r['experiencias_disponibles'])

    def test_el_error_le_ordena_al_modelo_no_mostrar_la_lista(self):
        """Lo segundo que enseñó el intento: el modelo le pasó la lista
        interna al cliente que YA había aceptado. El mensaje ahora lo
        prohíbe y le ordena reintentar solo."""
        _experiencia()
        r = self._preparar('no_existe_nada_asi')
        self.assertIn('NO le muestres esta lista', r['mensaje'])
        self.assertIn('volvé a llamar', r['mensaje'])


class PrecioDeLaFuenteCorrectaTest(TestCase):
    """Tercer intento real (2026-08-12, 01:23): Luna citó el precio del
    SERVICIO ($40.000) y la gift card valía $50.000 — el cliente aceptó un
    precio y la cotización salió con otro."""

    def test_el_resumen_con_precios_reales_viaja_en_la_propuesta(self):
        """La corrección visible: el resumen de la propuesta lleva el precio
        del catálogo de gift cards, línea por línea."""
        _experiencia(monto_fijo=50000)
        r = preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE), sin_datos_regalo=True,
            historial=HISTORIAL,
            giftcards_data=[{'experiencia_id': 'masaje_relajacion', 'cantidad': 2,
                             'destinatario_nombre': 'Los papás de María'}])
        self.assertTrue(r['success'])
        self.assertIn('$100,000', r['resumen_texto'].replace('.', ','))
        self.assertEqual(r['total'], 100000)

    def test_el_prompt_prohibe_cotizar_con_el_precio_del_servicio(self):
        import whatsapp_agent.prompt as prompt_mod
        fuente = open(prompt_mod.__file__, encoding='utf-8').read()
        self.assertIn('NUNCA del catálogo de', fuente)
        self.assertIn('ANTES de decir cualquier precio', fuente)

    def test_el_mensaje_de_cierre_incluye_el_detalle_con_precios(self):
        """El dispatch arma el mensaje al cliente con el resumen real: si el
        modelo citó mal antes, acá aparece la corrección."""
        import whatsapp_agent.agent as agent_mod
        fuente = open(agent_mod.__file__, encoding='utf-8').read()
        self.assertIn("resultado.get('resumen_texto')", fuente)


class CotizacionConGiftcardsTest(_SinSenalesDeVenta, TestCase):
    """Cuarto intento real (2026-08-12, 01:37): la conversación cerró perfecto
    y la página de la cotización decía «Sin servicios cargados aún — Total $0»
    con el botón de aprobar. La página no sabía de gift cards."""

    def _cotizar(self):
        _experiencia(id_exp='pausa_dos', nombre='Pausa junto al río · para dos',
                     monto_fijo=110000)
        prep = preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE), sin_datos_regalo=True,
            historial=HISTORIAL + '[Cliente]: para Martín\n',
            giftcards_data=[{'experiencia_id': 'pausa_dos',
                             'destinatario_nombre': 'Martín'}])
        self.assertTrue(prep['success'])
        return prep

    def test_la_cotizacion_muestra_las_cartas_y_el_total_real(self):
        from ventas.views.ficha_reserva_view import token_para_cotizacion
        prep = self._cotizar()
        r = self.client.get(
            f'/ventas/propuesta/{token_para_cotizacion(prep["propuesta_id"])}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Pausa junto al río')
        self.assertContains(r, 'para Martín')
        self.assertContains(r, '$110.000')
        self.assertContains(r, 'llega por email')
        self.assertNotContains(r, 'Sin servicios cargados')
        self.assertNotContains(r, 'Total</span><span>$0<')
        # El copy del botón habla de gift cards, no de generar una reserva.
        self.assertContains(r, 'las gift cards llegan a tu email')

    def test_aprobar_desde_la_pagina_crea_la_venta_con_cartas(self):
        """El botón del cliente termina el circuito completo."""
        from django.contrib.auth.models import User as _User

        from ventas.views.ficha_reserva_view import token_para_cotizacion
        _User.objects.create_superuser('sistema', 's@s.cl', 'x')
        prep = self._cotizar()
        token = token_para_cotizacion(prep['propuesta_id'])
        with override_settings(LUNA_API_KEY='clave-test'):
            r = self.client.post(f'/ventas/propuesta/{token}/aprobar/')
        self.assertEqual(r.status_code, 302, getattr(r, 'content', b'')[:200])
        prop = PropuestaReserva.objects.get(propuesta_id=prep['propuesta_id'])
        self.assertEqual(prop.estado, 'creada')
        venta = VentaReserva.objects.get(id=prop.reserva_id)
        self.assertEqual(venta.giftcards.count(), 1)
        self.assertEqual(int(venta.total), 110000)
        # Y la ficha destino ya sabe mostrarlas (GC-C).
        self.assertIn('/ventas/reserva/', r.url)


class PreguntasDeRegaloObligatoriasTest(TestCase):
    """Quinto intento real (2026-08-12, 01:46): Luna saltó directo al cierre
    y la carta salió «para su hijo», sin nombre ni dedicatoria, y el email se
    usó en silencio. Luna no sostiene guiones: la pregunta obligatoria vive
    en la herramienta."""

    def setUp(self):
        _experiencia()

    def _preparar(self, gc=None, historial='', **kw):
        return preparar_giftcard(
            canal='whatsapp', external_id='+56911111111',
            cliente_data=dict(CLIENTE), historial=historial,
            giftcards_data=[gc or {'experiencia_id': 'masaje_relajacion'}],
            **kw)

    def test_sin_destinatario_ni_dedicatoria_se_niega(self):
        r = self._preparar()
        self.assertFalse(r['success'])
        # H-094 cambió el nombre del error: ahora la herramienta no solo se
        # niega, dice CUÁL es la siguiente pregunta.
        self.assertEqual(r['error'], 'falta_destinatario')
        self.assertIn('nombre', r['siguiente_pregunta'].lower())
        self.assertEqual(PropuestaReserva.objects.count(), 0)

    def test_con_destinatario_pasa(self):
        r = self._preparar({'experiencia_id': 'masaje_relajacion',
                            'destinatario_nombre': 'Martín'},
                           historial=HISTORIAL + '[Cliente]: para Martín\n',
                           sin_datos_regalo=True)
        self.assertTrue(r['success'], r)

    def test_solo_dedicatoria_YA_NO_alcanza(self):
        """H-094: el destinatario dejó de ser opcional. Una carta sin nombre de
        quien la recibe es justo lo que salió mal a las 01:46."""
        r = self._preparar({'experiencia_id': 'masaje_relajacion',
                            'mensaje': 'Con cariño, papá'},
                           historial='[Cliente]: con cariño, papá\n')
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], 'falta_destinatario')

    def test_declinar_la_frase_pasa_pero_el_nombre_sigue_haciendo_falta(self):
        """`sin_datos_regalo` siempre fue para la DEDICATORIA, nunca un permiso
        para saltarse a quién va dirigido el regalo."""
        self.assertEqual(
            self._preparar(sin_datos_regalo=True)['error'], 'falta_destinatario')
        r = self._preparar({'experiencia_id': 'masaje_relajacion',
                            'destinatario_nombre': 'Martín'},
                           historial=HISTORIAL + '[Cliente]: para Martín\n',
                           sin_datos_regalo=True)
        self.assertTrue(r['success'], r)

    def test_el_cierre_confirma_el_email_en_voz_alta(self):
        """El email de la ficha se usa, pero nunca más en silencio: el
        mensaje al cliente lo dice y ofrece corregirlo."""
        import whatsapp_agent.agent as agent_mod
        fuente = open(agent_mod.__file__, encoding='utf-8').read()
        self.assertIn('las gift cards llegan a {email}', fuente)
        self.assertIn('Si prefieres otro correo', fuente)


class CatalogoRealDeAremkoTest(TestCase):
    """Simulado contra el catálogo REAL de Jorge (2026-08-12) y traído acá:
    dos agujeros que no se veían con nombres de laboratorio."""

    def setUp(self):
        # Los nombres son los de producción, tal cual.
        _experiencia(id_exp='Masaje para 1 persona',
                     nombre='Masaje de Relajacion o Descontracturante 1 persona',
                     monto_fijo=40000)
        _experiencia(id_exp='masaje_pareja', nombre='Masaje para Dos',
                     monto_fijo=80000)
        _experiencia(id_exp='tina_para_dos',
                     nombre='Tina para dos · junto al río', monto_fijo=50000)
        _experiencia(id_exp='velada_dulce', nombre='Velada Sorpresa · Dulce',
                     monto_fijo=98000)
        _experiencia(id_exp='velada_dulce_hidro',
                     nombre='Velada Sorpresa · Dulce + hidromasaje',
                     monto_fijo=108000)

    def _resolver(self, texto):
        from whatsapp_agent.giftcards import _resolver_experiencia
        exp, _err = _resolver_experiencia(texto)
        return exp

    def test_dos_masajes_calza_aunque_venga_en_plural(self):
        """La frase literal de Jorge. Antes: «masajes» ≠ «Masaje» → error."""
        exp = self._resolver('dos masajes')
        self.assertIsNotNone(exp)
        self.assertEqual(exp.id_experiencia, 'masaje_pareja')

    def test_la_velada_base_ya_no_es_irresoluble(self):
        """«Velada Sorpresa · Dulce» es subconjunto exacto de «… +
        hidromasaje»: pedir la base daba ambigüedad para siempre. Ahora el
        calce EXACTO gana."""
        exp = self._resolver('Velada Sorpresa Dulce')
        self.assertIsNotNone(exp)
        self.assertEqual(exp.id_experiencia, 'velada_dulce')

    def test_la_version_con_hidromasaje_sigue_resolviendo(self):
        exp = self._resolver('Velada Sorpresa · Dulce + hidromasaje')
        self.assertEqual(exp.id_experiencia, 'velada_dulce_hidro')

    def test_masaje_a_secas_sigue_pidiendo_precision(self):
        """Con dos masajes activos, «masaje» es genuinamente ambiguo: no
        adivinar es lo correcto."""
        self.assertIsNone(self._resolver('masaje'))

    def test_el_individual_no_se_confunde_con_el_de_pareja(self):
        exp = self._resolver('Masaje Relajación o Descontracturante (50 min)')
        self.assertEqual(exp.id_experiencia, 'Masaje para 1 persona')
        self.assertEqual(int(exp.monto_fijo), 40000)

    def test_el_prompt_distingue_una_carta_para_dos_de_dos_cartas(self):
        import whatsapp_agent.prompt as prompt_mod
        fuente = open(prompt_mod.__file__, encoding='utf-8').read()
        self.assertIn('Masaje para dos personas', fuente)
        self.assertIn('no se puede partir', fuente)
