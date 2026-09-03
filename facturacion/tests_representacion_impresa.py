"""La representación impresa de la boleta y su timbre PDF417 — punto 9 de la
Declaración de Cumplimiento del SII.

Lo que se prueba acá no son preferencias nuestras: son las reglas del
instructivo técnico del SII (Anexo 2). Romperlas produce un timbre que se ve
bien pero que un lector rechaza — el peor tipo de falla, porque no avisa.

Las dos más fáciles de romper sin notarlo:

1. El TED se firma sobre el string SIN blancos ENTRE tags (A.2.4). Nuestro
   XML guardado SÍ tiene saltos de línea e indentación. Si se codificara tal
   cual, un verificador estricto reconstruiría un string distinto del firmado.
2. El contenido DENTRO de un elemento terminal no se toca. Si al normalizar
   se comieran los espacios de «Cabaña El Ciprés», el timbre dejaría de
   corresponder al documento firmado.

Ejecutar:
    python manage.py test facturacion.tests_representacion_impresa
"""
from __future__ import annotations

import base64
import io
import re

from django.test import TestCase

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import representacion_impresa as ri


# Un DTE con la misma forma que los reales — CAF y firmas del largo real
# (copiados del folio 33 de producción), con indentación y un ítem con
# espacios. El largo importa: con un CAF de juguete el TED daba 540 caracteres
# y cabía en 6 columnas, escondiendo el tope de 90 filas del PDF417 que sí
# aparece con el TED real de ~720.
XML_DTE = """<?xml version="1.0" encoding="ISO-8859-1"?>
<DTE version="1.0">
  <Documento ID="T_1">
    <Encabezado>
      <IdDoc>
        <TipoDTE>39</TipoDTE>
        <Folio>33</Folio>
        <FchEmis>2026-09-02</FchEmis>
        <IndServicio>3</IndServicio>
      </IdDoc>
      <Emisor>
        <RUTEmisor>76485192-7</RUTEmisor>
        <RznSocEmisor>AREMKO HOTEL SPA</RznSocEmisor>
        <GiroEmisor>Arriendo de Alojamiento, tinas, masajes y sauna</GiroEmisor>
        <DirOrigen>RIO PESCADO KM 4 PARCELA 3</DirOrigen>
        <CmnaOrigen>Puerto Varas</CmnaOrigen>
      </Emisor>
      <Receptor>
        <RUTRecep>66666666-6</RUTRecep>
        <RznSocRecep>Consumidor final</RznSocRecep>
      </Receptor>
      <Totales>
        <MntNeto>2941</MntNeto>
        <IVA>559</IVA>
        <MntTotal>3500</MntTotal>
      </Totales>
    </Encabezado>
    <Detalle>
      <NroLinDet>1</NroLinDet>
      <NmbItem>Cabana El Cipres con tina</NmbItem>
      <QtyItem>5</QtyItem>
      <UnmdItem>Kg</UnmdItem>
      <PrcItem>700</PrcItem>
      <MontoItem>3500</MontoItem>
    </Detalle>
    <TED version="1.0">
      <DD>
        <RE>76485192-7</RE>
        <TD>39</TD>
        <F>33</F>
        <FE>2026-09-02</FE>
        <RR>66666666-6</RR>
        <RSR>Consumidor final</RSR>
        <MNT>3500</MNT>
        <IT1>Cabana El Cipres con tina</IT1>
        <CAF version="1.0">
          <DA>
            <RE>76485192-7</RE>
            <RS>AREMKO HOTEL SPA</RS>
            <TD>39</TD>
            <RNG><D>1</D><H>50</H></RNG>
            <FA>2026-07-12</FA>
            <RSAPK><M>wWVsTSO6ZFf5rm73zeSvvORc6Gta8DnS+Enu+bjiX8L8eI+lYGizXZmTcHeSXDw4MpqPkhDOAPtjAwTvOz+4nQ==</M><E>Aw==</E></RSAPK>
            <IDK>100</IDK>
          </DA>
          <FRMA algoritmo="SHA1withRSA">vWDgPfVBwlnr+w6ooE01jWQqANxFVZ63aqzMhCUjnF64snttYkmzRap/9ayuSkjRIU2dJFnE1Fi78teOTET35g==</FRMA>
        </CAF>
        <TSTED>2026-09-02T09:52:36</TSTED>
      </DD>
      <FRMT algoritmo="SHA1withRSA">iUR+WXuxoKcHbGlhNhHqU6eDCQf1VqFXVKCUyQl8FpwV4WXgIkYeLuJyU3xf9R5T1nspGmDmj5CVc/hOvgbRzA==</FRMT>
    </TED>
  </Documento>
</DTE>"""


