// Registro do Service Worker do PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js', { scope: '/' })
            .then((registration) => {
                console.log('[PWA] Service Worker registrado com sucesso:', registration.scope);
            })
            .catch((error) => {
                console.warn('[PWA] Falha ao registrar Service Worker:', error);
            });
    });
}

// Manipulador do prompt de instalação do PWA
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
    // Previne a barra automática do navegador para exibir o banner personalizado
    e.preventDefault();
    deferredPrompt = e;

    const installBanner = document.getElementById('pwa-install-banner');
    if (installBanner) {
        installBanner.style.display = 'flex';
    }
});

function triggerPWAInstall() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
            console.log('[PWA] Usuário aceitou a instalação do aplicativo.');
        }
        deferredPrompt = null;
        const installBanner = document.getElementById('pwa-install-banner');
        if (installBanner) {
            installBanner.style.display = 'none';
        }
    });
}

function dismissPWAInstall() {
    const installBanner = document.getElementById('pwa-install-banner');
    if (installBanner) {
        installBanner.style.display = 'none';
    }
}
