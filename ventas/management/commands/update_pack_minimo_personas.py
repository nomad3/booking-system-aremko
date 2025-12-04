"""
Comando para actualizar la cantidad mínima de personas en los packs de descuento existentes.
Especialmente para el pack de Tina + Masaje que debe requerir mínimo 2 personas.
"""

from django.core.management.base import BaseCommand
from ventas.models import PackDescuento


class Command(BaseCommand):
    help = 'Actualiza la cantidad mínima de personas para los packs de descuento'

    def handle(self, *args, **options):
        self.stdout.write("\n🔧 Actualizando packs de descuento con cantidad mínima de personas...\n")

        # Buscar packs que incluyen Tina + Masaje
        packs_tina_masaje = PackDescuento.objects.filter(
            nombre__icontains='tina'
        ) | PackDescuento.objects.filter(
            nombre__icontains='masaje'
        )

        # Buscar específicamente el pack de 35000 de descuento
        pack_35000 = PackDescuento.objects.filter(
            descuento=35000
        ).first()

        if pack_35000:
            self.stdout.write(f"\n📦 Pack encontrado: {pack_35000.nombre}")
            self.stdout.write(f"   Descuento: ${pack_35000.descuento:,}")
            self.stdout.write(f"   Cantidad mínima actual: {getattr(pack_35000, 'cantidad_minima_personas', 1)}")

            # Actualizar a mínimo 2 personas
            pack_35000.cantidad_minima_personas = 2
            pack_35000.save()

            self.stdout.write(self.style.SUCCESS(f"   ✅ Actualizado a mínimo 2 personas\n"))

        # Mostrar todos los packs relacionados con Tina o Masaje
        if packs_tina_masaje.exists():
            self.stdout.write("\n📋 Otros packs relacionados con Tina o Masaje:")
            for pack in packs_tina_masaje:
                min_personas = getattr(pack, 'cantidad_minima_personas', 1)
                self.stdout.write(f"\n   • {pack.nombre}")
                self.stdout.write(f"     Descuento: ${pack.descuento:,}")
                self.stdout.write(f"     Mínimo personas: {min_personas}")

                # Si es un pack combinado y no tiene mínimo configurado, sugerir actualización
                if ('tina' in pack.nombre.lower() and 'masaje' in pack.nombre.lower()) and min_personas == 1:
                    self.stdout.write(self.style.WARNING(f"     ⚠️  Este pack combina servicios - considerar actualizar a 2 personas mínimo"))

        # Resumen general de todos los packs
        self.stdout.write("\n" + "="*60)
        self.stdout.write("\n📊 RESUMEN DE TODOS LOS PACKS:\n")

        all_packs = PackDescuento.objects.all().order_by('-activo', 'nombre')
        for pack in all_packs:
            estado = "✅" if pack.activo else "❌"
            min_personas = getattr(pack, 'cantidad_minima_personas', 1)
            self.stdout.write(
                f"\n{estado} {pack.nombre}"
                f"\n   Descuento: ${pack.descuento:,}"
                f"\n   Mínimo personas: {min_personas}"
                f"\n   Servicios: {', '.join([s.nombre for s in pack.servicios_requeridos.all()[:3]])}"
            )

        self.stdout.write(self.style.SUCCESS("\n✅ Proceso completado\n"))