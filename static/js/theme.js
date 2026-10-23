/**
 * skdnote Theme Engine (Modo Claro Padrão com Alternador para Modo Escuro)
 * Persistência instantânea via localStorage com zero FOUC.
 */
(function() {
    function getStoredTheme() {
        const stored = localStorage.getItem('skdnote-theme');
        if (stored) return stored;
        // Padrão solicitado pelo usuário: tema claro (light)
        return 'light';
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.body && document.body.setAttribute('data-theme', theme);
        localStorage.setItem('skdnote-theme', theme);
        updateButtons(theme);
    }

    function updateButtons(theme) {
        const isDark = theme === 'dark';
        const buttons = document.querySelectorAll('.theme-toggle-btn');
        buttons.forEach(btn => {
            const icon = btn.querySelector('.theme-toggle-icon');
            const label = btn.querySelector('.theme-toggle-label');
            if (icon) {
                icon.textContent = isDark ? '☀️' : '🌙';
            }
            if (label) {
                label.textContent = isDark ? 'Claro' : 'Escuro';
            }
            btn.setAttribute('title', isDark ? 'Mudar para Modo Claro' : 'Mudar para Modo Escuro');
            btn.setAttribute('aria-label', isDark ? 'Mudar para Modo Claro' : 'Mudar para Modo Escuro');
        });
    }

    function toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
    }

    // Exporta globalmente para uso em botões e menus
    window.toggleTheme = toggleTheme;
    window.setTheme = applyTheme;

    // Inicialização ao carregar o DOM
    document.addEventListener('DOMContentLoaded', function() {
        const currentTheme = getStoredTheme();
        applyTheme(currentTheme);
    });
})();
