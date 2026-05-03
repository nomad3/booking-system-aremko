/**
 * Aremko - Eventos custom de GA4 (Tarea 2.2 plan maestro)
 *
 * Trackea automáticamente:
 *   - whatsapp_click: clicks en links wa.me o api.whatsapp.com
 *   - phone_click: clicks en links tel:
 *   - cta_blog_click: clicks en links al blog desde otra página
 *
 * También expone window.aremkoTrack(eventName, params) para uso manual
 * desde flujos específicos como:
 *   - reservation_started (al abrir modal de booking)
 *   - reservation_completed (al crearse la reserva exitosamente)
 *
 * GA4 ID configurado en base_public.html: G-T3K4CTD3HJ
 *
 * Después de desplegar, configurar estos eventos como "Conversions" en
 * GA4 Admin → Events para que cuenten como objetivos medibles.
 */
(function () {
    'use strict';

    // Helper público — disparar eventos custom desde otros scripts
    function aremkoTrack(eventName, params) {
        params = params || {};
        if (typeof gtag === 'undefined') {
            console.warn('[aremko-events] gtag no disponible, evento no enviado:', eventName);
            return;
        }
        try {
            gtag('event', eventName, params);
            console.log('[aremko-events] Evento enviado:', eventName, params);
        } catch (e) {
            console.error('[aremko-events] Error enviando evento:', eventName, e);
        }
    }
    window.aremkoTrack = aremkoTrack;

    // === Auto-tracking via event delegation ===
    document.addEventListener('click', function (e) {
        var link = e.target.closest('a');
        if (!link || !link.href) return;

        var href = link.href.toLowerCase();
        var linkText = (link.innerText || link.textContent || '').trim().substring(0, 100);
        var pagePath = window.location.pathname;

        // WhatsApp click
        if (href.indexOf('wa.me/') !== -1 || href.indexOf('api.whatsapp.com') !== -1) {
            aremkoTrack('whatsapp_click', {
                link_url: link.href,
                link_text: linkText,
                page_path: pagePath,
            });
            return;
        }

        // Phone click
        if (href.indexOf('tel:') === 0) {
            aremkoTrack('phone_click', {
                link_url: link.href,
                link_text: linkText,
                page_path: pagePath,
            });
            return;
        }

        // CTA blog click — link a /blog/ desde una página que no es el blog
        if (href.indexOf('/blog/') !== -1 && pagePath.indexOf('/blog/') === -1) {
            // Identificar el "source" según la URL del link
            var url = new URL(link.href);
            var utmSource = url.searchParams.get('utm_source') || '';
            var utmCampaign = url.searchParams.get('utm_campaign') || '';

            aremkoTrack('cta_blog_click', {
                link_url: link.href,
                link_text: linkText,
                page_path: pagePath,
                target_path: url.pathname,
                utm_source: utmSource,
                utm_campaign: utmCampaign,
            });
        }
    }, false);

    console.log('[aremko-events] Tracking activo: whatsapp_click, phone_click, cta_blog_click');
})();
