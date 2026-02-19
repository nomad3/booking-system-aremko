#!/usr/bin/env python
"""
Fix mejorado: Validación ESTRICTA de inventario en comandas
Solo permite guardar si TODOS los productos tienen stock suficiente
"""

print("""
================================================================================
FIX MEJORADO: VALIDACIÓN ESTRICTA DE INVENTARIO EN COMANDAS
================================================================================

PRINCIPIO: La comanda se guarda SOLO si TODOS los productos tienen stock suficiente

CÓDIGO A IMPLEMENTAR EN ventas/admin.py:

1. AGREGAR NUEVO MÉTODO EN ComandaAdmin (antes de save_formset):

def validar_stock_completo(self, formset):
    '''
    Valida que TODOS los productos tengan stock suficiente
    Retorna: (es_valido, lista_errores)
    '''
    errores = []

    for form in formset:
        if form.cleaned_data and not form.cleaned_data.get('DELETE'):
            producto = form.cleaned_data.get('producto')
            cantidad = form.cleaned_data.get('cantidad')

            if producto and cantidad:
                stock_actual = producto.cantidad_disponible

                if stock_actual < cantidad:
                    errores.append({
                        'producto': producto.nombre,
                        'solicitado': cantidad,
                        'disponible': stock_actual,
                        'faltante': cantidad - stock_actual
                    })
                elif stock_actual < 5:  # Advertencia de stock bajo
                    errores.append({
                        'producto': producto.nombre,
                        'solicitado': cantidad,
                        'disponible': stock_actual,
                        'tipo': 'advertencia'
                    })

    return len([e for e in errores if e.get('tipo') != 'advertencia']) == 0, errores


2. REEMPLAZAR EL MÉTODO save_formset CON:

def save_formset(self, request, form, formset, change):
    '''Guardar SOLO si hay stock suficiente para TODOS los productos'''
    try:
        # Validar stock ANTES de guardar cualquier cosa
        stock_valido, problemas_stock = self.validar_stock_completo(formset)

        if not stock_valido:
            # Mostrar errores detallados
            from django.contrib import messages

            messages.error(request, "❌ NO SE PUEDE CREAR LA COMANDA - INVENTARIO INSUFICIENTE:")
            messages.error(request, "")

            # Agrupar por tipo de problema
            sin_stock = [p for p in problemas_stock if p.get('tipo') != 'advertencia']
            advertencias = [p for p in problemas_stock if p.get('tipo') == 'advertencia']

            # Mostrar productos sin stock
            for problema in sin_stock:
                messages.error(
                    request,
                    f"🚫 {problema['producto']}: "
                    f"Necesita {problema['solicitado']} | "
                    f"Disponible: {problema['disponible']} | "
                    f"FALTAN: {problema['faltante']} unidades"
                )

            # Mostrar advertencias (stock bajo)
            if advertencias:
                messages.warning(request, "")
                messages.warning(request, "⚠️ ADVERTENCIA - Stock bajo en:")
                for adv in advertencias:
                    messages.warning(
                        request,
                        f"• {adv['producto']}: Solo quedan {adv['disponible']} unidades"
                    )

            messages.error(request, "")
            messages.error(request, "📝 ACCIONES REQUERIDAS:")
            messages.error(request, "1. Ajuste las cantidades o elimine productos sin stock")
            messages.error(request, "2. Informe al cliente sobre disponibilidad")
            messages.error(request, "3. Intente guardar nuevamente")

            return  # NO guardar nada

        # Si llegamos aquí, HAY STOCK SUFICIENTE para TODO
        # Proceder con el guardado normal

        instances = formset.save(commit=False)

        # Guardar las instancias del formset (DetalleComanda)
        for instance in instances:
            instance.save()

        # Eliminar instancias marcadas para borrar
        for obj in formset.deleted_objects:
            obj.delete()

        formset.save_m2m()

        # Crear ReservaProducto si es nueva comanda desde admin
        comanda = form.instance
        if getattr(comanda, '_is_new_from_admin', False):
            from django.utils import timezone
            from ventas.models import ReservaProducto

            productos_agregados = []

            for detalle in comanda.detalles.all():
                fecha_entrega_reserva = (
                    comanda.fecha_entrega_objetivo.date()
                    if comanda.fecha_entrega_objetivo
                    else timezone.now().date()
                )

                try:
                    rp, created = ReservaProducto.objects.get_or_create(
                        venta_reserva=comanda.venta_reserva,
                        producto=detalle.producto,
                        defaults={
                            'cantidad': detalle.cantidad,
                            'precio_unitario_venta': detalle.precio_unitario,
                            'fecha_entrega': fecha_entrega_reserva
                        }
                    )

                    if not created:
                        rp.cantidad += detalle.cantidad
                        rp.save()

                    productos_agregados.append(f"{detalle.producto.nombre} x{detalle.cantidad}")

                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error creando ReservaProducto: {e}")

            # Mensaje de éxito con detalles
            from django.contrib import messages
            messages.success(request, f"✅ Comanda #{comanda.id} creada exitosamente")
            messages.success(request, "Productos agregados a la reserva:")
            for prod in productos_agregados:
                messages.success(request, f"• {prod}")

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error en save_formset de ComandaAdmin: {str(e)}", exc_info=True)

        from django.contrib import messages
        messages.error(request, f"Error inesperado: {str(e)}")


3. OPCIONAL - Agregar validación en tiempo real (JavaScript):

En el método Media de ComandaAdmin, agregar:

class Media:
    js = ('admin/js/validar_stock_comanda.js',)

Y crear el archivo static/admin/js/validar_stock_comanda.js:

(function($) {
    $(document).ready(function() {
        // Validar al cambiar producto o cantidad
        $('.field-producto select, .field-cantidad input').on('change', function() {
            // Aquí podrías hacer una llamada AJAX para verificar stock
            // y mostrar advertencia en tiempo real
        });
    });
})(django.jQuery);

================================================================================
BENEFICIOS DE ESTA IMPLEMENTACIÓN:
================================================================================

1. ✅ Validación ESTRICTA: TODO o NADA
2. ✅ Mensajes CLAROS sobre qué productos faltan
3. ✅ Vendedor sabe EXACTAMENTE qué ajustar
4. ✅ Cliente NO espera productos que no llegarán
5. ✅ Sistema coherente: Comanda = Compromiso cumplible

================================================================================
""")