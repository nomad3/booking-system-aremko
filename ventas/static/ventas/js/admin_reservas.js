document.addEventListener('DOMContentLoaded', function() {
    // Delegación de eventos para inlines dinámicos
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('actualizar-horarios')) {
            const row = e.target.closest('.dynamic-reservaservicio');
            const servicioSelect = row.querySelector('.field-servicio select');
            const fechaInput = row.querySelector('.field-fecha_agendamiento input');
            const selectHora = row.querySelector('.field-hora_inicio select');

            // Validación visual
            if (!servicioSelect.value) {
                servicioSelect.style.border = '2px solid #ff4444';
                return;
            }
            if (!fechaInput.value) {
                fechaInput.style.border = '2px solid #ff4444';
                return;
            }

            // Restablecer estilos
            servicioSelect.style.border = '';
            fechaInput.style.border = '';

            // Lógica AJAX
            fetch(`/admin/ventas/servicio/${servicioSelect.value}/slots/?fecha=${fechaInput.value}`)
                .then(response => response.json())
                .then(data => {
                    selectHora.innerHTML = data.slots
                        .map(slot => `<option value="${slot}">${slot}</option>`)
                        .join('');
                })
                .catch(error => console.error('Error:', error));
        }
    });
}); 