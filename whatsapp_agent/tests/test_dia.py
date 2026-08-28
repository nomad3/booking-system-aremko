# -*- coding: utf-8 -*-
"""Pruebas de «Cabaña y spa por el día».

Lo que se cuida acá es la regla que hace único a este producto: exige la
cabaña libre la noche ANTERIOR y la del día. Si esa regla falla hacia el lado
permisivo, se vende un día para el que la cabaña no va a estar lista a las
10:00 de la mañana — y el cliente llega desde Osorno a una puerta cerrada.

El otro cuidado es la jerarquía de horarios: solo las combinaciones que
cierran con la tina de las 16:30 entregan las ocho horas que promete el
nombre. Ofrecer una corta habiendo una larga libre es cobrar lo mismo por
medio día menos.
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from whatsapp_agent import packs

LUNES = date(2026, 8, 31)
MARTES = date(2026, 9, 1)
MIERCOLES = date(2026, 9, 2)
DOMINGO = date(2026, 8, 30)


def _serv(sid, nombre, slots):
    return {'servicio_id': sid, 'nombre': nombre, 'slots_libres': list(slots),
            'precio_total': 100000}


CAB = [_serv(1, 'Cabaña Pucón', ['16:00'])]
MASAJES = [_serv(9, 'Masaje Relajación', ['11:45', '13:00', '14:15'])]
TINAS = [_serv(5, 'Tina Llaima', ['11:30', '14:00', '16:30'])]


def _mock(cab_previa, cab_dia, masajes=None, tinas=None):
    """Simula el motor: responde según la fecha y el tipo que le pidan."""
    def _disp(f, personas, tipo, limite=None, incluir_slots_programa=False):
        if tipo == 'cabana':
            return {'servicios': cab_dia if f == LUNES else cab_previa}
        if tipo == 'masaje':
            return {'servicios': MASAJES if masajes is None else masajes}
        return {'servicios': TINAS if tinas is None else tinas}
    return _disp


class LaReglaDeLasDosNoches(SimpleTestCase):
    """La noche anterior importa tanto como la del día, y por razones distintas:
    la anterior para que la cabaña esté lista a las 10:00, la del día porque el
    cliente la ocupa hasta la tarde."""

    def _pedir(self, cab_previa, cab_dia):
        with patch('whatsapp_agent.availability.disponibilidad',
                   side_effect=_mock(cab_previa, cab_dia)), \
             patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None):
            return packs.disponibilidad_dia(LUNES.isoformat())

    def test_libre_las_dos_noches_se_vende(self):
        r = self._pedir(CAB, CAB)
        self.assertTrue(r['disponible'], r.get('nota'))
        self.assertEqual(r['itinerario']['cabana']['nombre'], 'Cabaña Pucón')

    def test_ocupada_la_noche_anterior_NO_se_vende(self):
        """El caso peligroso: la cabaña está libre el lunes, pero alguien
        durmió el domingo y se va a las 11:00. A las 10:00 no está lista."""
        r = self._pedir([], CAB)
        self.assertFalse(r['disponible'])
        self.assertIn('noche anterior', r['nota'])

    def test_ocupada_la_noche_del_dia_NO_se_vende(self):
        r = self._pedir(CAB, [])
        self.assertFalse(r['disponible'])

    def test_tiene_que_ser_la_MISMA_cabaña(self):
        """Una libre el domingo y otra distinta el lunes no sirve: el cliente
        no se cambia de cabaña a mitad de día."""
        otra = [_serv(2, 'Cabaña Villarrica', ['16:00'])]
        r = self._pedir(otra, CAB)
        self.assertFalse(r['disponible'])


class LosDiasQueSeVenden(SimpleTestCase):
    def _pedir(self, f):
        with patch('whatsapp_agent.availability.disponibilidad',
                   side_effect=_mock(CAB, CAB)), \
             patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None):
            return packs.disponibilidad_dia(f.isoformat())

    def test_el_martes_no_se_vende(self):
        """Aremko cierra los martes por mantención."""
        r = self._pedir(MARTES)
        self.assertFalse(r['disponible'])
        self.assertIn('lunes, miércoles y jueves', r['nota'])

    def test_el_domingo_no_se_vende(self):
        """Las cabañas del sábado se desocupan a las 11:00: no alcanzan a
        prepararse para recibir a las 10:00."""
        self.assertFalse(self._pedir(DOMINGO)['disponible'])

    def test_el_miercoles_si(self):
        with patch('whatsapp_agent.availability.disponibilidad',
                   side_effect=lambda f, p, tipo, limite=None,
                   incluir_slots_programa=False: {
                       'servicios': CAB if tipo == 'cabana'
                       else (MASAJES if tipo == 'masaje' else TINAS)}), \
             patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None):
            self.assertTrue(packs.disponibilidad_dia(MIERCOLES.isoformat())['disponible'])


class LaJerarquiaDeHorarios(SimpleTestCase):
    """Solo las combinaciones con tina a las 16:30 dan las ocho horas."""

    def _pedir(self, masajes, tinas):
        with patch('whatsapp_agent.availability.disponibilidad',
                   side_effect=_mock(CAB, CAB, masajes, tinas)), \
             patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None):
            return packs.disponibilidad_dia(LUNES.isoformat())

    def test_con_todo_libre_elige_la_de_las_ocho_horas(self):
        it = self._pedir(MASAJES, TINAS)['itinerario']
        self.assertEqual(it['tina']['hora'], '16:30')
        self.assertEqual(it['masaje']['hora'], '11:45')

    def test_sin_16_30_baja_al_respaldo_y_no_inventa(self):
        """Sin la tina de las 16:30 quedan las cortas. Tiene que elegir una
        combinación REAL de la lista, no armar uno que se pise."""
        tinas = [_serv(5, 'Tina Llaima', ['11:30', '14:00'])]
        it = self._pedir(MASAJES, tinas)['itinerario']
        self.assertIn((it['masaje']['hora'], it['tina']['hora']),
                      packs.DIA_COMBINACIONES)
        self.assertNotEqual(it['tina']['hora'], '16:30')

    def test_prefiere_la_tina_estandar_sobre_la_de_hidromasaje(self):
        """Precio plano: gastar la tina cara sin necesidad se come el margen."""
        tinas = [_serv(7, 'Tina Hidromasaje Calbuco', ['16:30']),
                 _serv(5, 'Tina Llaima', ['16:30'])]
        r = self._pedir(MASAJES, tinas)
        self.assertEqual(r['itinerario']['tina']['nombre'], 'Tina Llaima')
        self.assertFalse(r['es_hidromasaje'])

    def test_sin_masaje_no_hay_programa(self):
        r = self._pedir([_serv(9, 'Masaje', [])], TINAS)
        self.assertFalse(r['disponible'])
        self.assertIn('calce', r['nota'])

    def test_no_usa_los_horarios_reservados_al_ritual(self):
        """15:30/18:00/20:30/21:45 son del Ritual y del Refugio. Este producto
        no puede quitárselos."""
        reservados = {'15:30', '18:00', '20:30', '21:45'}
        for masaje_hora, _ in packs.DIA_COMBINACIONES:
            self.assertNotIn(masaje_hora, reservados)


class ElPrecioYLaForma(SimpleTestCase):
    def test_precio_plano(self):
        self.assertEqual(packs.DIA_PRECIO_PLANO, 200000)

    def test_fecha_invalida_avisa(self):
        self.assertIn('error', packs.disponibilidad_dia('no-es-fecha'))

    def test_las_cinco_combinaciones_y_el_orden(self):
        """Las tres primeras cierran a las 16:30 —las de ocho horas— y van
        antes que las de respaldo. Si alguien reordena la lista, esto avisa."""
        self.assertEqual(len(packs.DIA_COMBINACIONES), 5)
        self.assertTrue(all(t == '16:30' for _, t in packs.DIA_COMBINACIONES[:3]))
        self.assertTrue(all(t != '16:30' for _, t in packs.DIA_COMBINACIONES[3:]))


class ElBloqueoDeLaNocheAnterior(TestCase):
    """Sin este bloqueo queda una ventana peligrosa: se vende el día, alguien
    reserva esa noche después, y el cliente llega desde Osorno a las 10:00 a
    una cabaña que recién se está desocupando."""

    def setUp(self):
        from ventas.models import Servicio
        self.cabana = Servicio.objects.create(
            nombre='Cabaña Pucón', precio_base=100000, duracion=60,
            slots_disponibles=['16:00'])

    def test_bloquea_la_noche_ANTERIOR_no_la_del_dia(self):
        from ventas.models import ServicioSlotBloqueo
        packs.bloquear_noche_previa(self.cabana.id, LUNES)
        fechas = list(ServicioSlotBloqueo.objects
                      .filter(servicio=self.cabana).values_list('fecha', flat=True))
        self.assertEqual(fechas, [LUNES - timedelta(days=1)])

    def test_llamarla_dos_veces_no_duplica(self):
        """La confirmación puede reintentarse; no puede dejar basura."""
        from ventas.models import ServicioSlotBloqueo
        packs.bloquear_noche_previa(self.cabana.id, LUNES)
        packs.bloquear_noche_previa(self.cabana.id, LUNES)
        self.assertEqual(ServicioSlotBloqueo.objects.count(), 1)

    def test_bloquea_todos_los_slots_de_la_cabaña(self):
        """Si mañana alguien le agrega un horario a la cabaña, la noche tiene
        que seguir cerrada — no solo el check-in."""
        from ventas.models import ServicioSlotBloqueo
        self.cabana.slots_disponibles = ['16:00', '18:00']
        self.cabana.save(update_fields=['slots_disponibles'])
        packs.bloquear_noche_previa(self.cabana.id, LUNES)
        self.assertEqual(ServicioSlotBloqueo.objects.count(), 2)

    def test_queda_marcado_con_su_motivo(self):
        """Se busca por el motivo para deshacerlo si la reserva se cancela."""
        from ventas.models import ServicioSlotBloqueo
        packs.bloquear_noche_previa(self.cabana.id, LUNES, referencia='reserva 123')
        b = ServicioSlotBloqueo.objects.get()
        self.assertEqual(b.motivo, packs.DIA_MOTIVO_BLOQUEO)
        self.assertIn('123', b.notas or '')
        self.assertTrue(b.activo)

    def test_cabaña_inexistente_no_revienta(self):
        self.assertEqual(packs.bloquear_noche_previa(999999, LUNES), 0)


class ElArmadoDeLaReserva(TestCase):
    """El total tiene que quedar clavado en $200.000, y la cabaña UNA sola vez
    —el cliente no duerme, y una noche fantasma haría que housekeeping prepare
    una llegada que no existe."""

    def setUp(self):
        from ventas.models import Servicio
        self.cab = Servicio.objects.create(nombre='Cabaña Pucón', precio_base=120000,
                                           duracion=60, slots_disponibles=['16:00'])
        self.tina = Servicio.objects.create(nombre='Tina Llaima', precio_base=50000,
                                            duracion=120, slots_disponibles=['16:30'])
        self.mas = Servicio.objects.create(nombre='Masaje', precio_base=40000,
                                           duracion=50, slots_disponibles=['11:45'])
        self.desc = Servicio.objects.create(nombre='Descuento de servicios',
                                            precio_base=-1000, duracion=1,
                                            slots_disponibles=['16:00'])

    def _armar(self):
        cab = [_serv(self.cab.id, 'Cabaña Pucón', ['16:00'])]
        with patch('whatsapp_agent.availability.disponibilidad',
                   side_effect=lambda f, p, tipo, limite=None,
                   incluir_slots_programa=False: {'servicios':
                       cab if tipo == 'cabana'
                       else ([_serv(self.mas.id, 'Masaje', ['11:45', '13:00', '14:15'])]
                             if tipo == 'masaje'
                             else [_serv(self.tina.id, 'Tina Llaima', ['16:30'])])}), \
             patch('whatsapp_agent.packs._desayuno_de_cabana', return_value=None), \
             patch('whatsapp_agent.packs._servicio_descuento', return_value=self.desc):
            return packs.construir_servicios_dia(LUNES.isoformat())

    def test_el_total_queda_en_200000(self):
        r = self._armar()
        self.assertTrue(r['disponible'], r.get('nota') or r.get('error'))
        self.assertEqual(r['total'], packs.DIA_PRECIO_PLANO)

    def test_la_cabaña_va_UNA_sola_vez(self):
        servicios = self._armar()['servicios']
        veces = [s for s in servicios if s['servicio_id'] == self.cab.id]
        self.assertEqual(len(veces), 1)
        self.assertEqual(veces[0]['fecha'], LUNES.isoformat())

    def test_devuelve_la_cabaña_para_poder_bloquear_la_noche_previa(self):
        self.assertEqual(self._armar()['cabana_id'], self.cab.id)

    def test_todo_cae_el_mismo_dia(self):
        """No hay noche: ningún servicio puede quedar en otra fecha."""
        for s in self._armar()['servicios']:
            self.assertEqual(s['fecha'], LUNES.isoformat())


class LasHerramientasDeLuna(SimpleTestCase):
    """Un nombre mal escrito acá no da error: simplemente Luna nunca usa la
    herramienta, el producto no se vende, y nadie se entera de por qué."""

    def _tools(self):
        from whatsapp_agent.agent import _TOOLS
        return {t['function']['name'] for t in _TOOLS}

    def test_las_dos_estan_declaradas(self):
        self.assertIn('consultar_disponibilidad_dia', self._tools())
        self.assertIn('confirmar_dia', self._tools())

    def test_la_descripcion_dice_los_dias_y_que_no_hay_alojamiento(self):
        """Si Luna no sabe que es lunes/miércoles/jueves y sin dormir, va a
        ofrecerlo cualquier día y prometer una noche que no existe."""
        from whatsapp_agent.agent import _TOOLS
        d = next(t['function']['description'] for t in _TOOLS
                 if t['function']['name'] == 'consultar_disponibilidad_dia')
        for palabra in ('lunes', 'miércoles', 'jueves', 'alojamiento DIURNO', '200.000'):
            self.assertIn(palabra, d)

    def test_confirmar_dia_cierra_la_conversacion(self):
        """Sin estar en esa lista, una confirmación exitosa sin texto del
        modelo escalaría a un humano sin necesidad."""
        import inspect

        from whatsapp_agent import agent
        fuente = inspect.getsource(agent)
        i = fuente.index("'confirmar_reserva_carrito', 'confirmar_ritual'")
        self.assertIn('confirmar_dia', fuente[i:i + 200])


class ElBloqueoQuedaCableado(SimpleTestCase):
    """El despacho vive dentro de una función anidada del agente, así que no se
    puede invocar directo. Esto es una comprobación de humo: verifica que la
    rama de confirmación efectivamente llama al bloqueo y que no depende de que
    el cliente tenga carrito o de que el bloqueo funcione para que la reserva
    sobreviva. No reemplaza a una prueba de integración — la reemplaza el día
    que el despacho se pueda llamar desde afuera."""

    def _rama(self):
        import inspect

        from whatsapp_agent import agent
        fuente = inspect.getsource(agent)
        i = fuente.index("if name == 'confirmar_dia':")
        return fuente[i:i + 6000]

    def test_llama_al_bloqueo_de_la_noche_previa(self):
        self.assertIn('bloquear_noche_previa(', self._rama())

    def test_bloquea_DESPUES_de_crear_la_propuesta(self):
        """Bloquear al cotizar dejaría noches tomadas por cotizaciones que
        nunca se convierten."""
        rama = self._rama()
        self.assertLess(rama.index('preparar_reserva('),
                        rama.index('bloquear_noche_previa('))

    def test_si_el_bloqueo_falla_la_reserva_no_se_cae_pero_grita(self):
        """Una reserva ya creada no se puede deshacer porque falló un bloqueo;
        pero la noche queda sin proteger y eso tiene que verse en el log."""
        rama = self._rama()
        i = rama.index('bloquear_noche_previa(')
        posterior = rama[i:i + 900]
        self.assertIn('except', posterior)
        self.assertIn('logger.error', posterior)


class LaInstruccionDeLuna(SimpleTestCase):
    """La herramienta puede existir y estar perfecta, y aun así el producto no
    venderse nunca: si el prompt no le dice a Luna CUÁNDO ofrecerlo, no lo va a
    ofrecer. Esa es la pieza que convierte código en ventas."""

    def _bloque(self):
        from whatsapp_agent import prompt
        import inspect
        fuente = inspect.getsource(prompt)
        i = fuente.index('CABAÑA Y SPA POR EL DÍA')
        return fuente[i:i + 2000]

    def test_le_dice_el_precio_y_los_dias(self):
        b = self._bloque()
        self.assertIn('200.000', b)
        for d in ('lunes', 'miércoles', 'jueves'):
            self.assertIn(d, b)

    def test_le_dice_el_gatillo(self):
        """El «me encantaría pero no puedo quedarme a dormir» es exactamente lo
        que este producto resuelve. Si Luna no lo reconoce, va a ofrecer una
        tina suelta y perder la venta."""
        b = self._bloque()
        self.assertIn('no puede quedarse a dormir', b)
        self.assertIn('niños', b)

    def test_prohibe_prometer_la_noche_sin_negar_la_cabaña(self):
        """Las dos mitades importan. Prometer la noche genera un reclamo el día
        de la llegada; pero decir «sin alojamiento» suena a que no reciben
        cabaña, y la cabaña es lo que los diferencia de cualquier spa."""
        b = self._bloque()
        self.assertIn('no se pernocta', b)
        self.assertIn('NUNCA «sin alojamiento»', b)

    def test_prohibe_inventar_horarios(self):
        """Los itinerarios salen del motor, que ya descartó las combinaciones
        que se pisan. Uno inventado manda a alguien a dos servicios a la vez."""
        b = self._bloque()
        self.assertIn('TAL CUAL', b)
        self.assertIn('nunca armes otra combinación', b.lower().replace('NUNCA', 'nunca'))

    def test_nombra_las_dos_herramientas(self):
        b = self._bloque()
        self.assertIn('consultar_disponibilidad_dia', b)
        self.assertIn('confirmar_dia', b)


class LaBandejaDeDeborah(SimpleTestCase):
    """El botón del menú de la bandeja llama a este constructor. Si el tipo no
    está registrado acá, el botón existe en la pantalla y no hace nada."""

    def test_el_tipo_esta_registrado(self):
        from whatsapp_agent import alternativas
        self.assertIn('dia', alternativas.TIPOS_VALIDOS)
        self.assertIn('dia', alternativas._BUILDERS)
        self.assertEqual(alternativas.NOMBRES['dia'], 'Cabaña y spa por el día')

    def _alternativas(self, masajes=None, tinas=None):
        from whatsapp_agent import alternativas
        base = {'disponible': True, 'fecha': LUNES.isoformat(), 'precio_total': 200000,
                'itinerario': {'cabana': {'nombre': 'Cabaña Pucón'},
                               'masaje': {'hora': '11:45'}, 'tina': {'hora': '16:30'}}}
        with patch('whatsapp_agent.packs.disponibilidad_dia', return_value=base), \
             patch('whatsapp_agent.alternativas.disponibilidad',
                   side_effect=lambda f, p, tipo, limite=None: {
                       'servicios': (MASAJES if masajes is None else masajes)
                       if tipo == 'masaje' else (TINAS if tinas is None else tinas)}):
            return alternativas._dia(LUNES.isoformat(), 2)

    def test_ofrece_una_alternativa_por_combinacion_libre(self):
        alts = self._alternativas()['alternativas']
        self.assertEqual(len(alts), 5)

    def test_las_de_ocho_horas_van_primero(self):
        """El orden del menú es el orden en que Deborah las va a ofrecer."""
        alts = self._alternativas()['alternativas']
        self.assertIn('16:30', alts[0]['titulo'])

    def test_el_texto_dice_que_la_cabaña_es_suya_pero_no_se_pernocta(self):
        """Es el texto que Deborah copia y pega al cliente, y tiene que decir
        las DOS cosas. «Sin alojamiento» a secas suena a que no reciben cabaña
        —lo pilló Jorge probándolo en vivo— y la cabaña es justamente lo que
        los diferencia de cualquier spa. Pero omitir que no se duerme genera
        un reclamo el día de la llegada."""
        texto = self._alternativas()['alternativas'][0]['texto_sugerido']
        self.assertNotIn('sin alojamiento', texto.lower())
        self.assertIn('a su disposición durante todo el día', texto)
        self.assertIn('no se pernocta', texto)
        self.assertIn('vuelven a dormir a su casa', texto)

    def test_todas_valen_200000(self):
        for a in self._alternativas()['alternativas']:
            self.assertEqual(a['precio_total'], 200000)
            self.assertFalse(a['hay_descuento'])

    def test_sin_disponibilidad_devuelve_lista_vacia_con_la_razon(self):
        from whatsapp_agent import alternativas
        with patch('whatsapp_agent.packs.disponibilidad_dia',
                   return_value={'disponible': False, 'fecha': LUNES.isoformat(),
                                 'nota': 'no hay cabaña libre las dos noches'}):
            r = alternativas._dia(LUNES.isoformat(), 2)
        self.assertEqual(r['alternativas'], [])
        self.assertIn('dos noches', r['nota'])


class LaCartaDePrecios(SimpleTestCase):
    """La carta es lo primero que ve quien escribe «hola». Si el programa no
    está ahí, para la mayoría de los clientes simplemente no existe: solo lo
    verían los que ya saben preguntar por él."""

    def _carta(self):
        from whatsapp_agent.carta import construir_carta
        return construir_carta(masaje=40000, tina_simple=50000,
                               tina_hidro=60000, cabana=110000)

    def test_aparece_en_la_carta(self):
        self.assertIn('Cabaña y spa por el día', self._carta())

    def test_va_ANTES_del_ritual_por_precio(self):
        """La carta se ordena de menor a mayor: $200.000 va antes de los
        $210.000 del Ritual. Verlos seguidos es lo que deja clara la elección
        —lo mismo, con o sin la noche."""
        c = self._carta()
        self.assertLess(c.index('Cabaña y spa por el día'), c.index('Ritual del Río'))

    def test_la_etiqueta_dice_los_dias_y_que_no_se_pernocta(self):
        """Sin los días llegan consultas para el sábado; sin lo de pernoctar,
        alguien cree que compró una noche a $200.000."""
        linea = next(l for l in self._carta().split('\n')
                     if 'Cabaña y spa por el día' in l)
        self.assertIn('lun/mié/jue', linea)
        self.assertIn('sin pernoctar', linea)

    def test_su_precio_es_plano_sin_desde(self):
        """No lleva «desde»: son $200.000 fijos, no un piso."""
        linea = next(l for l in self._carta().split('\n')
                     if 'Cabaña y spa por el día' in l)
        self.assertNotIn('desde', linea)
        self.assertIn('200.000', linea)
