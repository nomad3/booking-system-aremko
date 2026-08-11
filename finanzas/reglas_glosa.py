# -*- coding: utf-8 -*-
"""La lista de glosas que Jorge declaró «siempre Aremko» (2026-08-10).

Vive en la base, no en el código, porque la administra él. Este módulo es el
único lugar que la consulta, y la mantiene en memoria para no hacer una query
por cada línea de una cartola de 300 filas. El caché se bota solo cuando la
lista cambia (señal en signals.py) — así una regla nueva rige de inmediato,
sin reiniciar nada.
"""
_CACHE = {'reglas': None}


def invalidar_cache():
    _CACHE['reglas'] = None


def _leer_reglas():
    from .models import ReglaGlosa
    return list(ReglaGlosa.objects
                .filter(activa=True)
                .values_list('patron', 'categoria__clave'))


def reglas_activas():
    """[(patrón, clave de categoría)] de más largo a más corto.

    El orden importa: si alguien guarda «BCI» y también «BCI SEGUROS», gana el
    específico. Con el orden al revés, la regla ancha se comería a la fina.

    Si la tabla todavía no existe —código desplegado antes de correr la
    migración— se devuelve la lista vacía en vez de reventar: sin reglas todo
    queda POR CLASIFICAR, que es el lado seguro. El 2026-08-10 ese hueco dejó
    la carga de cartolas rota entre el deploy y la migración.
    """
    if _CACHE['reglas'] is None:
        from django.db import DatabaseError, transaction
        try:
            # El savepoint importa: en Postgres una consulta fallida aborta la
            # transacción entera, y esto corre DENTRO del atomic que escribe
            # los movimientos. Sin él, la cartola completa se caería.
            with transaction.atomic():
                filas = _leer_reglas()
        except DatabaseError:
            return []          # sin cachear: al migrar, rige de inmediato
        _CACHE['reglas'] = sorted(filas, key=lambda r: -len(r[0]))
    return _CACHE['reglas']


def categoria_por_glosa(descripcion):
    """Clave de la categoría si la glosa está en la lista; None si no.

    None significa POR CLASIFICAR, y es el resultado correcto la mayoría de
    las veces: en las cuentas de Jorge y Alda nada se asigna a Aremko salvo lo
    que él haya declarado acá.
    """
    d = (descripcion or '').upper()
    if not d:
        return None
    for patron, clave in reglas_activas():
        if patron and patron in d:
            return clave
    return None


def patron_sugerido(descripcion):
    """La parte estable de una glosa, para proponerla como patrón.

    Los bancos meten números que cambian mes a mes («Prima Seguro
    2024092601642», «Tef A Martin Aguilera Toloza 777021»). Guardar la glosa
    entera haría que la regla no calzara nunca más. Se sacan los números y la
    basura de separadores, y queda lo que se repite.
    """
    import re

    d = (descripcion or '').upper()
    # Las cartolas propias vienen con el prefijo de la cuenta; no es parte de
    # la glosa del comercio y ensuciaría el patrón.
    d = re.sub(r'^CARTOLA [A-Z_ ]+?:\s*', '', d)
    d = re.sub(r'\d+', ' ', d)
    d = re.sub(r'[^A-ZÑÁÉÍÓÚ ]+', ' ', d)
    palabras = [p for p in d.split() if len(p) > 1]
    # Tres palabras alcanzan para identificar un comercio sin amarrarse a la
    # cola variable de la glosa.
    return ' '.join(palabras[:3])[:120]
