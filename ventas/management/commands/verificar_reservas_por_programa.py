# -*- coding: utf-8 -*-
"""Verifica (solo lectura) calcular_reservas_por_programa_semanal() contra datos reales,
antes de confiar en lo que se ve en /analytics/dashboard/ (H-058). No modifica nada.

Uso:
    python manage.py verificar_reservas_por_programa
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Imprime el desglose semanal por programa (últimas 8 semanas) para verificarlo."

    def handle(self, *args, **opts):
        from ventas.api_aremko_cli import calcular_reservas_por_programa_semanal

        data = calcular_reservas_por_programa_semanal(weeks=8)
        labels = data['semanas_labels']
        rangos = data['semanas_rango']

        self.stdout.write(f"Semanas (lunes-domingo, última hasta ayer): {labels}")
        for r in rangos:
            self.stdout.write(f"  {r['inicio']} a {r['fin']}")

        for prog in data['programas']:
            self.stdout.write(f"\n{'=' * 60}")
            self.stdout.write(f"{prog['nombre']} ({prog['clave']})")
            self.stdout.write(f"{'Semana':<10}{'Reservas':<12}{'Ingresos':<15}")
            for label, sem in zip(labels, prog['semanas']):
                self.stdout.write(f"{label:<10}{sem['count']:<12}${sem['revenue']:,.0f}")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Total 8 sem.: {prog['total_count']} reservas, ${prog['total_revenue']:,.0f}"
                )
            )
