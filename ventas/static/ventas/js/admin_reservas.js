document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.actualizar-horarios').forEach(button => {
        button.addEventListener('click', function(e) {
            const row = this.closest('.dynamic-reservaservicio');
            const servicioSelect = row.querySelector('.field-servicio select');
            const fechaInput = row.querySelector('.field-fecha_agendamiento input');
            const horaInicioSelect = row.querySelector('.field-hora_inicio select');
            
            if (servicioSelect.value && fechaInput.value) {
                fetch(`/admin/ventas/servicio/${servicioSelect.value}/slots/?fecha=${fechaInput.value}`)
                    .then(response => response.json())
                    .then(data => {
                        horaInicioSelect.innerHTML = '';
                        data.slots.forEach(slot => {
                            const option = document.createElement('option');
                            option.value = slot;
                            option.textContent = slot;
                            horaInicioSelect.appendChild(option);
                        });
                    });
            }
        });
    });
}); 