def _boleta(xml=XML_DTE, ambiente='produccion', estado='aceptada', folio=33):
    return BoletaElectronica.objects.create(
        pago=None, tipo_dte=39, ambiente=ambiente, folio=folio,
        monto_total=3500, monto_neto=2941, monto_iva=559,
        glosa='prueba', estado=estado, xml_dte=xml)


class ElTedSeExtraeComoFueFirmado(TestCase):
    def test_elimina_los_blancos_entre_tags(self):
        # Regla A.2.4 del SII: la firma se calculó sobre el string sin los
        # caracteres entre el cierre de un tag y la apertura del siguiente.
        ted = ri.extraer_ted(XML_DTE)
        self.assertNotIn('>\n', ted)
        self.assertNotIn('> <', ted)
        self.assertIn('</RE><TD>', ted)

    def test_conserva_el_contenido_de_los_elementos_terminales(self):
        # Lo que va ENTRE el tag de inicio y el de fin NO se toca: si se
        # comieran estos espacios, el timbre dejaría de corresponder al
        # documento firmado.
        ted = ri.extraer_ted(XML_DTE)
        self.assertIn('<IT1>Cabana El Cipres con tina</IT1>', ted)
        self.assertIn('<RSR>Consumidor final</RSR>', ted)

    def test_empieza_y_termina_en_el_ted(self):
        ted = ri.extraer_ted(XML_DTE)
        self.assertTrue(ted.startswith('<TED'))
        self.assertTrue(ted.endswith('</TED>'))

    def test_incluye_el_caf_y_la_firma(self):
        # Sin el CAF adentro, el timbre no prueba que el folio esté autorizado.
        ted = ri.extraer_ted(XML_DTE)
        self.assertIn('<CAF', ted)
        self.assertIn('<FRMT', ted)

    def test_una_boleta_sin_xml_falla_con_mensaje_claro(self):
        with self.assertRaises(ri.SinTimbre):
            ri.extraer_ted('')

    def test_un_xml_sin_ted_falla_con_mensaje_claro(self):
        with self.assertRaises(ri.SinTimbre):
            ri.extraer_ted('<DTE><Documento></Documento></DTE>')


