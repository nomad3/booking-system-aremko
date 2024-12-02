document.addEventListener('DOMContentLoaded', function() {
    function getPrecioBase(selectElement) {
        const selectedOption = selectElement.options[selectElement.selectedIndex];
        return parseFloat(selectedOption.getAttribute('data-precio-unitario')) || 0;
    }

    function calculateValorTotal(form) {
        const productoSelect = form.querySelector('select[name$="-producto"]');
        const cantidadInput = form.querySelector('input[name$="-cantidad"]');
        const precioBaseInput = form.querySelector('input[name$="-precio_base"]');
        const valorTotalInput = form.querySelector('input[name$="-valor_total"]');

        const precioBase = getPrecioBase(productoSelect);
        const cantidad = parseInt(cantidadInput.value, 10) || 0;
        const valorTotal = precioBase * cantidad;

        precioBaseInput.value = precioBase.toFixed(2);
        valorTotalInput.value = valorTotal.toFixed(2);
    }

    document.querySelectorAll('.inline-related').forEach(function(inline) {
        const form = inline.querySelector('form');
        if (!form) return;

        const productoSelect = form.querySelector('select[name$="-producto"]');
        const cantidadInput = form.querySelector('input[name$="-cantidad"]');

        if (productoSelect && cantidadInput) {
            productoSelect.addEventListener('change', function() {
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
