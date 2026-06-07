/*
 * Plan Geo E1 — Form de Cliente (admin).
 * País = Chile / Extranjero. Si es Chile, la comuna se activa (y es obligatoria);
 * si es Extranjero, la comuna se desactiva y se limpia (la zona será 'extranjero').
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
  }

  if (document.readyState !== 'loading') {
    init();
  } else {
    document.addEventListener('DOMContentLoaded', init);
  }
})();
