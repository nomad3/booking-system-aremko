"""
Comando: Diagnóstico del sistema de vaciado de tinas

Este comando realiza un diagnóstico completo para entender por qué no se están
generando tareas de vaciado de tinas.

Uso:
    python manage.py diagnostico_vaciado
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User, Group
from datetime import datetime, timedelta
from control_gestion.models import Task
from ventas.models import VentaReserva, ReservaServicio
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Diagnóstico completo del sistema de vaciado de tinas"

    def handle(self, *args, **options):
        now = timezone.now()
        today = now.date()

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔍 DIAGNÓSTICO DE VACIADO DE TINAS"))
        self.stdout.write("=" * 80 + "\n")

        self.stdout.write(f"🕐 Hora actual: {now.strftime('%H:%M')}")
        self.stdout.write(f"📅 Fecha: {today}\n")

        # 1. Verificar grupo OPERACIONES
        self.stdout.write("─" * 80)
        self.stdout.write("1️⃣ VERIFICANDO GRUPO OPERACIONES")
        self.stdout.write("─" * 80 + "\n")

        try:
            ops_group = Group.objects.get(name='OPERACIONES')
            ops_users = User.objects.filter(groups=ops_group)

            if ops_users.exists():
                self.stdout.write(self.style.SUCCESS(
                    f"   ✅ Grupo OPERACIONES existe con {ops_users.count()} usuario(s)"
                ))
                for user in ops_users:
                    self.stdout.write(f"      - {user.username}")
            else:
                self.stdout.write(self.style.WARNING(
                    "   ⚠️  Grupo OPERACIONES existe pero NO tiene usuarios asignados"
                ))
                self.stdout.write("   💡 Solución: Asignar usuarios al grupo OPERACIONES\n")
        except Group.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                "   ⚠️  Grupo OPERACIONES NO existe"
            ))
            self.stdout.write("   💡 Solución: Crear grupo con Group.objects.create(name='OPERACIONES')\n")

        # 2. Buscar servicios de tinas del día
        self.stdout.write("─" * 80)
        self.stdout.write("2️⃣ BUSCANDO SERVICIOS DE TINAS DEL DÍA")
        self.stdout.write("─" * 80 + "\n")

        # Buscar reservas activas
        reservas_hoy = VentaReserva.objects.filter(
            fecha_reserva=today
        ).prefetch_related('reservaservicios__servicio')

        self.stdout.write(f"   📊 Total reservas hoy: {reservas_hoy.count()}\n")

        # Buscar servicios de tinas
        servicios_tina_hoy = []
        for reserva in reservas_hoy:
            for rs in reserva.reservaservicios.all():
                if rs.servicio and rs.servicio.tipo_servicio == 'tina':
                    servicios_tina_hoy.append({
                        'reserva': reserva,
                        'rs': rs,
                        'servicio_nombre': rs.servicio.nombre,
                        'hora_inicio': rs.hora_inicio,
                        'fecha': rs.fecha_agendamiento,
                        'estado_reserva': reserva.estado_reserva
                    })

        self.stdout.write(f"   🛁 Servicios de TINAS hoy: {len(servicios_tina_hoy)}")

        if servicios_tina_hoy:
            self.stdout.write("\n   📋 Detalle de servicios de tinas:\n")
            for srv in servicios_tina_hoy:
                # Normalizar hora
                hora_str = str(srv['hora_inicio']).strip()
                hora_str = hora_str.replace(';', ':').replace('.', ':')

                if ':' not in hora_str:
                    if len(hora_str) == 4:
                        hora_str = f"{hora_str[:2]}:{hora_str[2:]}"
                    elif len(hora_str) == 2:
                        hora_str = f"{hora_str}:00"

                try:
                    hora_inicio = datetime.strptime(hora_str, "%H:%M").time()
                    datetime_inicio = timezone.make_aware(
                        datetime.combine(srv['fecha'], hora_inicio)
                    )

                    # Calcular fin del servicio (inicio + 120 min)
                    datetime_fin = datetime_inicio + timedelta(minutes=120)

                    # Estado del servicio
                    if now < datetime_inicio:
                        estado = "⏰ Aún no inicia"
                    elif datetime_inicio <= now < datetime_fin:
                        estado = "▶️  EN CURSO"
                    elif now >= datetime_fin:
                        minutos_desde_fin = int((now - datetime_fin).total_seconds() / 60)
                        estado = f"✅ Terminó hace {minutos_desde_fin} min"

                    self.stdout.write(
                        f"      • {srv['servicio_nombre']} - Reserva #{srv['reserva'].id}\n"
                        f"        Hora: {hora_str} - {datetime_fin.strftime('%H:%M')}\n"
                        f"        Estado reserva: {srv['estado_reserva']}\n"
                        f"        Estado servicio: {estado}\n"
                    )
                except Exception as e:
                    self.stdout.write(
                        f"      • {srv['servicio_nombre']} - Reserva #{srv['reserva'].id}\n"
                        f"        ❌ Error parseando hora: {str(e)}\n"
                    )
        else:
            self.stdout.write(self.style.WARNING(
                "\n   ⚠️  NO hay servicios de tinas programados para hoy"
            ))

        # 3. Verificar servicios que deberían tener tarea de vaciado
        self.stdout.write("\n" + "─" * 80)
        self.stdout.write("3️⃣ VERIFICANDO SERVICIOS QUE DEBERÍAN TENER TAREA DE VACIADO")
        self.stdout.write("─" * 80 + "\n")

        # Buscar servicios terminados en últimas 3 horas
        ventana_busqueda = now - timedelta(minutes=150)

        self.stdout.write(
            f"   🔍 Buscando servicios de tina terminados desde las "
            f"{ventana_busqueda.strftime('%H:%M')}\n"
        )

        servicios_para_vaciar = []
        for srv in servicios_tina_hoy:
            hora_str = str(srv['hora_inicio']).strip().replace(';', ':').replace('.', ':')

            if ':' not in hora_str:
                if len(hora_str) == 4:
                    hora_str = f"{hora_str[:2]}:{hora_str[2:]}"
                elif len(hora_str) == 2:
                    hora_str = f"{hora_str}:00"

            try:
                hora_inicio = datetime.strptime(hora_str, "%H:%M").time()
                datetime_inicio = timezone.make_aware(
                    datetime.combine(srv['fecha'], hora_inicio)
                )
                datetime_fin = datetime_inicio + timedelta(minutes=120)

                # ¿Ya terminó?
                if now >= datetime_fin:
                    # ¿Está en la ventana de búsqueda?
                    if now <= datetime_fin + timedelta(minutes=150):
                        servicios_para_vaciar.append({
                            **srv,
                            'datetime_fin': datetime_fin
                        })
            except:
                continue

        self.stdout.write(f"   📊 Servicios terminados que podrían necesitar vaciado: {len(servicios_para_vaciar)}\n")

        if servicios_para_vaciar:
            for srv in servicios_para_vaciar:
                # Verificar si ya existe tarea
                nombre_tina_corto = srv['servicio_nombre'].split()[-1]
                tarea_existe = Task.objects.filter(
                    reservation_id=str(srv['reserva'].id),
                    title__icontains="Vaciar"
                ).filter(
                    title__icontains=nombre_tina_corto
                ).exists()

                estado_tarea = "✅ Ya existe" if tarea_existe else "❌ NO existe (debería crearse)"

                self.stdout.write(
                    f"      • {srv['servicio_nombre']} - Reserva #{srv['reserva'].id}\n"
                    f"        Terminó: {srv['datetime_fin'].strftime('%H:%M')}\n"
                    f"        Estado reserva: {srv['estado_reserva']}\n"
                    f"        Tarea de vaciado: {estado_tarea}\n"
                )
        else:
            self.stdout.write(self.style.WARNING(
                "   ℹ️  No hay servicios de tina terminados en la ventana de tiempo\n"
            ))

        # 4. Verificar tareas de vaciado creadas hoy
        self.stdout.write("─" * 80)
        self.stdout.write("4️⃣ TAREAS DE VACIADO CREADAS HOY")
        self.stdout.write("─" * 80 + "\n")

        tareas_vaciado_hoy = Task.objects.filter(
            created_at__date=today,
            title__icontains="Vaciar"
        )

        self.stdout.write(f"   📊 Total tareas de vaciado hoy: {tareas_vaciado_hoy.count()}\n")

        if tareas_vaciado_hoy.exists():
            for tarea in tareas_vaciado_hoy:
                self.stdout.write(
                    f"      • ID:{tarea.id} - {tarea.title}\n"
                    f"        Creada: {tarea.created_at.strftime('%H:%M')}\n"
                    f"        Estado: {tarea.get_state_display()}\n"
                    f"        Asignada a: {tarea.owner.username if tarea.owner else 'Sin asignar'}\n"
                )
        else:
            self.stdout.write(self.style.WARNING(
                "   ⚠️  NO se han creado tareas de vaciado hoy\n"
            ))

        # 5. Diagnóstico final y recomendaciones
        self.stdout.write("─" * 80)
        self.stdout.write("5️⃣ DIAGNÓSTICO Y RECOMENDACIONES")
        self.stdout.write("─" * 80 + "\n")

        problemas = []

        # Verificar grupo OPERACIONES
        try:
            ops_group = Group.objects.get(name='OPERACIONES')
            ops_users = User.objects.filter(groups=ops_group)
            if not ops_users.exists():
                problemas.append({
                    'problema': 'Grupo OPERACIONES sin usuarios',
                    'solucion': 'Asignar usuarios al grupo OPERACIONES en el admin'
                })
        except Group.DoesNotExist:
            problemas.append({
                'problema': 'Grupo OPERACIONES no existe',
                'solucion': 'Crear grupo: Group.objects.create(name="OPERACIONES")'
            })

        # Verificar servicios de tina
        if not servicios_tina_hoy:
            problemas.append({
                'problema': 'No hay servicios de tinas programados para hoy',
                'solucion': 'Esto es normal si no hay reservas de tinas hoy'
            })

        # Verificar servicios terminados sin tarea
        servicios_sin_tarea = 0
        for srv in servicios_para_vaciar:
            nombre_tina_corto = srv['servicio_nombre'].split()[-1]
            tarea_existe = Task.objects.filter(
                reservation_id=str(srv['reserva'].id),
                title__icontains="Vaciar",
                title__icontains=nombre_tina_corto
            ).exists()

            if not tarea_existe and srv['estado_reserva'] in ['checkin', 'checkout']:
                servicios_sin_tarea += 1

        if servicios_sin_tarea > 0:
            problemas.append({
                'problema': f'{servicios_sin_tarea} servicio(s) de tina terminado(s) sin tarea de vaciado',
                'solucion': 'Ejecutar manualmente: python manage.py gen_vaciado_tinas'
            })

        # Verificar estado de reservas
        reservas_pendiente = [s for s in servicios_tina_hoy if s['estado_reserva'] == 'pendiente']
        if len(reservas_pendiente) == len(servicios_tina_hoy) and servicios_tina_hoy:
            problemas.append({
                'problema': 'Todas las reservas de tinas están en estado "pendiente"',
                'solucion': 'Cambiar a "checkin" o "checkout" cuando el servicio esté en curso o termine'
            })

        if problemas:
            self.stdout.write(self.style.WARNING("   ⚠️  PROBLEMAS DETECTADOS:\n"))
            for i, p in enumerate(problemas, 1):
                self.stdout.write(f"   {i}. {p['problema']}")
                self.stdout.write(f"      💡 Solución: {p['solucion']}\n")
        else:
            self.stdout.write(self.style.SUCCESS(
                "   ✅ Todo parece estar configurado correctamente\n"
            ))

        # Resumen final
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📋 RESUMEN"))
        self.stdout.write("=" * 80 + "\n")

        self.stdout.write(f"   🛁 Servicios de tinas hoy: {len(servicios_tina_hoy)}")
        self.stdout.write(f"   ✅ Servicios terminados: {len(servicios_para_vaciar)}")
        self.stdout.write(f"   📝 Tareas de vaciado creadas hoy: {tareas_vaciado_hoy.count()}")
        self.stdout.write(f"   ⚠️  Problemas detectados: {len(problemas)}")

        self.stdout.write("\n" + "=" * 80 + "\n")

        # Próximos pasos
        self.stdout.write(self.style.WARNING("📌 PRÓXIMOS PASOS:\n"))

        if problemas:
            self.stdout.write("   1. Resolver los problemas detectados arriba")
            self.stdout.write("   2. Ejecutar: python manage.py gen_vaciado_tinas")
            self.stdout.write("   3. Verificar que se crean las tareas esperadas")
        else:
            if servicios_para_vaciar:
                self.stdout.write("   • Ejecutar: python manage.py gen_vaciado_tinas")
                self.stdout.write("     (Debería crear tareas de vaciado para los servicios terminados)")
            else:
                self.stdout.write("   • Esperar a que terminen servicios de tinas")
                self.stdout.write("   • El cron job ejecutará automáticamente cada 30 minutos")

        self.stdout.write("\n")
