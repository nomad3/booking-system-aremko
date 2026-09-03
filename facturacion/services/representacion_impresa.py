"""Representación gráfica e impresa de la boleta electrónica — punto 9 de la
Declaración de Cumplimiento del SII.

El corazón de esto es el TIMBRE: el código de barras PDF417 que permite a
cualquiera (incluido un fiscalizador con un lector) verificar que el folio
está autorizado y que el documento no fue alterado. No se calcula nada nuevo
acá — el TED ya viene firmado dentro del XML que guardamos al timbrar. Lo que
falta es extraerlo, dibujarlo y maquetar la hoja.

Los parámetros NO son elegidos por nosotros: salen del instructivo técnico del
SII (Anexo 2, A.2.5 «Reglas Para La Generación e Impresión Del Timbre
PDF417»), y desviarse de ellos produce un timbre que un lector rechaza:

· Modo de codificación BINARIO (byte compaction) — exigido explícitamente
  «para evitar problemas con los caracteres especiales».
· Error Correction Level 5.
· Row Height / X Width en relación 3:1.
· Quiet Zone de 0,25 pulgadas en los cuatro lados (se aplica en el CSS, en
  centímetros, para que sea verificable con una regla sobre el papel).
· Sin «truncated» (aumenta la sensibilidad al daño).
· Tamaño impreso recomendado: máximo 3 cm de alto × 9 cm de ancho.

Y el detalle que arruina el timbre en silencio si se ignora (A.2.4): la firma
del TED se calculó sobre el string SIN los blancos ni saltos de línea que van
ENTRE tags. Si codificáramos el TED con la indentación con que lo guardamos,
un verificador estricto obtendría un string distinto del firmado. Por eso
`extraer_ted` normaliza exactamente eso — y solo eso: lo que va entre el tag
de inicio y el de cierre de un elemento terminal NO se toca.
"""
import base64
import io
import re

# Del instructivo técnico del SII (A.2.5). No son preferencias nuestras.
NIVEL_CORRECCION = 5
RATIO_ALTO_ANCHO = 3      # Row Height : X Width = 3:1
ESCALA = 3                # píxeles por módulo; el tamaño físico lo fija el CSS

# Límites físicos del timbre impreso: mínimo 2 × 5 cm, máximo recomendado
# 3 × 9 cm (manual de muestras impresas + A.2.5).
ANCHO_MAX_CM = 9.0
ANCHO_MIN_CM = 5.0
ALTO_MAX_CM = 3.0
ALTO_MIN_CM = 2.0

# El número de columnas NO puede ser fijo: define la proporción del código, y
# el largo del TED varía con el nombre del primer ítem («Tina» vs «Noche de
# ritual junto al río para dos personas»). Con columnas fijas, un servicio de
# nombre largo produce un código más alto que ancho, que al forzarlo a 9×3 cm
# en el CSS se deforma hasta volverse ilegible — falla que no avisa, porque el
# PDF se ve perfecto. Se eligen midiendo el código real.
COLUMNAS_CANDIDATAS = range(6, 31)

# El SII exige ISO-8859-1 en el timbre y advierte que las librerías no deben
# transformarlo (por ejemplo a UTF-8) o la verificación de la firma falla.
ENCODING_SII = 'ISO-8859-1'


class SinTimbre(Exception):
    """La boleta no tiene un TED que imprimir (simulada, pendiente o en error)."""


def extraer_ted(xml_dte):
    """El TED tal como fue firmado: sin blancos ni saltos ENTRE tags.

    Regla del SII (A.2.4): «La firma del TED se realiza sobre el string
    resultante de eliminar todos los caracteres que están entre el tag de
    cierre de un elemento y el tag de inicio del siguiente, sin modificar la
    información que va entre el tag de inicio y el tag de fin de los elementos
    terminales».
    """
    if not xml_dte:
        raise SinTimbre('La boleta no tiene XML: no se puede imprimir su timbre.')
    encontrado = re.search(r'<TED\b.*?</TED>', xml_dte, re.S)
    if not encontrado:
        raise SinTimbre('El XML de la boleta no contiene un TED.')
    return re.sub(r'>\s+<', '><', encontrado.group(0)).strip()