class ElTimbreCumpleLosParametrosDelSii(TestCase):
    def test_usa_nivel_de_correccion_5(self):
        # El instructivo (A.2.5) exige ECL nivel 5, no el default de la librería.
        self.assertEqual(ri.NIVEL_CORRECCION, 5)

    def test_usa_relacion_3_a_1(self):
        # Row Height : X Width = 3:1, exigido por el SII.
        self.assertEqual(ri.RATIO_ALTO_ANCHO, 3)

    def test_las_medidas_impresas_respetan_los_limites_del_sii(self):
        # Mínimo 2x5 cm, máximo 3x9 cm. Fuera de ahí el timbre es rechazable.
        t = ri.generar_timbre(ri.extraer_ted(XML_DTE))
        self.assertLessEqual(t['alto_cm'], ri.ALTO_MAX_CM)
        self.assertGreaterEqual(t['alto_cm'], ri.ALTO_MIN_CM)
        self.assertLessEqual(t['ancho_cm'], ri.ANCHO_MAX_CM)
        self.assertGreaterEqual(t['ancho_cm'], ri.ANCHO_MIN_CM)

    def test_el_timbre_no_se_deforma(self):
        # Las medidas en cm deben tener la MISMA proporción que la imagen: si
        # se desviaran, el PDF417 saldría estirado y un lector lo rechazaría.
        from PIL import Image
        t = ri.generar_timbre(ri.extraer_ted(XML_DTE))
        img = Image.open(io.BytesIO(base64.b64decode(t['png_base64'])))
        proporcion_imagen = img.width / img.height
        proporcion_impresa = t['ancho_cm'] / t['alto_cm']
        self.assertAlmostEqual(proporcion_imagen, proporcion_impresa, delta=0.05)

    def test_un_ted_largo_tambien_cabe(self):
        # El largo del TED varía con el nombre del servicio. Con columnas fijas
        # un nombre largo producía un código más alto que ancho.
        largo = XML_DTE.replace(
            '<IT1>Cabana El Cipres con tina</IT1>',
            '<IT1>Noche de ritual junto al rio para dos personas con desayuno</IT1>')
        t = ri.generar_timbre(ri.extraer_ted(largo))
        self.assertLessEqual(t['alto_cm'], ri.ALTO_MAX_CM)
        self.assertGreater(t['ancho_cm'], t['alto_cm'])

    def test_un_ted_del_largo_real_no_revienta(self):
        # El PDF417 tiene un tope duro de 90 filas. Con pocas columnas un TED
        # real no cabe y la librería lanza ValueError: hay que seguir probando
        # con más columnas, no abortar. Se descubrió en producción — el fixture
        # anterior era más corto que un TED real y no lo alcanzaba.
        ted = ri.extraer_ted(XML_DTE)
        self.assertGreater(len(ted), 700, 'el fixture dejó de ser realista')
        t = ri.generar_timbre(ted)          # no debe lanzar
        self.assertGreater(t['columnas'], 6)

    def test_codifica_en_binario_y_no_en_texto(self):
        # El SII exige byte compaction mode «para evitar problemas con los
        # caracteres especiales». En pdf417gen eso se activa pasando BYTES;
        # si se pasara str, la librería elegiría modo texto.
        capturado = {}
        from pdf417gen import encode as encode_real

        def espia(data, **kw):
            capturado['tipo'] = type(data)
            capturado['nivel'] = kw.get('security_level')
            return encode_real(data, **kw)

        import pdf417gen
        pdf417gen.encode = espia
        try:
            ri.generar_timbre(ri.extraer_ted(XML_DTE))
        finally:
            pdf417gen.encode = encode_real
        self.assertIs(capturado['tipo'], bytes)
        self.assertEqual(capturado['nivel'], 5)

    def test_genera_un_png_valido(self):
        from PIL import Image
        t = ri.generar_timbre(ri.extraer_ted(XML_DTE))
        img = Image.open(io.BytesIO(base64.b64decode(t['png_base64'])))
        self.assertEqual(img.format, 'PNG')
        # Apaisado, como corresponde a un timbre de 3 cm de alto por 9 de ancho.
        self.assertGreater(img.width, img.height)


class LosDatosSalenDelXmlFirmado(TestCase):
    def setUp(self):
        self.d = ri.datos_para_impresion(_boleta())

    def test_toma_folio_y_fecha_del_documento(self):
        self.assertEqual(self.d['folio'], '33')
        self.assertEqual(self.d['fecha_emision'], '2026-09-02')

    def test_toma_los_datos_del_emisor(self):
        self.assertEqual(self.d['emisor']['rut'], '76485192-7')
        self.assertEqual(self.d['emisor']['razon_social'], 'AREMKO HOTEL SPA')
        self.assertEqual(self.d['emisor']['comuna'], 'Puerto Varas')

    def test_toma_los_totales(self):
        self.assertEqual(self.d['totales']['neto'], 2941)
        self.assertEqual(self.d['totales']['iva'], 559)
        self.assertEqual(self.d['totales']['total'], 3500)

    def test_toma_el_detalle(self):
        self.assertEqual(len(self.d['detalles']), 1)
        self.assertEqual(self.d['detalles'][0]['nombre'], 'Cabana El Cipres con tina')
        self.assertEqual(self.d['detalles'][0]['monto'], '3500')

    def test_prefiere_el_xml_por_sobre_los_campos_del_modelo(self):
        # Si la BD y el documento firmado difirieran, manda el firmado: es lo
        # que existe ante el SII.
        b = _boleta()
        b.monto_total = 999999          # se desvía del XML a propósito
        b.save()
        d = ri.datos_para_impresion(b)
        self.assertEqual(d['totales']['total'], 3500)

    def test_desescapa_las_entidades_xml(self):
        xml = XML_DTE.replace('AREMKO HOTEL SPA', 'Aremko &amp; Spa')
        d = ri.datos_para_impresion(_boleta(xml=xml))
        self.assertEqual(d['emisor']['razon_social'], 'Aremko & Spa')


