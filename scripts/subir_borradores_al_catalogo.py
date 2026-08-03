#!/usr/bin/env python3
"""
Sube al catálogo las fotos que quedaron a medio catalogar en el disco.

El banco del disco y el catálogo de la nube se separaron con el tiempo: hay 88
fotos en los dos, 72 que se subieron directo a la nube, y otras que quedaron en
el disco en estado `borrador_v2` — catalogadas a medias y nunca subidas. Esas
últimas son material real que hoy no puede usar nadie.

Este script las sube. **La taxonomía ya está hecha en el disco**, así que no se
vuelve a inventar: se manda tal cual, con el estado en «revisar» para que la
apruebe una persona desde el panel.

Tres cosas que resuelve por el camino:

1. **El HEIC no se puede subir.** La ingesta acepta jpg/png/webp, y casi la
   mitad de las fotos del iPhone son HEIC. Se convierten con `sips`, que viene
   en macOS, sin instalar nada.
2. **Las masters pesan demasiado.** El límite son 16 MB y varias los pasan. Se
   redimensionan a 2400px de lado mayor, que es de sobra para una historia.
3. **Los videos quedan fuera.** El catálogo en la nube es de fotos; los 57
   videos del disco necesitan otro camino y no se tocan acá.

Corre en el computador que tiene el disco conectado, con la clave de la API:

    AREMKO_API_KEY=... python3 scripts/subir_borradores_al_catalogo.py --en-seco
    AREMKO_API_KEY=... python3 scripts/subir_borradores_al_catalogo.py
"""
import argparse
import json
import mimetypes
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid

BASE = "https://www.aremko.cl/marketing/api/catalogo/"
RAIZ = pathlib.Path("/Volumes/JAguilera/AREMKO")
SUBIBLES = {".jpg", ".jpeg", ".png", ".webp"}
# Guarda de marca: al catálogo solo entra material real. Un nombre no prueba
# nada, pero estos aparecen cuando el archivo salió de un generador, y es
# preferible dejar fuera una foto real que colar una sintética.
SUENA_A_GENERADA = ("generated", "midjourney", "dall", "chatgpt", "firefly",
                    "stable-diffusion", "nano-banana", "ai_generated")
LADO_MAYOR = 2400          # de sobra para una historia vertical
LIMITE = 15 * 1024 * 1024  # el endpoint corta en 16; se deja margen


