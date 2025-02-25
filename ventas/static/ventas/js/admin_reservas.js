document.addEventListener('DOMContentLoaded', function() {
    // Delegación de eventos para inlines dinámicos
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('actualizar-horarios')) {
            const row = e.target.closest('.dynamic-reservaservicio');
            const servicioId = row.querySelector('.field-servicio select').value;
            const fecha = row.querySelector('.field-fecha_agendamiento input').value;
            const selectHora = row.querySelector('.field-hora_inicio select');

            if (servicioId && fecha) {
                fetch(`/admin/ventas/servicio/${servicioId}/slots/?fecha=${fecha}`)
                    .then(response => response.json())
                    .then(data => {
                        selectHora.innerHTML = '';  // Limpiar opciones
                        data.slots.forEach(slot => {
                            const option = document.createElement('option');
                            option.value = slot;
                            option.textContent = slot;
                            selectHora.appendChild(option);
                        });
                    })
                    .catch(error => console.error('Error:', error));
            }
        }
    });
}); 