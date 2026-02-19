#!/usr/bin/env python
"""
Script para agregar validación de inventario al guardar comandas
Este script modifica el admin para validar stock antes de guardar

IMPORTANTE: Este script muestra los cambios necesarios.
Para aplicarlos, debes editar manualmente ventas/admin.py
"""

print("""
=== CAMBIOS NECESARIOS EN ventas/admin.py ===

1. En la clase ComandaAdmin, modificar el método save_formset:

Buscar el método save_formset (alrededor de línea 3233) y agregar validación:

def save_formset(self, request, form, formset, change):
    '''Guardar el formset y crear ReservaProducto para nuevas comandas'''
    try:
        instances = formset.save(commit=False)

        # NUEVO: Validar inventario ANTES de guardar
        errores_inventario = []
        for instance in instances:
            if instance.producto and instance.cantidad:
                if instance.producto.cantidad_disponible < instance.cantidad:
                    errores_inventario.append(
                        f"{instance.producto.nombre}: Solo hay {instance.producto.cantidad_disponible} unidades disponibles, "
                        f"pero se intentaron pedir {instance.cantidad}"
                    )

        # Si hay errores de inventario, mostrar mensaje y no guardar
        if errores_inventario:
            from django.contrib import messages
            for error in errores_inventario:
                messages.error(request, f"Error de inventario: {error}")
            messages.error(request, "La comanda no se guardó debido a problemas de inventario.")
            return  # No continuar con el guardado

        # Si llegamos aquí, el inventario está OK, continuar normal...
        # [resto del código existente]

2. Alternativa: Agregar método clean en DetalleComandaInline:

class DetalleComandaInline(admin.TabularInline):
    # ... código existente ...

    def clean(self):
        '''Validar inventario antes de guardar'''
        super().clean()
        if self.cleaned_data and not self.cleaned_data.get('DELETE'):
            producto = self.cleaned_data.get('producto')
            cantidad = self.cleaned_data.get('cantidad')

            if producto and cantidad:
                if producto.cantidad_disponible < cantidad:
                    raise ValidationError({
                        'cantidad': f'Solo hay {producto.cantidad_disponible} unidades disponibles'
                    })

=== CAMBIO TEMPORAL (mientras se implementa la solución) ===

Para permitir crear comandas sin validar inventario temporalmente,
puedes modificar la señal en ventas/signals/main_signals.py:

En la función actualizar_inventario (línea 437), cambiar el manejo del error:

except Exception as e:
    # En lugar de solo loggear, puedes comentar el logger.error
    # para evitar ruido en los logs
    # logger.error(f"Error updating inventory...")
    pass  # Ignorar errores de inventario temporalmente

=== RECOMENDACIÓN ===

La mejor solución es implementar la validación preventiva en el admin.
Esto evitará que se intenten crear comandas con productos sin stock
y mejorará la experiencia del usuario mostrando mensajes claros.
""")