# -*- coding: utf-8 -*-
"""Carga las 4 EXPERIENCIAS INSIGNIA como GiftCardExperiencia (docs/
PROPUESTA_GIFTCARDS_EXPERIENCIAS.md, decisiones de Jorge 2026-07-05):

- Precio ÚNICO al valor de día de semana (dom-jue), válido CUALQUIER día — decisión
  deliberada: la GiftCard es la forma más conveniente de ir un fin de semana.
- Ritual = "el regalo estrella"; Pausa = "la más regalada" (badges en el template).
- Desactiva las reliquias: "Paquete Romántico" y los duplicados con calendario en el
  nombre (Dom-Jue / Vie-Sáb) que las insignia reemplazan.

Idempotente: update_or_create por id_experiencia (NO pisa la imagen si ya fue subida
en el admin). Las imágenes NO se cargan aquí — se suben a mano en el admin
(GiftCardExperiencia → campo imagen).

Uso:
    python manage.py cargar_experiencias_giftcard            # dry-run
    python manage.py cargar_experiencias_giftcard --aplicar  # escribe
"""
from django.core.management.base import BaseCommand

INSIGNIAS = [
    {
        'id_experiencia': 'pausa_junto_al_rio',
        'categoria': 'packs',
        'nombre': 'Pausa junto al río · para dos',
        'descripcion': 'Tina caliente privada + masaje en pareja, la misma tarde. Válida cualquier día.',
        'descripcion_giftcard': (
            'Una tarde entera para los dos: tina caliente privada junto al río Pescado y '
            'masaje en pareja en un domo de madera entre el bosque. Con infusión de hierbas '
            'preparada por tu masajista y un mirador donde el río suena más fuerte que todo '
            'lo demás. Válida cualquier día de la semana.'
        ),
        'monto_fijo': 110000,
        'orden': 1,
    },
    {
        'id_experiencia': 'noche_aguas_calientes',
        'categoria': 'packs',
        'nombre': 'Noche de Aguas Calientes · para dos',
        'descripcion': 'Cabaña boutique + tina caliente + desayuno. Válida cualquier día.',
        'descripcion_giftcard': (
            'Una noche en cabaña boutique junto al río, con tina caliente privada esperando '
            'bajo las estrellas y desayuno sin apuro a la mañana siguiente. Para llegar de '
            'noche y no querer irse. Válida cualquier día de la semana.'
        ),
        'monto_fijo': 130000,
        'orden': 2,
    },
    {
        'id_experiencia': 'ritual_del_rio',
        'categoria': 'packs',
        'nombre': 'Ritual del Río · para dos',
        'descripcion': 'Cabaña + tina + masaje en pareja + desayuno. El regalo estrella. Válida cualquier día.',
        'descripcion_giftcard': (
            'La experiencia completa: cabaña boutique, tina caliente junto al río, masaje en '
            'pareja en el domo y desayuno al despertar. Una noche que se recuerda por años — '
            'el regalo estrella de Aremko. Válida cualquier día de la semana.'
        ),
        'monto_fijo': 210000,
        'orden': 3,
    },
    {
        'id_experiencia': 'refugio_aremko',
        'categoria': 'packs',
        'nombre': 'Refugio Aremko · dos noches para dos',
        'descripcion': '2 noches, misma cabaña, tina + masaje en pareja. Válida cualquier día.',
        'descripcion_giftcard': (
            'Dos noches, la misma cabaña, cero apuro: tina caliente, masaje en pareja y el '
            'río de fondo todo el fin de semana. Para desconectar de verdad. Válida cualquier '
            'día de la semana.'
        ),
        'monto_fijo': 290000,
        'orden': 4,
    },
]

# DECISIÓN RADICAL de Jorge (2026-07-05, reforzada al ver la página): "solo se
# regalan experiencias, no tinas sueltas, no masajes sueltos" — y la GiftCard de
# monto libre TAMPOCO va. Se desactiva TODO lo que no sea una de las 4 insignia.
# Reversible: activo=False, se reactivan en el admin.
CATEGORIAS_QUE_SOBREVIVEN = set()  # nada sobrevive fuera de las 4 insignia


class Command(BaseCommand):
    help = "Carga las 4 experiencias insignia y desactiva todo lo demás (radical: solo se regalan experiencias)."

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true',
                            help='Escribir de verdad (sin esto es dry-run)')

    def handle(self, *args, **opts):
        from ventas.models import GiftCardExperiencia

        aplicar = opts['aplicar']
        ids_insignia = [d['id_experiencia'] for d in INSIGNIAS]

        self.stdout.write('=== 1) Experiencias insignia (update_or_create) ===')
        for datos in INSIGNIAS:
            id_exp = datos['id_experiencia']
            existente = GiftCardExperiencia.objects.filter(id_experiencia=id_exp).first()
            if aplicar:
                if existente:
                    # No tocar la imagen (puede haber sido subida en el admin).
                    for campo in ('categoria', 'nombre', 'descripcion',
                                  'descripcion_giftcard', 'monto_fijo', 'orden'):
                        setattr(existente, campo, datos[campo])
                    existente.activo = True
                    existente.save()
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {id_exp}: ACTUALIZADA (imagen intacta)'))
                else:
                    GiftCardExperiencia.objects.create(activo=True, **datos)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {id_exp}: CREADA (subir imagen en el admin)'))
            else:
                accion = 'SE ACTUALIZARÍA' if existente else 'SE CREARÍA'
                self.stdout.write(f'  → {id_exp}: {accion} — "{datos["nombre"]}" ${datos["monto_fijo"]:,}')

        self.stdout.write('\n=== 2) RADICAL: desactivar todo lo que no sea insignia (ni monto libre) ===')
        candidatas = GiftCardExperiencia.objects.filter(activo=True)
        n_desactivadas = 0
        for exp in candidatas:
            if exp.id_experiencia in ids_insignia:
                continue
            if exp.categoria in CATEGORIAS_QUE_SOBREVIVEN:
                self.stdout.write(f'  = {exp.id_experiencia}: SE MANTIENE (monto libre) — "{exp.nombre}"')
                continue
            if aplicar:
                exp.activo = False
                exp.save(update_fields=['activo', 'modificado'])
                self.stdout.write(self.style.WARNING(f'  ✗ {exp.id_experiencia}: DESACTIVADA — "{exp.nombre}"'))
            else:
                self.stdout.write(f'  → {exp.id_experiencia}: SE DESACTIVARÍA — "{exp.nombre}"')
            n_desactivadas += 1

        self.stdout.write('\n=== 3) Catálogo resultante (activas, por categoría/orden) ===')
        for exp in GiftCardExperiencia.objects.filter(activo=True).order_by('categoria', 'orden', 'nombre'):
            precio = f'${exp.monto_fijo:,}' if exp.monto_fijo else f'sugeridos {exp.montos_sugeridos}'
            con_foto = 'con foto' if exp.imagen else 'SIN FOTO'
            self.stdout.write(f'  [{exp.categoria}] {exp.id_experiencia} — "{exp.nombre}" · {precio} · {con_foto}')

        if not aplicar:
            self.stdout.write('\n(dry-run — nada se escribió; usar --aplicar para escribir)')
