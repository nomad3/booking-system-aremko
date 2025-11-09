"""
Management command para diagnosticar el error en la vista de reportes
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Diagnóstico de la vista de reportes diarios'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("DIAGNÓSTICO DE REPORTES DIARIOS")
        self.stdout.write("=" * 60)

        # 1. Verificar importación del modelo
        self.stdout.write("\n1. Verificando importación del modelo DailyReport...")
        try:
            from control_gestion.models import DailyReport
            self.stdout.write(self.style.SUCCESS("✅ Modelo DailyReport importado correctamente"))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ Error importando DailyReport: {e}"))
            return

        # 2. Verificar tabla en BD
        self.stdout.write("\n2. Verificando tabla en base de datos...")
        try:
            count = DailyReport.objects.count()
            self.stdout.write(self.style.SUCCESS(f"✅ Tabla existe. Total de reportes: {count}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error accediendo a la tabla: {e}"))
            self.stdout.write(self.style.WARNING("   Posible solución: ejecutar 'python manage.py migrate control_gestion'"))
            return

        # 3. Obtener reportes (como en la vista)
        self.stdout.write("\n3. Probando query de la vista...")
        try:
            reportes = DailyReport.objects.all().order_by('-date')[:14]
            self.stdout.write(self.style.SUCCESS(f"✅ Query exitoso. Reportes encontrados: {reportes.count()}"))

            if reportes.exists():
                self.stdout.write("\nÚltimos reportes:")
                for r in reportes:
                    self.stdout.write(f"  - {r.date} | Generado: {r.generated_at.strftime('%Y-%m-%d %H:%M')}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error en query: {e}"))
            return

        # 4. Verificar estadísticas
        self.stdout.write("\n4. Probando query de estadísticas...")
        try:
            stats = {
                'total': DailyReport.objects.count(),
                'ultima_semana': DailyReport.objects.filter(
                    date__gte=timezone.now().date() - timedelta(days=7)
                ).count()
            }
            self.stdout.write(self.style.SUCCESS(f"✅ Estadísticas calculadas: {stats}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error calculando estadísticas: {e}"))
            return

        # 5. Verificar template
        self.stdout.write("\n5. Verificando template...")
        try:
            from django.template.loader import get_template
            template = get_template('control_gestion/reportes_diarios.html')
            self.stdout.write(self.style.SUCCESS("✅ Template encontrado"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error cargando template: {e}"))
            return

        # 6. Simular render de la vista
        self.stdout.write("\n6. Simulando render de la vista...")
        try:
            from django.test import RequestFactory
            from django.contrib.auth import get_user_model
            from control_gestion.views import reportes_diarios

            User = get_user_model()

            # Crear request de prueba
            factory = RequestFactory()
            request = factory.get('/control_gestion/reportes/')

            # Asignar usuario (necesario para @login_required)
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.first()

            if user:
                request.user = user

                # Intentar ejecutar la vista
                response = reportes_diarios(request)

                if response.status_code == 200:
                    self.stdout.write(self.style.SUCCESS(f"✅ Vista ejecutada correctamente (status: {response.status_code})"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠️  Vista retornó status: {response.status_code}"))
            else:
                self.stdout.write(self.style.WARNING("⚠️  No se encontró usuario para probar"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error ejecutando vista: {e}"))
            import traceback
            self.stdout.write(traceback.format_exc())
            return

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ DIAGNÓSTICO COMPLETADO"))
        self.stdout.write("=" * 60)
