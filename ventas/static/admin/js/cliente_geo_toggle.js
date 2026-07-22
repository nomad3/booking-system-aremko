/*
 * Plan Geo E1 — Form de Cliente (admin).
 * País = Chile / Extranjero. Si es Chile, la comuna se activa (y es obligatoria);
 * si es Extranjero, la comuna se desactiva y se limpia (la zona será 'extranjero').
 *
 * 2026-07-22: + accesos rápidos de comuna (Puerto Varas/Puerto Montt/Osorno —
 * la gran mayoría de los clientes). Sin ID hardcodeado: busca por nombre contra
 * el mismo endpoint AJAX que ya usa el autocomplete de Django admin (los
 * data-ajax--url/data-app-label/data-model-name/data-field-name que Django ya
 * deja en #id_comuna para Select2), así que si algún día cambia el seed de
 * Comuna esto se sigue resolviendo solo.
 */
(function () {
  function init() {
    var $ = (window.django && window.django.jQuery) || window.jQuery;
    if (!$) { return; }

    var $pais = $('#id_pais');
    var $comuna = $('#id_comuna');
    if (!$pais.length || !$comuna.length) { return; }

    var $row = $comuna.closest('.form-row, .field-comuna');

    function toggle() {
      var esChile = ($pais.val() || '').toLowerCase() === 'chile';
      $comuna.prop('disabled', !esChile);
      // Select2 (autocomplete) refleja el estado disabled al re-disparar change.
      if ($comuna.hasClass('select2-hidden-accessible')) {
        $comuna.trigger('change.select2');
      }
      if (esChile) {
        $row.css('opacity', '1');
      } else {
        // Extranjero: limpiar la comuna seleccionada.
        $comuna.val(null).trigger('change');
        $row.css('opacity', '0.45');
      }
    }

    $pais.on('change', toggle);
    toggle();

    function initComunaRapida() {
      var $botones = $('.aremko-comuna-btn');
      if (!$botones.length) { return; }

      var ajaxUrl = $comuna.data('ajax--url');
      var appLabel = $comuna.data('app-label');
      var modelName = $comuna.data('model-name');
      var fieldName = $comuna.data('field-name');
      if (!ajaxUrl) { return; } // sin autocomplete configurado, no hay de dónde buscar

      $botones.on('click', function (ev) {
        ev.preventDefault();
        var $btn = $(this);
        var nombre = $btn.data('comuna-nombre');
        if (!nombre) { return; }

        // Un clic en un acceso rápido implica País = Chile (si estaba en
        // Extranjero, la comuna estaría deshabilitada y el clic no serviría).
        if (($pais.val() || '').toLowerCase() !== 'chile') {
          $pais.val('Chile').trigger('change');
        }

        $btn.prop('disabled', true);
        $.ajax({
          url: ajaxUrl,
          dataType: 'json',
          data: {
            term: nombre,
            app_label: appLabel,
            model_name: modelName,
            field_name: fieldName,
          },
        }).done(function (data) {
          var resultados = (data && data.results) || [];
          // Preferir el match exacto por nombre (antes de la coma, ej.
          // "Puerto Varas, Los Lagos" -> "Puerto Varas"); si no hay exacto,
          // usar el primer resultado como fallback razonable.
          var match = null;
          for (var i = 0; i < resultados.length; i++) {
            var nombreResultado = (resultados[i].text || '').split(',')[0].trim();
            if (nombreResultado === nombre) {
              match = resultados[i];
              break;
            }
          }
          if (!match) { match = resultados[0]; }
          if (!match) { return; } // no se encontró — no-op silencioso

          if (!$comuna.find('option[value="' + match.id + '"]').length) {
            $comuna.append(new Option(match.text, match.id, true, true));
          } else {
            $comuna.val(match.id);
          }
          $comuna.trigger('change');
        }).always(function () {
          $btn.prop('disabled', false);
        });
      });
    }

    initComunaRapida();
  }

  if (document.readyState !== 'loading') {
    init();
  } else {
    document.addEventListener('DOMContentLoaded', init);
  }
})();
