/**
 * Configuración optimizada para autocomplete de Django Admin
 *
 * Mejoras de rendimiento:
 * - minimumInputLength: Requiere al menos 2 caracteres antes de buscar
 * - delay: Espera 300ms después de que el usuario deja de escribir
 *
 * Esto reduce significativamente el número de queries a la base de datos.
 */
(function($) {
    'use strict';

    $(document).ready(function() {
        // Configurar todos los campos autocomplete (select2)
        $('.admin-autocomplete').each(function() {
            var $element = $(this);

            // Obtener configuración actual de Select2 si existe
            var currentConfig = $element.data('select2') ? $element.select2('data') : {};

            // Destruir instancia actual si existe
            if ($element.data('select2')) {
                $element.select2('destroy');
            }

            // Reinicializar con configuración optimizada
            $element.select2({
                ajax: {
                    delay: 300,  // Esperar 300ms después de dejar de escribir
                },
                minimumInputLength: 2,  // Requiere mínimo 2 caracteres
                language: {
                    inputTooShort: function() {
                        return 'Ingrese al menos 2 caracteres para buscar';
                    },
                    searching: function() {
                        return 'Buscando...';
                    },
                    noResults: function() {
                        return 'No se encontraron resultados';
                    }
                }
            });
        });
    });
})(django.jQuery);