def generar_timbre(ted):
    """El PDF417 del timbre, con las medidas en cm a las que debe imprimirse.

    Devuelve {'png_base64', 'ancho_cm', 'alto_cm', 'columnas'}. Las medidas se
    calculan del código realmente generado y no se fijan en el CSS: así el
    timbre nunca se estira ni se aplasta, que es lo que lo volvería ilegible.

    Se codifica en BYTES a propósito: eso activa el byte compaction mode que
    el SII exige, y evita que la librería reinterprete los acentos.
    """
    from pdf417gen import encode, render_image

    datos = ted.encode(ENCODING_SII, errors='replace')

    # Se prueban proporciones reales, de menos a más columnas (el código se va
    # achatando), y se toma la primera que entra en el alto máximo.
    elegida = None
    for columnas in COLUMNAS_CANDIDATAS:
        try:
            codigos = encode(datos, columns=columnas, security_level=NIVEL_CORRECCION)
        except ValueError:
            # El PDF417 tiene un tope duro de 90 filas: con pocas columnas un
            # TED real (~720 caracteres con el CAF de producción adentro) no
            # cabe y la librería aborta. No es un error — es la señal de que
            # hacen falta más columnas, así que se sigue probando.
            continue
        medida = render_image(codigos, scale=1, ratio=RATIO_ALTO_ANCHO, padding=2)
        proporcion = medida.width / medida.height
        if ANCHO_MAX_CM / proporcion <= ALTO_MAX_CM:
            elegida = (columnas, proporcion)
            break
    if elegida is None:
        # TED tan largo que ni 30 columnas lo achatan: se imprime lo más ancho
        # posible y se acepta el alto que salga. Preferible a no imprimir el
        # timbre, que dejaría el documento sin su elemento obligatorio.
        codigos = encode(datos, columns=30, security_level=NIVEL_CORRECCION)
        medida = render_image(codigos, scale=1, ratio=RATIO_ALTO_ANCHO, padding=2)
        elegida = (30, medida.width / medida.height)

    columnas = elegida[0]
    codigos = encode(datos, columns=columnas, security_level=NIVEL_CORRECCION)
    imagen = render_image(codigos, scale=ESCALA, ratio=RATIO_ALTO_ANCHO, padding=2)

    # La proporción se toma de la imagen FINAL, no de la de tanteo: el padding
    # pesa distinto según la escala, y usar la proporción equivocada estiraría
    # el código lo justo para volverlo dudoso ante un lector.
    proporcion = imagen.width / imagen.height
    ancho_cm, alto_cm = ANCHO_MAX_CM, ANCHO_MAX_CM / proporcion
    if alto_cm < ALTO_MIN_CM:
        # Demasiado achatado: se agranda hasta el alto mínimo, sin pasarse del
        # ancho máximo (el SII fija ambos límites, no uno solo).
        alto_cm = ALTO_MIN_CM
        ancho_cm = min(ANCHO_MAX_CM, ALTO_MIN_CM * proporcion)

    buffer = io.BytesIO()
    imagen.save(buffer, format='PNG')
    return {
        'png_base64': base64.b64encode(buffer.getvalue()).decode('ascii'),
        'ancho_cm': round(ancho_cm, 2),
        'alto_cm': round(alto_cm, 2),
        'columnas': columnas,
        # El CSS se arma ACÁ y no en la plantilla a propósito: Django localiza
        # los decimales y en español imprimiría «width: 9,0cm», que es CSS
        # inválido. El navegador lo descarta en silencio y el timbre sale a su
        # tamaño natural en píxeles — fuera de las medidas del SII, sin que
        # nada avise. Formateado como string, el locale no lo toca.
        'estilo_css': f'width: {ancho_cm:.2f}cm; height: {alto_cm:.2f}cm;',
    }


def _texto(xml, tag, default=''):
    encontrado = re.search(rf'<{tag}>(.*?)</{tag}>', xml, re.S)
    if not encontrado:
        return default
    # Des-escapar las entidades XML predefinidas que el SII obliga a usar.
    valor = encontrado.group(1).strip()
    for entidad, caracter in (('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                              ('&quot;', '"'), ('&apos;', "'")):
        valor = valor.replace(entidad, caracter)
    return valor


def datos_para_impresion(boleta):
    """Los datos que van en la hoja, leídos del XML FIRMADO.

    Se parsea el XML y no los campos del modelo a propósito: el XML es lo que
    efectivamente se emitió y timbró. Si alguna vez difirieran (un ajuste
    manual en la BD, por ejemplo), lo que vale ante el SII es el documento
    firmado — y la representación impresa tiene que reflejar ESE.
    """
    xml = boleta.xml_dte or ''
    ted = extraer_ted(xml)

    encabezado = re.search(r'<Encabezado>.*?</Encabezado>', xml, re.S)
    encabezado = encabezado.group(0) if encabezado else ''
    emisor = re.search(r'<Emisor>.*?</Emisor>', encabezado, re.S)
    emisor = emisor.group(0) if emisor else ''
    receptor = re.search(r'<Receptor>.*?</Receptor>', encabezado, re.S)
    receptor = receptor.group(0) if receptor else ''
    totales = re.search(r'<Totales>.*?</Totales>', encabezado, re.S)
    totales = totales.group(0) if totales else ''

    detalles = []
    for bloque in re.findall(r'<Detalle>.*?</Detalle>', xml, re.S):
        detalles.append({
            'nombre': _texto(bloque, 'NmbItem'),
            'cantidad': _texto(bloque, 'QtyItem', '1'),
            'unidad': _texto(bloque, 'UnmdItem'),
            'precio': _texto(bloque, 'PrcItem'),
            'monto': _texto(bloque, 'MontoItem'),
        })

    def entero(valor):
        try:
            return int(valor)
        except (TypeError, ValueError):
            return 0

    return {
        'folio': _texto(encabezado, 'Folio'),
        'fecha_emision': _texto(encabezado, 'FchEmis'),
        'emisor': {
            'rut': _texto(emisor, 'RUTEmisor'),
            'razon_social': _texto(emisor, 'RznSocEmisor'),
            'giro': _texto(emisor, 'GiroEmisor'),
            'direccion': _texto(emisor, 'DirOrigen'),
            'comuna': _texto(emisor, 'CmnaOrigen'),
        },
        'receptor': {
            'rut': _texto(receptor, 'RUTRecep'),
            'razon_social': _texto(receptor, 'RznSocRecep'),
        },
        'totales': {
            'neto': entero(_texto(totales, 'MntNeto')),
            'iva': entero(_texto(totales, 'IVA')),
            'total': entero(_texto(totales, 'MntTotal')),
            'exento': entero(_texto(totales, 'MntExe')),
        },
        'detalles': detalles,
        'timbre': generar_timbre(ted),
    }
