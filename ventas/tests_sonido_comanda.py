"""El aviso sonoro de comanda en la Agenda Operativa.

Caso real (Jorge, 2026-08-02): "ahora se produce uno que es demasiado suave y
muchas veces no nos damos cuenta que se generó una comanda".

Dos causas, no una:

1. **Muchas veces no sonaba NADA.** Cada aviso creaba un `AudioContext` nuevo
   desde el temporizador del polling. Sin un gesto previo del usuario ese
   contexto nace `suspended` y no emite. Además se acumulaban, y los
   navegadores topan en ~6 por página.
2. **Cuando sonaba, era flojo.** Una senoidal de 800 Hz que decae en 0,4 s no
   compite con la música de fondo de recepción — y el navegador no puede
   bajarle el volumen a esa música porque es otra aplicación.

Este archivo fija ambas cosas. Lo interesante es el test de forma de onda: los
parámetros se LEEN del template y se sintetiza la señal para medir pico y RMS.
Sirve de freno al reflejo de "súbele más el volumen": el intento anterior
(makeup 2.6) saturaba 237 muestras, que es exactamente el crujido que se quería
evitar. La ganancia real vino de sostener la nota, no de amplificarla.

Ejecutar:
    python manage.py test ventas.tests_sonido_comanda
"""
import io
import math
import os
import re

from django.conf import settings
from django.test import TestCase

FS = 44100
# Referencia medida del sonido anterior (senoidal 800 Hz, gain 0.3 → 0.01 en 0.4 s).
RMS_VIEJO_DBFS = -25.8


def _template():
    ruta = os.path.join(settings.BASE_DIR, 'ventas', 'templates', 'ventas',
                        'agenda_operativa.html')
    return io.open(ruta, encoding='utf-8').read()


def _bloque_audio(html):
    return html[html.index('// === Alerta de comanda'):
                html.index('// === Parpadeo del título')]


def _parametros(bloque):
    """Los valores REALES del template, para no medir una copia desactualizada."""
    voces = [(tipo, 0.5 if '/' in f else 1.0, float(pico))
             for tipo, f, pico in re.findall(
                 r"\['(\w+)',\s*(freq(?:\s*/\s*2)?),\s*([\d.]+)\]", bloque)]
    uno = lambda patron: float(re.search(patron, bloque).group(1))
    notas = re.findall(
        r'_notaComanda\(ctx, limitador, ([\d.]+), base(?: \+ ([\d.]+))?, ([\d.]+)\)',
        bloque)
    return {
        'voces': voces,
        'caida': uno(r'_CAIDA\s*=\s*([\d.]+)'),
        'thr': uno(r'threshold\.setValueAtTime\((-?[\d.]+)'),
        'ratio': uno(r'ratio\.setValueAtTime\(([\d.]+)'),
        'atk': uno(r'attack\.setValueAtTime\(([\d.]+)'),
        'rel': uno(r'release\.setValueAtTime\(([\d.]+)'),
        'makeup': uno(r'makeup\.gain\.setValueAtTime\(([\d.]+)'),
        'reps': int(uno(r'rep <\s*(\d+)')),
        'sep': uno(r'rep \* ([\d.]+)'),
        'notas': [(float(f), float(off or 0), float(d)) for f, off, d in notas],
    }


def _onda(tipo, freq, n0, n):
    """Formas ideales. Las del navegador son band-limited y sobrepasan un poco:
    por eso el umbral de pico del test deja margen bajo 1.0."""
    out = []
    for i in range(n):
        p = (freq * ((n0 + i) / FS)) % 1.0
        if tipo == 'sawtooth':
            out.append(2 * p - 1)
        elif tipo == 'square':
            out.append(1.0 if p < 0.5 else -1.0)
        elif tipo == 'triangle':
            out.append(4 * abs(p - 0.5) - 1)
        else:
            out.append(math.sin(2 * math.pi * p))
    return out


def _envolvente(n, dur, caida):
    """Ataque 12 ms → SOSTIENE → suelta en los últimos `caida` s."""
    e, t_caida = [], max(dur - caida, 0.02)
    for i in range(n):
        t = i / FS
        if t < 0.012:
            e.append(0.0001 + (1 - 0.0001) * (t / 0.012))
        elif t < t_caida:
            e.append(1.0)
        elif t < dur:
            e.append(max(0.001, 0.001 ** ((t - t_caida) / caida)))
        else:
            e.append(0.001)
    return e


def _limitador(x, p):
    """Modelo feed-forward del DynamicsCompressor (knee 0) + makeup."""
    a_atk = math.exp(-1 / (p['atk'] * FS))
    a_rel = math.exp(-1 / (p['rel'] * FS))
    red, out = 0.0, []
    for v in x:
        nivel = abs(v)
        db = 20 * math.log10(nivel) if nivel > 1e-9 else -200
        objetivo = (db - p['thr']) * (1 - 1 / p['ratio']) if db > p['thr'] else 0.0
        red = objetivo + (a_atk if objetivo > red else a_rel) * (red - objetivo)
        out.append(v * (10 ** (-red / 20)) * p['makeup'])
    return out


