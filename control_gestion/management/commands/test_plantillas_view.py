"""
Comando para probar la vista de plantillas y ver el error exacto

Simula lo que hace la vista plantillas_dashboard para detectar el error
"""

from django.core.management.base import BaseCommand
import traceback


class Command(BaseCommand):
    help = 'Prueba la vista de plantillas para detectar errores'

    def handle(self, *args, **options):
        print("\n" + "="*80)
        print("TEST: VISTA DE PLANTILLAS")
        print("="*80 + "\n")

        try:
            # Importar el modelo
            print("1. Importando TaskTemplate...")
            from control_gestion.models_templates import TaskTemplate
            print("   ✅ Import exitoso\n")

            # Obtener todas las plantillas
            print("2. Obteniendo todas las plantillas...")
            plantillas = TaskTemplate.objects.all().order_by('swimlane', 'queue_position')
            print(f"   ✅ {plantillas.count()} plantillas encontradas\n")

            # Iterar sobre cada plantilla y probar get_dias_str()
            print("3. Probando get_dias_str() en cada plantilla...")
            for i, plantilla in enumerate(plantillas, 1):
                try:
                    print(f"\n   Plantilla {i}: ID={plantilla.id}")
                    print(f"   - Título: {plantilla.title_template}")
                    print(f"   - Frecuencia: {plantilla.frecuencia}")
                    print(f"   - Activa: {plantilla.activa}")

                    # Intentar get_dias_str()
                    dias_str = plantilla.get_dias_str()
                    print(f"   - Días: {dias_str}")
                    print(f"   ✅ OK")

                except Exception as e:
                    print(f"   ❌ ERROR en plantilla ID={plantilla.id}")
                    print(f"   Error: {str(e)}")
                    print(f"   Tipo: {type(e).__name__}")
                    print("\n   Traceback completo:")
                    traceback.print_exc()
                    print("\n   Valores de campos:")
                    print(f"   - frecuencia: {repr(plantilla.frecuencia)}")
                    print(f"   - dias_activa: {repr(plantilla.dias_activa)}")
                    print(f"   - solo_martes: {repr(plantilla.solo_martes)}")
                    print(f"   - dia_del_mes: {repr(plantilla.dia_del_mes)}")
                    print(f"   - mes_inicio: {repr(plantilla.mes_inicio)}")

            # Probar estadísticas (como en la vista)
            print("\n4. Probando generación de estadísticas...")
            from control_gestion.models import Swimlane

            stats = {
                'total': plantillas.count(),
                'activas': plantillas.filter(activa=True).count(),
                'por_area': {},
                'solo_martes': plantillas.filter(solo_martes=True).count()
            }

            for lane in Swimlane:
                count = plantillas.filter(swimlane=lane).count()
                if count > 0:
                    stats['por_area'][lane.label] = count

            print(f"   ✅ Estadísticas generadas:")
            print(f"   - Total: {stats['total']}")
            print(f"   - Activas: {stats['activas']}")
            print(f"   - Solo martes: {stats['solo_martes']}")
            print(f"   - Por área: {stats['por_area']}")

            print("\n" + "="*80)
            print("✅ TEST COMPLETADO SIN ERRORES")
            print("="*80)
            print("\nSi el test pasó pero la vista falla, el problema puede estar en:")
            print("- El template HTML (plantillas_dashboard.html)")
            print("- Middleware o decoradores")
            print("- Permisos de usuario")

        except Exception as e:
            print("\n" + "="*80)
            print("❌ ERROR DURANTE EL TEST")
            print("="*80)
            print(f"\nError: {str(e)}")
            print(f"Tipo: {type(e).__name__}")
            print("\nTraceback completo:")
            traceback.print_exc()
            print("\n")
