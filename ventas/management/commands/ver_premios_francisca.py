"""
Comando para ver los premios de Francisca Cuevas Parga
"""
from django.core.management.base import BaseCommand
from ventas.models import Cliente, ClientePremio


class Command(BaseCommand):
    help = 'Muestra los premios de Francisca Cuevas Parga'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("👤 PREMIOS DE FRANCISCA CUEVAS PARGA"))
        self.stdout.write("=" * 80 + "\n")

        # Buscar a Francisca
        francisca = Cliente.objects.filter(nombre__icontains="Francisca Cuevas").first()

        if not francisca:
            self.stdout.write(self.style.ERROR("❌ No se encontró a Francisca Cuevas"))
            return

        self.stdout.write(f"Cliente: {francisca.nombre}")
        self.stdout.write(f"ID: {francisca.id}")
        self.stdout.write(f"Email: {francisca.email}")
        self.stdout.write(f"Teléfono: {francisca.telefono}\n")

        # Obtener todos los premios
        premios = francisca.premios.all().order_by('id')

        if not premios:
            self.stdout.write(self.style.WARNING("⚠️  No tiene premios registrados"))
            return

        self.stdout.write(f"Total de premios: {premios.count()}\n")
        self.stdout.write("─" * 80)

        for p in premios:
            self.stdout.write(f"\n🎁 Premio #{p.id}")
            self.stdout.write(f"   Nombre: {p.premio.nombre}")
            self.stdout.write(f"   Tipo: {p.premio.tipo}")

            # Estado con color
            if p.estado == 'cancelado':
                estado_str = self.style.ERROR(f"   Estado: {p.estado}")
            elif p.estado == 'pendiente_aprobacion':
                estado_str = self.style.WARNING(f"   Estado: {p.estado}")
            elif p.estado == 'aprobado':
                estado_str = self.style.SUCCESS(f"   Estado: {p.estado}")
            else:
                estado_str = f"   Estado: {p.estado}"

            self.stdout.write(estado_str)

            self.stdout.write(f"   Tramo al ganar: {p.tramo_al_ganar}")
            if p.tramo_anterior:
                self.stdout.write(f"   Tramo anterior: {p.tramo_anterior}")
            self.stdout.write(f"   Gasto total: ${p.gasto_total_al_ganar:,.0f}")
            self.stdout.write(f"   Fecha ganado: {p.fecha_ganado.strftime('%d/%m/%Y %H:%M')}")

            if p.fecha_aprobacion:
                self.stdout.write(f"   Fecha aprobación: {p.fecha_aprobacion.strftime('%d/%m/%Y %H:%M')}")

            if p.notas_admin:
                self.stdout.write(f"   Notas: {p.notas_admin[:150]}")

            self.stdout.write("─" * 80)

        self.stdout.write("\n" + "=" * 80)
