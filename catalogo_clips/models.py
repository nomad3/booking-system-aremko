"""Catálogo de Clips (H-070, base del M17) — Fase A: el catálogo de fotos deja de
vivir en un JSON local y vive en Django.

App AISLADA (patrón whatsapp_agent/personal_operativo): migración 0001 sin
dependencias cruzadas → no toca el drift AR-033/AR-034.

Diseño port-friendly a Datamatic Hospitality multi-tenant: los campos UNIVERSALES
van explícitos (queryables); lo específico del rubro (spa ≠ restaurante) va en
`atributos` (JSON). Cuando migre a DH se agrega un FK `empresa` (nullable) — en
Aremko es mono-tenant, el hueco queda documentado aquí y NO se crea aún.
"""
from django.db import models


class Clip(models.Model):
    """Una foto (después video) del banco de material real de la empresa.

    Flujo: ingesta (IA propone taxonomía) → operador confirma/corrige → keeper
    disponible para la automatización de publicaciones. SOLO material real —
    nada sintético entra al catálogo (guarda de marca).
    """

    TIPOS = [('foto', 'Foto'), ('video', 'Video')]
    AREAS = [
        ('tina', 'Tina'), ('masaje', 'Masaje'), ('cabaña', 'Cabaña'),
        ('entorno', 'Entorno'), ('detalle', 'Detalle'), ('aereo', 'Aéreo'),
        ('recepcion', 'Recepción'), ('entorno_region', 'Entorno región'),
    ]
    MOMENTOS = [('dia', 'Día'), ('atardecer', 'Atardecer'), ('noche', 'Noche'),
                ('indistinto', 'Indistinto')]
    ESTACIONES = [('invierno', 'Invierno'), ('verano', 'Verano'), ('indistinto', 'Indistinto')]
    VAPOR = [('no', 'No'), ('sí', 'Sí'), ('sí (IA)', 'Sí (IA)')]
    DECORACION = [('con', 'Con decoración'), ('sin', 'Sin decoración'), ('', '—')]
    PERMISOS = [('libre', 'Libre'), ('revisar_derechos', 'Revisar derechos')]
    CALIDADES = [('alta', 'Alta'), ('media', 'Media')]
    ESTADOS = [('ok', 'OK'), ('revisar', 'Revisar'), ('descartado', 'Descartado')]

    # Identidad / archivo. `archivo` es la clave de upsert de la semilla local→nube.
    archivo = models.CharField(max_length=255, unique=True, db_index=True,
                               help_text='Nombre original del archivo (referencia; clave de upsert).')
    # Imagen optimizada: para subidas a mano desde el admin (storage de imágenes del
    # proyecto). La ingesta por API sube directo a Cloudinary y llena `cloud_url`.
    imagen = models.ImageField(upload_to='catalogo_clips/', blank=True, null=True,
                               help_text='Solo la imagen optimizada (el master pesado NO se sube).')
    cloud_url = models.URLField(max_length=500, blank=True,
                                help_text='URL Cloudinary de la imagen optimizada (q_auto,f_auto,w_1440).')
    tipo = models.CharField(max_length=10, choices=TIPOS, default='foto')

    # Taxonomía universal (explícita, queryable)
    area = models.CharField(max_length=20, choices=AREAS, db_index=True)
    nombre_comercial = models.CharField(max_length=100, blank=True,
                                        help_text='Nombre de la tina/cabaña/espacio (vacío si hay duda).')
    momento = models.CharField(max_length=12, choices=MOMENTOS, default='indistinto')
    estacion = models.CharField(max_length=12, choices=ESTACIONES, default='indistinto')
    vapor = models.CharField(max_length=8, choices=VAPOR, default='no')
    decoracion = models.CharField(max_length=4, choices=DECORACION, blank=True, default='')
    personas = models.BooleanField(default=False)
    permiso = models.CharField(max_length=20, choices=PERMISOS, default='libre')
    calidad = models.CharField(max_length=6, choices=CALIDADES, default='media')
    keeper = models.BooleanField(default=False, db_index=True,
                                 help_text='Hero: sin personas, nítida, distinta, no duplicado.')
    descripcion = models.CharField(max_length=300, blank=True)
    orientacion = models.CharField(max_length=12, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default='ok', db_index=True)
    fuente = models.CharField(max_length=30, blank=True, default='disco',
                              help_text='disco | chatgpt | ingesta_api | ...')
    nota = models.TextField(blank=True)
    origen = models.CharField(max_length=120, blank=True, help_text='Variantes / master de origen.')

    # Flexibles
    etiquetas = models.JSONField(default=list, blank=True)
    apto_para = models.JSONField(default=list, blank=True)
    # Extras por vertical (spa ≠ restaurante). En Aremko p.ej. {"hidromasaje": true}.
    atributos = models.JSONField(default=dict, blank=True)

    # PORT MULTI-TENANT (DH): aquí irá `empresa = FK(nullable)` cuando esta app migre
    # a Datamatic Hospitality. En Aremko (cliente cero) es mono-tenant: NO crear aún.

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Clip del catálogo'
        verbose_name_plural = 'Catálogo de clips'
        ordering = ['-actualizado']
        indexes = [
            models.Index(fields=['area', 'keeper'], name='catalogo_cl_area_keeper_idx'),
            models.Index(fields=['estado', 'tipo'], name='catalogo_cl_estado_tipo_idx'),
        ]

    def __str__(self):
        etiqueta = self.nombre_comercial or self.get_area_display()
        return f'{self.archivo} · {etiqueta}{" ⭐" if self.keeper else ""}'

    def save(self, *args, **kwargs):
        # Si subieron la imagen a mano por el admin y no hay cloud_url, derivarla.
        if not self.cloud_url and self.imagen:
            try:
                self.cloud_url = self.imagen.url
            except Exception:  # noqa: BLE001 — sin storage configurado (tests) se deja vacío
                pass
        super().save(*args, **kwargs)

    def to_dict(self):
        """Shape canónico de la API (ver docs/CONTRATO_H-070_CATALOGO.md)."""
        return {
            'id': self.id,
            'archivo': self.archivo,
            'cloud_url': self.cloud_url,
            'tipo': self.tipo,
            'area': self.area,
            'nombre_comercial': self.nombre_comercial,
            'momento': self.momento,
            'estacion': self.estacion,
            'vapor': self.vapor,
            'decoracion': self.decoracion,
            'personas': self.personas,
            'permiso': self.permiso,
            'calidad': self.calidad,
            'keeper': self.keeper,
            'descripcion': self.descripcion,
            'orientacion': self.orientacion,
            'estado': self.estado,
            'fuente': self.fuente,
            'nota': self.nota,
            'origen': self.origen,
            'etiquetas': self.etiquetas or [],
            'apto_para': self.apto_para or [],
            'atributos': self.atributos or {},
            'creado': self.creado.isoformat() if self.creado else None,
            'actualizado': self.actualizado.isoformat() if self.actualizado else None,
        }
