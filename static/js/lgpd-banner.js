// Gerenciador de Consentimento e Cookies da LGPD
document.addEventListener('DOMContentLoaded', () => {
    const consentKey = 'skdnote_lgpd_consent';
    const banner = document.getElementById('lgpd-consent-banner');
    if (!banner) return;

    const savedConsent = localStorage.getItem(consentKey);
    if (!savedConsent) {
        banner.style.display = 'flex';
    }

    const btnAccept = document.getElementById('lgpd-btn-accept');
    const btnEssential = document.getElementById('lgpd-btn-essential');

    if (btnAccept) {
        btnAccept.addEventListener('click', () => {
            saveConsent({ essential: true, analytics: true, marketing: true });
        });
    }

    if (btnEssential) {
        btnEssential.addEventListener('click', () => {
            saveConsent({ essential: true, analytics: false, marketing: false });
        });
    }

    function saveConsent(consentData) {
        consentData.timestamp = new Date().toISOString();
        localStorage.setItem(consentKey, JSON.stringify(consentData));
        banner.style.display = 'none';

        // Envia para API interna caso o usuário esteja autenticado
        const csrfToken = getCookie('csrftoken');
        if (csrfToken) {
            fetch('/accounts/api/lgpd-consent/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(consentData)
            }).catch(() => {
                // Silencioso caso seja visitante não-autenticado
            });
        }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});