def _sintetizar(p):
    eventos = [(f, 0.02 + rep * p['sep'] + off, d)
               for rep in range(p['reps']) for f, off, d in p['notas']]
    largo = max(t0 + d for _, t0, d in eventos) + 0.2
    buf = [0.0] * int(FS * largo)
    for freq, t0, dur in eventos:
        n0, n = int(t0 * FS), int((dur + 0.03) * FS)
        env = _envolvente(n, dur, p['caida'])
        for tipo, mult, pico in p['voces']:
            w = _onda(tipo, freq * mult, n0, n)
            for i in range(n):
                if n0 + i < len(buf):
                    buf[n0 + i] += w[i] * env[i] * pico
    return _limitador(buf, p), largo


class MotorDeAudioTest(TestCase):
    """La causa #1: sonaba nada, no sonaba bajo."""

    @classmethod
    def setUpTestData(cls):
        cls.bloque = _bloque_audio(_template())

    def test_un_solo_contexto_reusado(self):
        # El bug era crear uno nuevo por aviso: nace suspendido y se acumulan.
        self.assertEqual(self.bloque.count('new AC()'), 1)
        self.assertIn('if (!audioCtx)', self.bloque)

    def test_se_desbloquea_con_el_primer_gesto(self):
        for evento in ("'click'", "'keydown'", "'touchstart'"):
            self.assertIn(evento, self.bloque)
        self.assertIn('once: true', self.bloque)

    def test_resume_defensivo_antes_de_cada_aviso(self):
        # Aunque el gesto ya haya ocurrido, el navegador puede volver a suspender.
        self.assertGreaterEqual(self.bloque.count("state === 'suspended'"), 2)

    def test_nunca_rompe_la_agenda(self):
        self.assertIn('try {', self.bloque)
        self.assertIn('catch (e)', self.bloque)


class FormaDeOndaTest(TestCase):
    """La causa #2, medida sobre la señal que realmente se va a emitir."""

    @classmethod
    def setUpTestData(cls):
        cls.p = _parametros(_bloque_audio(_template()))
        cls.señal, cls.largo = _sintetizar(cls.p)

    def test_NO_SATURA(self):
        """El freno al 'súbele más el volumen'. Con makeup 2.6 saturaba 237
        muestras; saturar cruje, y crujir es peor que sonar bajo."""
        saturadas = sum(1 for v in self.señal if abs(v) > 1.0)
        self.assertEqual(saturadas, 0, f'{saturadas} muestras saturadas')

    def test_deja_margen_para_el_overshoot_del_navegador(self):
        # Las ondas band-limited reales pasan un poco de la forma ideal.
        self.assertLess(max(abs(v) for v in self.señal), 0.9)

    def test_es_MUY_superior_al_sonido_viejo(self):
        rms = 20 * math.log10(
            math.sqrt(sum(v * v for v in self.señal) / len(self.señal)))
        self.assertGreater(rms - RMS_VIEJO_DBFS, 10.0,
                           f'solo {rms - RMS_VIEJO_DBFS:+.1f} dB sobre el viejo')

    def test_la_nota_SOSTIENE_no_es_un_punteo(self):
        """De aquí salió la ganancia real (+13 dB vs +6 del punteo). Si alguien
        borra el setValueAtTime del sostén, la envolvente vuelve a decaer sola."""
        self.assertIn('g.gain.setValueAtTime(voz[2],',
                      _bloque_audio(_template()))

    def test_dura_lo_suficiente_para_notarse(self):
        audible = sum(1 for v in self.señal if abs(v) > 0.05) / FS
        self.assertGreater(audible, 0.8)   # el viejo: 0.24 s
        self.assertLess(self.largo, 3.0)   # pero sin volverse molesto


class AvisoVisualTest(TestCase):
    """El sonido igual se puede perder: refuerzo por pestaña y polling más corto."""

    @classmethod
    def setUpTestData(cls):
        cls.html = _template()

    def test_polling_cada_10_segundos(self):
        self.assertIn('setInterval(pollComandas, 10000)', self.html)

    def test_el_titulo_parpadea_al_entrar_una_comanda(self):
        self.assertIn('marcarComandasPendientes', self.html)
        self.assertIn('_parpadeoTitulo = setInterval', self.html)

    def test_se_calma_al_volver_a_la_pestana(self):
        self.assertIn("addEventListener('visibilitychange'", self.html)
        self.assertIn('if (!document.hidden) detenerParpadeoTitulo();', self.html)

    def test_el_titulo_original_se_restaura(self):
        # Si no, la pestaña queda con "¡COMANDA NUEVA!" para siempre.
        self.assertIn('document.title = TITULO_ORIGINAL;', self.html)

    def test_hay_boton_para_probar_el_sonido(self):
        self.assertIn('probarSonidoComanda()', self.html)
        self.assertIn('Probar sonido', self.html)
