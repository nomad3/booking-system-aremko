"""
Admin para Control de Gestión - Configuración básica

Se completará en pasos posteriores con acciones e inlines.
"""

from django.contrib import admin
from .models import Task, ChecklistItem, TaskLog, CustomerSegment, DailyReport

# Registro básico - se expandirá en los siguientes pasos
admin.site.register(CustomerSegment)
admin.site.register(DailyReport)