class LaPaginaImpresa(TestCase):
    def _html(self, boleta):
        from django.template.loader import render_to_string
        config = ConfiguracionFacturacion.get()
        return render_to_string('facturacion/boleta_impresa.html', {
            'd': ri.datos_para_impresion(boleta),
            'unidad_sii': (config.unidad_sii or config.comuna or '').upper(),
            'url_verificacion': 'www.aremko.cl/boletas/consulta/',
        })

    def test_muestra_los_datos_obligatorios(self):
        html = self._html(_boleta())
        for esperado in ('AREMKO HOTEL SPA', '76485192-7', 'BOLETA ELECTRÓNICA',
                         'N° 33', '2026-09-02', 'Cabana El Cipres con tina'):
            self.assertIn(esperado, html)

    def test_lleva_la_leyenda_del_timbre(self):
        # El manual de muestras impresas la exige debajo del código.
        self.assertIn('Timbre Electrónico SII', self._html(_boleta()))

    def test_lleva_el_timbre_incrustado(self):
        self.assertIn('data:image/png;base64,', self._html(_boleta()))

    def test_el_timbre_lleva_medidas_en_centimetros(self):
        # En cm y no en píxeles: los límites del SII son físicos, sobre papel.
        html = self._html(_boleta())
        self.assertRegex(html, r'width: [\d.]+cm; height: [\d.]+cm')

    def test_el_css_del_timbre_usa_punto_decimal(self):
        # Django localiza los decimales: en español «9.0» se imprime «9,0», que
        # es CSS inválido. El visor lo descarta sin avisar y el timbre sale a
        # su tamaño en píxeles, fuera de las medidas del SII.
        html = self._html(_boleta())
        self.assertNotRegex(html, r'width: [\d]+,[\d]+cm')
        self.assertNotRegex(html, r'height: [\d]+,[\d]+cm')

    def test_no_muestra_rut_generico_del_consumidor_final(self):
        # 66666666-6 es el comodín de "consumidor final": imprimirlo confunde.
        html = self._html(_boleta())
        self.assertIn('Consumidor final', html)
        self.assertNotIn('R.U.T. 66666666-6', html)


class QuienPuedeVerla(TestCase):
    def test_el_cliente_ve_su_boleta_real(self):
        b = _boleta(ambiente='produccion', estado='aceptada')
        r = self.client.get(f'/boletas/b/{b.token_consulta}/impresa/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_una_boleta_de_certificacion_no_se_publica(self):
        # Un documento sin valor tributario en manos de un cliente, presentado
        # como si lo tuviera, es exactamente lo que el SII revisa acá.
        b = _boleta(ambiente='certificacion', estado='aceptada')
        r = self.client.get(f'/boletas/b/{b.token_consulta}/impresa/')
        self.assertEqual(r.status_code, 404)

    def test_una_boleta_simulada_no_se_publica(self):
        b = _boleta(ambiente='produccion', estado='simulada')
        r = self.client.get(f'/boletas/b/{b.token_consulta}/impresa/')
        self.assertEqual(r.status_code, 404)

    def test_la_vista_de_staff_pide_sesion(self):
        b = _boleta()
        r = self.client.get(f'/boletas/{b.pk}/impresa/')
        self.assertIn(r.status_code, (302, 403))

    def test_el_cliente_encuentra_el_boton_en_su_pagina_de_consulta(self):
        # Un PDF al que solo se llega escribiendo la URL a mano no le sirve
        # a nadie: el cliente entra por su enlace de consulta.
        b = _boleta(ambiente='produccion', estado='aceptada')
        html = self.client.get(f'/boletas/b/{b.token_consulta}/').content.decode()
        self.assertIn(f'/boletas/b/{b.token_consulta}/impresa/', html)

    def test_una_boleta_sin_folio_no_ofrece_pdf(self):
        # Sin folio no está timbrada: no hay timbre que imprimir.
        b = _boleta(ambiente='produccion', estado='aceptada', folio=None)
        html = self.client.get(f'/boletas/b/{b.token_consulta}/').content.decode()
        self.assertNotIn('Descargar boleta en PDF', html)

    def test_una_boleta_sin_timbre_avisa_en_vez_de_reventar(self):
        b = _boleta(xml='', ambiente='produccion', estado='aceptada')
        r = self.client.get(f'/boletas/b/{b.token_consulta}/impresa/')
        self.assertEqual(r.status_code, 409)
        self.assertIn('no se puede imprimir', r.content.decode().lower())
