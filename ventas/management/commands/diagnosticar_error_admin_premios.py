"""
Comando para diagnosticar el error 500 en el admin de ClientePremio
"""
from django.core.management.base import BaseCommand
from ventas.models import ClientePremio


class Command(BaseCommand):
    help = 'Diagnostica errores en el admin de ClientePremio'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔍 DIAGNÓSTICO DE ERROR EN ADMIN DE PREMIOS"))
        self.stdout.write("=" * 80 + "\n")

        # Verificar todos los premios
        premios = ClientePremio.objects.all().order_by('id')
        total = premios.count()

        self.stdout.write(f"Total de premios: {total}\n")

        problemas = []

        for premio in premios:
            try:
                # Intentar acceder a todos los campos que se muestran en list_display
                _ = str(premio.cliente) if premio.cliente else None
                _ = str(premio.premio) if premio.premio else None
                _ = premio.estado
                _ = premio.tramo_al_ganar
                _ = premio.tramo_anterior
                _ = premio.gasto_total_al_ganar
                _ = premio.fecha_ganado
                _ = premio.fecha_expiracion

                # Verificar que los decimales sean válidos
                if premio.gasto_total_al_ganar is None:
                    problemas.append({
                        'id': premio.id,
                        'problema': 'gasto_total_al_ganar es None',
                        'cliente': premio.cliente.nombre if premio.cliente else 'N/A'
                    })

                # Verificar que tramo_al_ganar sea válido
                if premio.tramo_al_ganar is None or premio.tramo_al_ganar < 0:
                    problemas.append({
                        'id': premio.id,
                        'problema': f'tramo_al_ganar inválido: {premio.tramo_al_ganar}',
                        'cliente': premio.cliente.nombre if premio.cliente else 'N/A'
                    })

            except Exception as e:
                problemas.append({
                    'id': premio.id,
                    'problema': f'Error al acceder: {str(e)}',
                    'cliente': premio.cliente.nombre if premio.cliente else 'N/A'
                })

        if problemas:
            self.stdout.write(self.style.ERROR(f"\n❌ Se encontraron {len(problemas)} premios con problemas:\n"))
            for p in problemas:
                self.stdout.write(f"  Premio #{p['id']}: {p['problema']}")
                self.stdout.write(f"    Cliente: {p['cliente']}\n")
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ Todos los premios están OK\n"))

        self.stdout.write("=" * 80)
