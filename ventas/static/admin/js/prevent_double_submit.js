/**
 * Prevenir envío duplicado de formularios en Django Admin
 *
 * PROBLEMA SOLUCIONADO:
 * - Usuarios hacían doble clic en botones "Guardar" causando duplicación de pagos/productos
 * - Especialmente problemático en conexiones lentas donde el botón no se deshabilitaba a tiempo
 *
 * SOLUCIÓN:
 * - Deshabilita todos los botones submit después del primer clic
 * - Muestra indicador visual de "Guardando..."
 * - Previene múltiples envíos del mismo formulario
 */

(function($) {
    'use strict';

    $(document).ready(function() {
        // Interceptar TODOS los formularios del admin
        $('form').on('submit', function(e) {
            var $form = $(this);

            // Verificar si el formulario ya fue enviado
            if ($form.data('submitted') === true) {
                // Prevenir re-envío
                e.preventDefault();
                console.warn('Formulario ya enviado, previniendo duplicación');
                return false;
            }

            // Marcar formulario como enviado
            $form.data('submitted', true);

            // Deshabilitar TODOS los botones submit del formulario
            var $submitButtons = $form.find('input[type="submit"], button[type="submit"]');

            $submitButtons.each(function() {
                var $btn = $(this);

                // Guardar texto original
                $btn.data('original-text', $btn.val() || $btn.text());

                // Cambiar texto a "Guardando..."
                if ($btn.is('input')) {
                    $btn.val('Guardando...');
                } else {
                    $btn.html('<i class="fas fa-spinner fa-spin"></i> Guardando...');
                }

                // Deshabilitar botón
                $btn.prop('disabled', true);

                // Agregar clase visual
                $btn.addClass('disabled-submit');
            });

            // Si hay un error de validación del navegador, re-habilitar
            setTimeout(function() {
                if (!$form[0].checkValidity || !$form[0].checkValidity()) {
                    resetForm($form, $submitButtons);
                }
            }, 100);

            // Auto-reset después de 30 segundos (por si hay un error de red)
            setTimeout(function() {
                resetForm($form, $submitButtons);
            }, 30000);
        });

        // Función para resetear el formulario
        function resetForm($form, $submitButtons) {
            $form.data('submitted', false);

            $submitButtons.each(function() {
                var $btn = $(this);
                var originalText = $btn.data('original-text');

                if ($btn.is('input')) {
                    $btn.val(originalText);
                } else {
                    $btn.text(originalText);
                }

                $btn.prop('disabled', false);
                $btn.removeClass('disabled-submit');
            });
        }

        // Prevenir doble clic en botones inline "Agregar otro"
        $(document).on('click', '.add-row a', function(e) {
            var $link = $(this);

            if ($link.data('adding') === true) {
                e.preventDefault();
                return false;
            }

            $link.data('adding', true);

            // Reset después de 500ms
            setTimeout(function() {
                $link.data('adding', false);
            }, 500);
        });

        // Prevenir doble clic en botones inline "Eliminar"
        $(document).on('click', '.delete-row a', function(e) {
            var $link = $(this);

            if ($link.data('deleting') === true) {
                e.preventDefault();
                return false;
            }

            $link.data('deleting', true);

            // Reset después de 500ms
            setTimeout(function() {
                $link.data('deleting', false);
            }, 500);
        });
    });

})(django.jQuery);