def _multipart(campos: dict, archivo: pathlib.Path) -> tuple[bytes, str]:
    """El cuerpo de un POST con archivo, sin depender de `requests`."""
    borde = f"----aremko{uuid.uuid4().hex}"
    tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
    partes = []
    for k, v in campos.items():
        partes.append(f"--{borde}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    partes.append(
        f"--{borde}\r\nContent-Disposition: form-data; name=\"imagen\"; "
        f"filename=\"{archivo.name}\"\r\nContent-Type: {tipo}\r\n\r\n".encode())
    partes.append(archivo.read_bytes())
    partes.append(f"\r\n--{borde}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={borde}"


def _post(url: str, cuerpo: bytes, tipo: str, clave: str) -> dict:
    pedido = urllib.request.Request(url, data=cuerpo, method="POST",
                                    headers={"X-API-KEY": clave, "Content-Type": tipo})
    with urllib.request.urlopen(pedido, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def _preparar(origen: pathlib.Path, temp: pathlib.Path) -> pathlib.Path | None:
    """Deja el archivo listo para subir: convierte HEIC y achica lo que pesa.

    Devuelve la ruta a subir (la original si ya servía) o None si no se pudo.
    """
    ext = origen.suffix.lower()
    hay_que_convertir = ext not in SUBIBLES
    pesa_mucho = origen.stat().st_size > LIMITE
    if not hay_que_convertir and not pesa_mucho:
        return origen

    destino = temp / (origen.stem + ".jpg")
    r = subprocess.run(
        ["sips", "-s", "format", "jpeg", "--resampleHeightWidthMax", str(LADO_MAYOR),
         str(origen), "--out", str(destino)],
        capture_output=True)
    if r.returncode != 0 or not destino.exists():
        return None
    # Una master enorme puede seguir pasada después de un solo pase.
    if destino.stat().st_size > LIMITE:
        subprocess.run(["sips", "-s", "formatOptions", "60", str(destino)], capture_output=True)
    return destino if destino.stat().st_size <= LIMITE else None


def _ya_en_la_nube(clave: str) -> set[str]:
    nombres, off = set(), 0
    while True:
        pedido = urllib.request.Request(f"{BASE}?limit=200&offset={off}", headers={"X-API-KEY": clave})
        with urllib.request.urlopen(pedido, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        nombres |= {(c.get("archivo") or "").strip() for c in d["clips"]}
        off += 200
        if off >= d.get("total", 0):
            return nombres


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--en-seco", action="store_true", help="Contar sin subir nada.")
    ap.add_argument("--solo", type=int, default=0, help="Subir solo las primeras N.")
    ap.add_argument("--estado", default="borrador_v2",
                    help="Qué estado del disco subir (por defecto los borradores).")
    op = ap.parse_args()

    clave = os.environ.get("AREMKO_API_KEY", "")
    if not clave:
        print("Falta AREMKO_API_KEY en el entorno.", file=sys.stderr)
        return 1
    if not RAIZ.exists():
        print(f"No encuentro {RAIZ}. ¿Está conectado el disco?", file=sys.stderr)
        return 1

    catalogo = json.loads((RAIZ / "catalogo.json").read_text())
    catalogo = catalogo if isinstance(catalogo, list) else catalogo.get("clips", catalogo)

    # Índice de lo que existe de verdad en el disco: el catálogo tiene entradas
    # cuyo archivo ya no está donde decía.
    reales: dict[str, pathlib.Path] = {}
    for p in RAIZ.rglob("*"):
        if p.is_file():
            reales.setdefault(p.name, p)

    en_nube = _ya_en_la_nube(clave)
    pendientes, videos, sin_archivo, generadas = [], 0, 0, []
    for c in catalogo:
        if c.get("estado") != op.estado:
            continue
        nombre = (c.get("archivo") or "").strip()
        if not nombre:
            continue
        ruta = reales.get(nombre)
        if ruta is None:
            sin_archivo += 1
            continue
        if c.get("tipo") == "video" or ruta.suffix.lower() in {".mp4", ".mov", ".m4v"}:
            videos += 1
            continue
        if any(p in nombre.lower() for p in SUENA_A_GENERADA):
            generadas.append(nombre)
            continue
        # El nombre con el que va a quedar en la nube: si hay que convertirlo,
        # es el .jpg. Sin esto, volver a correr el script re-subiría todo.
        final = nombre if ruta.suffix.lower() in SUBIBLES else ruta.stem + ".jpg"
        if final in en_nube or nombre in en_nube:
            continue
        pendientes.append((c, ruta, final))

    if op.solo:
        pendientes = pendientes[:op.solo]

    print(f"{len(pendientes)} foto(s) para subir · {videos} video(s) que este catálogo no "
          f"acepta · {sin_archivo} del catálogo sin archivo en el disco")
    if generadas:
        print(f"  {len(generadas)} fuera por parecer generadas (al catálogo solo entra "
              f"material real): {', '.join(generadas[:3])}"
              + (" …" if len(generadas) > 3 else ""))
    if op.en_seco or not pendientes:
        return 0

    subidas = fallaron = 0
    with tempfile.TemporaryDirectory() as tmp:
        temp = pathlib.Path(tmp)
        for i, (c, ruta, final) in enumerate(pendientes, 1):
            listo = _preparar(ruta, temp)
            if listo is None:
                print(f"  [{i}/{len(pendientes)}] {ruta.name}: no se pudo preparar")
                fallaron += 1
                continue
            try:
                cuerpo, tipo = _multipart({}, listo)
                sub = _post(BASE + "ingesta/", cuerpo, tipo, clave)
                # La taxonomía del disco manda: el trabajo de catalogar ya está
                # hecho y el borrador de la IA no tiene por qué pisarlo.
                guardar = {
                    "archivo": final,
                    "cloud_url": sub["cloud_url"],
                    "tipo": "foto",
                    "area": c.get("area") or "detalle",
                    "momento": c.get("momento") or "indistinto",
                    "estacion": c.get("estacion") or "indistinto",
                    "vapor": c.get("vapor") or "no",
                    "decoracion": c.get("decoracion") or "",
                    "personas": bool(c.get("personas")),
                    # El catálogo del disco tiene «baja» y el de la nube no la
                    # acepta —solo alta o media—. Entra como media: llega en
                    # «revisar» igual, así que el que decide si sirve la mira.
                    "calidad": {"baja": "media"}.get(c.get("calidad"), c.get("calidad") or "media"),
                    "descripcion": (c.get("descripcion") or "")[:300],
                    "etiquetas": c.get("etiquetas") or [],
                    "apto_para": c.get("apto_para") or [],
                    "orientacion": c.get("orientacion") or sub.get("draft", {}).get("orientacion", ""),
                    # Llegan sin aprobar: catalogado a medias no es revisado.
                    "estado": "revisar",
                    "fuente": "disco_borradores",
                    "origen": ruta.name if ruta.name != final else "",
                }
                _post(BASE, json.dumps(guardar).encode(), "application/json", clave)
                subidas += 1
                print(f"  [{i}/{len(pendientes)}] {final} ✓")
            except urllib.error.HTTPError as e:
                fallaron += 1
                print(f"  [{i}/{len(pendientes)}] {ruta.name}: HTTP {e.code} "
                      f"{e.read().decode()[:120]}")
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                fallaron += 1
                print(f"  [{i}/{len(pendientes)}] {ruta.name}: {e}")

    print(f"\n{subidas} subidas · {fallaron} con problemas")
    print("Quedan en «revisar»: apruébalas desde el panel del catálogo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
