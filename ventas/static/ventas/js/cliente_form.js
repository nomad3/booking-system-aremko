/**
 * JavaScript para el formulario de Cliente
 * Maneja la lógica condicional de mostrar/ocultar campos según el país
 */

(function($) {
    'use strict';

    $(document).ready(function() {
        // Elementos del formulario
        const $countrySelect = $('.country-code-select');
        const $phoneInput = $('.phone-number-input');
        const $customCountryCode = $('.codigo-pais-otro');
        const $paisInput = $('.pais-input').closest('.form-row, .field-pais');
        const $ciudadInput = $('.ciudad-input').closest('.form-row, .field-ciudad');
        const $regionSelect = $('.region-select').closest('.form-row, .field-region');
        const $comunaSelect = $('.comuna-select').closest('.form-row, .field-comuna');
        const $comunaSelectElement = $('.comuna-select');
        const $regionSelectElement = $('.region-select');

        // Función para actualizar la visibilidad de campos
        function updateFieldVisibility() {
            const selectedCountry = $countrySelect.val();

            if (selectedCountry === '+56') {
                // Chile seleccionado
                $paisInput.hide();
                $ciudadInput.hide();
                $regionSelect.show();
                $comunaSelect.show();
                $customCountryCode.hide();

                // Establecer valor por defecto para país
                $('.pais-input').val('Chile');
            } else if (selectedCountry === 'other') {
                // Otro país
                $paisInput.show();
                $ciudadInput.show();
                $regionSelect.hide();
                $comunaSelect.hide();
                $customCountryCode.show();

                // Limpiar selecciones de Chile
                $regionSelectElement.val('');
                $comunaSelectElement.val('');
            } else if (selectedCountry) {
                // País conocido no-Chile
                $paisInput.show();
                $ciudadInput.show();
                $regionSelect.hide();
                $comunaSelect.hide();
                $customCountryCode.hide();

                // Limpiar selecciones de Chile
                $regionSelectElement.val('');
                $comunaSelectElement.val('');
            } else {
                // Nada seleccionado
                $paisInput.hide();
                $ciudadInput.hide();
                $regionSelect.show();
                $comunaSelect.show();
                $customCountryCode.hide();
            }
        }

        // Función para cargar comunas según región
        function loadComunas() {
            const regionId = $regionSelectElement.val();

            if (!regionId) {
                $comunaSelectElement.empty().append('<option value="">---------</option>');
                return;
            }

            // AJAX para cargar comunas
            $.ajax({
                url: '/api/comunas-por-region/',
                data: {
                    'region': regionId
                },
                success: function(data) {
                    $comunaSelectElement.empty();
                    $comunaSelectElement.append('<option value="">---------</option>');

                    if (data.comunas) {
                        $.each(data.comunas, function(index, comuna) {
                            $comunaSelectElement.append(
                                $('<option></option>').attr('value', comuna.id).text(comuna.nombre)
                            );
                        });
                    }
                },
                error: function() {
                    console.error('Error al cargar comunas');
                }
            });
        }

        // Event listeners
        $countrySelect.on('change', updateFieldVisibility);
        $regionSelectElement.on('change', loadComunas);

        // Validación del número de teléfono
        $phoneInput.on('input', function() {
            const value = $(this).val();
            const countryCode = $countrySelect.val();

            // Solo números, espacios y guiones permitidos
            const cleaned = value.replace(/[^\d\s\-]/g, '');
            if (cleaned !== value) {
                $(this).val(cleaned);
            }

            // Validación específica para Chile
            if (countryCode === '+56') {
                // Remover caracteres no numéricos para contar
                const digitsOnly = cleaned.replace(/[\s\-]/g, '');

                // Mostrar advertencia si no son 9 dígitos
                if (digitsOnly.length > 0 && digitsOnly.length !== 9) {
                    if (!$(this).next('.help-text').length) {
                        $(this).after('<span class="help-text error">Los números chilenos deben tener 9 dígitos</span>');
                    }
                } else {
                    $(this).next('.help-text.error').remove();
                }
            } else {
                $(this).next('.help-text.error').remove();
            }
        });

        // Inicializar al cargar la página
        updateFieldVisibility();

        // Para Django admin: asegurar que los campos requeridos se marquen correctamente
        if (typeof django !== 'undefined' && django.jQuery) {
            django.jQuery(document).on('formset:added', function(event, $row, formsetName) {
                // Re-inicializar para nuevas filas en formsets
                updateFieldVisibility();
            });
        }
    });
})(django.jQuery || jQuery);