document.addEventListener('DOMContentLoaded', function() {
    function getPrecioUnitario(selectElement) {
        const selectedOption = selectElement.options[selectElement.selectedIndex];
        return parseFloat(selectedOption.getAttribute('data-precio-unitario')) || 0;
    }

    function calculateValorTotal(form) {
        const servicioSelect = form.querySelector('select[name$="-servicio"]');
        const cantidadInput = form.querySelector('input[name$="-cantidad_personas"]');
        const precioUnitarioInput = form.querySelector('input[name$="-precio_unitario"]');
        const valorTotalInput = form.querySelector('input[name$="-valor_total"]');

        const precioUnitario = getPrecioUnitario(servicioSelect);
        const cantidad = parseInt(cantidadInput.value, 10) || 0;
        const valorTotal = precioUnitario * cantidad;

        precioUnitarioInput.value = precioUnitario.toFixed(2);
        valorTotalInput.value = valorTotal.toFixed(2);
    }

    document.querySelectorAll('.inline-related').forEach(function(inline) {
        const form = inline.querySelector('form');
        if (!form) return;

        const servicioSelect = form.querySelector('select[name$="-servicio"]');
        const cantidadInput = form.querySelector('input[name$="-cantidad_personas"]');

        if (servicioSelect && cantidadInput) {
            servicioSelect.addEventListener('change', function() {
                calculateValorTotal(inline);
            });

            cantidadInput.addEventListener('input', function() {
                calculateValorTotal(inline);
            });

            // Calcula al cargar
            calculateValorTotal(inline);
        }
    });
});
