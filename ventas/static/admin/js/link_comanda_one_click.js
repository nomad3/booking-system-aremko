// One-click: genera la comanda (si hace falta), copia el link y ofrece WhatsApp.
(function () {
    'use strict';

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    }

    async function copyToClipboard(text) {
        if (navigator.clipboard && window.isSecureContext) {
            try {
                await navigator.clipboard.writeText(text);
                return true;
            } catch (e) { /* fallthrough */ }
        }
        // Fallback
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        let ok = false;
        try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
        document.body.removeChild(ta);
        return ok;
    }

    function showToast(message, type) {
        const toast = document.createElement('div');
        toast.textContent = message;
        toast.style.cssText =
            'position:fixed;top:20px;right:20px;z-index:99999;' +
            'padding:12px 18px;border-radius:6px;font-size:13px;font-weight:600;' +
            'color:white;box-shadow:0 4px 12px rgba(0,0,0,.2);' +
            'background:' + (type === 'error' ? '#dc3545' : '#25d366');
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.transition = 'opacity .3s';
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 2800);
    }

    async function handleClick(btn) {
        const existing = btn.dataset.existing;
        const ajaxUrl = btn.dataset.ajaxUrl;
        const originalLabel = btn.textContent;

        btn.disabled = true;
        btn.textContent = '⏳ Procesando...';

        try {
            let url = existing;
            let whatsappUrl = null;

            if (!url) {
                const resp = await fetch(ajaxUrl, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    credentials: 'same-origin',
                });
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();
                if (!data.ok) throw new Error(data.error || 'unknown');
                url = data.url;
                whatsappUrl = data.whatsapp_url;
                btn.dataset.existing = url;
            }

            const copied = await copyToClipboard(url);
            if (copied) {
                showToast('✓ Link copiado al portapapeles');
                btn.style.background = '#4caf50';
                btn.textContent = '✓ Copiado';
            } else {
                showToast('Link generado (copia manual)', 'error');
                window.prompt('Copia el link:', url);
            }

            // Si tenemos URL de WhatsApp (solo cuando recién la generamos),
            // ofrece abrir WhatsApp Web tras un breve delay.
            if (whatsappUrl) {
                setTimeout(() => {
                    if (confirm('¿Abrir WhatsApp con el mensaje pre-cargado?')) {
                        window.open(whatsappUrl, '_blank');
                    }
                }, 300);
            }

            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = '📋 Copiar link';
                btn.style.background = '#25d366';
            }, 2500);
        } catch (err) {
            console.error('Error generando link de comanda:', err);
            showToast('Error: ' + err.message, 'error');
            btn.disabled = false;
            btn.textContent = originalLabel;
        }
    }

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.aremko-link-comanda-btn');
        if (!btn) return;
        e.preventDefault();
        handleClick(btn);
    });

    // --- Botón "Agregar Comanda con Productos" (abre menú cliente) ---
    async function handleOpenComanda(btn) {
        const existing = btn.dataset.existing;
        const ajaxUrl = btn.dataset.ajaxUrl;
        const originalLabel = btn.textContent;

        btn.disabled = true;
        btn.textContent = '⏳ Abriendo...';

        try {
            let url = existing;

            if (!url) {
                const resp = await fetch(ajaxUrl, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    credentials: 'same-origin',
                });
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                const data = await resp.json();
                if (!data.ok) throw new Error(data.error || 'unknown');
                url = data.url;
                btn.dataset.existing = url;
            }

            window.open(url, '_blank');

            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = '➕ Agregar Comanda con Productos';
            }, 1000);
        } catch (err) {
            console.error('Error abriendo menú de comanda:', err);
            showToast('Error: ' + err.message, 'error');
            btn.disabled = false;
            btn.textContent = originalLabel;
        }
    }

    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.aremko-open-comanda-btn');
        if (!btn) return;
        e.preventDefault();
        handleOpenComanda(btn);
    });
})();
