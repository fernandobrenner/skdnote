/**
 * Editor e Motor de Sincronização Estilo UpNote — skdnote
 */

let autosaveTimeout = null;
const AUTOSAVE_DELAY = 500; // 500ms debounce

document.addEventListener('DOMContentLoaded', () => {
    initAutosave();
    initMobileNavigation();
    initToolbar();
    checkPaywallTrigger();
});

// Inicialização do Autosave contínuo
function initAutosave() {
    const titleInput = document.getElementById('editor-title');
    const contentArea = document.getElementById('editor-content');
    const noteIdEl = document.getElementById('current-note-id');

    if (!titleInput || !contentArea || !noteIdEl) return;

    const noteId = noteIdEl.value;
    if (!noteId) return;

    const triggerSave = () => {
        updateSyncStatus('saving', 'Salvando...');
        clearTimeout(autosaveTimeout);
        autosaveTimeout = setTimeout(() => {
            performAutosave(noteId, titleInput.value, contentArea.innerHTML, contentArea.innerText);
        }, AUTOSAVE_DELAY);
    };

    titleInput.addEventListener('input', triggerSave);
    contentArea.addEventListener('input', triggerSave);
}

// Execução da requisição de autosave
function performAutosave(noteId, title, contentHtml, contentPlain) {
    const csrfToken = getCsrfToken();
    const url = `/app/${noteId}/autosave/`;

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            title: title,
            content_html: contentHtml,
            content_plain: contentPlain
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Falha no salvamento');
        return response.json();
    })
    .then(data => {
        updateSyncStatus('saved', `Sincronizado ${data.updated_at}`);
        
        // Atualiza título e prévia no card lateral correspondente
        const cardTitle = document.querySelector(`.note-card[data-note-id="${noteId}"] .card-title-text`);
        const cardPreview = document.querySelector(`.note-card[data-note-id="${noteId}"] .note-card-preview`);
        if (cardTitle) cardTitle.textContent = data.title;
        if (cardPreview) cardPreview.textContent = data.preview;

        // Atualiza tags dinâmicas detectadas via hashtag (#tag)
        if (data.tags && window.renderNoteTags) {
            window.renderNoteTags(data.tags, noteId);
        }
    })
    .catch(err => {
        console.warn('[skdnote] Erro ao sincronizar com nuvem. Salvando localmente:', err);
        updateSyncStatus('offline', 'Offline (salvo no cache)');
        localStorage.setItem(`skdnote_offline_${noteId}`, JSON.stringify({
            title: title,
            contentHtml: contentHtml,
            timestamp: new Date().toISOString()
        }));
    });
}

function updateSyncStatus(state, message) {
    const statusEl = document.getElementById('sync-status-badge');
    if (!statusEl) return;

    statusEl.className = `sync-status ${state}`;
    statusEl.innerHTML = `
        <span style="display:inline-block; width:6px; height:6px; border-radius:50%; background:currentColor;"></span>
        ${message}
    `;
}

// Formatação e Interações Estilo UpNote
let savedSelectionRange = null;

function initToolbar() {
    const contentArea = document.getElementById('editor-content');

    const format = (command, value = null) => {
        document.execCommand(command, false, value);
        if (contentArea) contentArea.focus();
        updateToolbarActiveStates();
        triggerAutosaveDirectly();
    };

    window.editorFormat = format;

    window.toggleUpnoteMenu = (popoverId, e) => {
        if (e && e.stopPropagation) {
            e.stopPropagation();
        }
        const target = document.getElementById(popoverId);
        if (!target) return;
        const isCurrentlyOpen = target.style.display === 'flex';
        closeAllPopovers();
        if (!isCurrentlyOpen) {
            saveCurrentSelection();
            target.style.display = 'flex';
        }
    };
    // Alias retrocompatível
    window.togglePopover = window.toggleUpnoteMenu;

    window.closeAllPopovers = () => {
        document.querySelectorAll('.upnote-popover').forEach(p => {
            p.style.display = 'none';
        });
    };

    // Fecha popovers ao clicar fora
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.upnote-bottom-bar') && !e.target.closest('.upnote-popover') && !e.target.closest('.modal-overlay')) {
            closeAllPopovers();
        }
    });

    window.setHeading = (tag) => {
        restoreSelection();
        if (tag === 'p') {
            document.execCommand('formatBlock', false, '<p>');
        } else {
            document.execCommand('formatBlock', false, `<${tag}>`);
        }
        if (contentArea) contentArea.focus();
        updateToolbarActiveStates();
        triggerAutosaveDirectly();
    };

    window.setTextColor = (color) => {
        restoreSelection();
        document.execCommand('foreColor', false, color);
        if (contentArea) contentArea.focus();
        triggerAutosaveDirectly();
    };

    window.setTextHighlight = (color) => {
        restoreSelection();
        if (color === 'transparent') {
            document.execCommand('removeFormat', false, null);
        } else {
            document.execCommand('hiliteColor', false, color) || document.execCommand('backColor', false, color);
        }
        if (contentArea) contentArea.focus();
        triggerAutosaveDirectly();
    };

    window.insertCheckbox = () => {
        restoreSelection();
        const checkboxHtml = '<div class="upnote-todo-item"><input type="checkbox" onchange="toggleTodoItem(this)"> <span>&nbsp;</span></div><p><br></p>';
        document.execCommand('insertHTML', false, checkboxHtml);
        if (contentArea) contentArea.focus();
        triggerAutosaveDirectly();
    };

    window.toggleTodoItem = (checkboxEl) => {
        const item = checkboxEl.closest('.upnote-todo-item');
        if (item) {
            if (checkboxEl.checked) {
                item.classList.add('checked');
                checkboxEl.setAttribute('checked', 'checked');
            } else {
                item.classList.remove('checked');
                checkboxEl.removeAttribute('checked');
            }
            triggerAutosaveDirectly();
        }
    };

    // Delegação de evento para checkboxes existentes
    if (contentArea) {
        contentArea.addEventListener('change', (e) => {
            if (e.target && e.target.type === 'checkbox') {
                window.toggleTodoItem(e.target);
            }
        });
    }

    window.insertCodeBlock = () => {
        restoreSelection();
        const codeBlockHtml = '<pre><code>// Seu código aqui</code></pre><p><br></p>';
        document.execCommand('insertHTML', false, codeBlockHtml);
        if (contentArea) contentArea.focus();
        triggerAutosaveDirectly();
    };

    window.insertDivider = () => {
        restoreSelection();
        const hrHtml = '<hr><p><br></p>';
        document.execCommand('insertHTML', false, hrHtml);
        if (contentArea) contentArea.focus();
        triggerAutosaveDirectly();
    };

    window.openLinkModal = () => {
        saveCurrentSelection();
        const selectedText = window.getSelection().toString();
        const textInput = document.getElementById('link-text-input');
        const urlInput = document.getElementById('link-url-input');
        if (textInput) textInput.value = selectedText || '';
        if (urlInput) urlInput.value = '';
        openModal('modal-insert-link');
        setTimeout(() => urlInput && urlInput.focus(), 100);
    };

    window.applyInsertLink = () => {
        const textInput = document.getElementById('link-text-input');
        const urlInput = document.getElementById('link-url-input');
        const text = textInput ? textInput.value.trim() : '';
        const url = urlInput ? urlInput.value.trim() : '';

        closeModal('modal-insert-link');
        restoreSelection();

        if (url) {
            const finalUrl = url.startsWith('http://') || url.startsWith('https://') ? url : `https://${url}`;
            const linkHtml = `<a href="${finalUrl}" target="_blank" rel="noopener noreferrer">${text || finalUrl}</a>`;
            document.execCommand('insertHTML', false, linkHtml);
            triggerAutosaveDirectly();
        }
    };

    window.openTexModal = () => {
        saveCurrentSelection();
        const texInput = document.getElementById('tex-formula-input');
        if (texInput) texInput.value = '';
        openModal('modal-insert-tex');
        setTimeout(() => texInput && texInput.focus(), 100);
    };

    window.applyInsertTex = () => {
        const texInput = document.getElementById('tex-formula-input');
        const formula = texInput ? texInput.value.trim() : '';
        closeModal('modal-insert-tex');
        restoreSelection();

        if (formula) {
            const texHtml = `<span class="upnote-tex-block" contenteditable="false" title="Fórmula TeX: ${formula}">\\( ${formula} \\)</span>&nbsp;`;
            document.execCommand('insertHTML', false, texHtml);
            triggerAutosaveDirectly();
        }
    };

    window.moveListItem = (direction) => {
        restoreSelection();
        const selection = window.getSelection();
        if (!selection || !selection.anchorNode) return;
        
        let node = selection.anchorNode;
        if (node.nodeType === Node.TEXT_NODE) node = node.parentNode;
        
        const listItem = node.closest('li') || node.closest('.upnote-todo-item');
        if (!listItem) return;

        if (direction === 'up' && listItem.previousElementSibling) {
            listItem.parentNode.insertBefore(listItem, listItem.previousElementSibling);
        } else if (direction === 'down' && listItem.nextElementSibling) {
            listItem.parentNode.insertBefore(listItem.nextElementSibling, listItem);
        }
        triggerAutosaveDirectly();
    };

    window.insertTable = (rows = 3, cols = 3) => {
        restoreSelection();
        let tableHtml = '<table style="width:100%; border-collapse:collapse; margin:16px 0; border:1px solid var(--border-color);">';
        tableHtml += '<thead><tr style="background:var(--bg-hover);">';
        for (let c = 0; c < cols; c++) {
            tableHtml += `<th style="border:1px solid var(--border-color); padding:8px 12px; text-align:left; font-weight:700;">Coluna ${c+1}</th>`;
        }
        tableHtml += '</tr></thead><tbody>';
        for (let r = 0; r < rows; r++) {
            tableHtml += '<tr>';
            for (let c = 0; c < cols; c++) {
                tableHtml += `<td style="border:1px solid var(--border-color); padding:8px 12px;">Item</td>`;
            }
            tableHtml += '</tr>';
        }
        tableHtml += '</tbody></table><p><br></p>';
        document.execCommand('insertHTML', false, tableHtml);
        triggerAutosaveDirectly();
    };

    window.insertImagePrompt = () => {
        const url = prompt('Informe o link direto (URL) da imagem:');
        if (url && url.trim()) {
            restoreSelection();
            const imgHtml = `<p><img src="${url.trim()}" alt="Imagem" style="max-width:100%; height:auto; border-radius:8px; margin:12px 0;" /></p><p><br></p>`;
            document.execCommand('insertHTML', false, imgHtml);
            triggerAutosaveDirectly();
        }
    };

    window.focusEditor = () => {
        if (contentArea) contentArea.focus();
    };

    // Detecção dinâmica de estado ativo (H, B, I, U, etc.)
    document.addEventListener('selectionchange', updateToolbarActiveStates);
    if (contentArea) {
        contentArea.addEventListener('keyup', updateToolbarActiveStates);
        contentArea.addEventListener('mouseup', updateToolbarActiveStates);
    }

    // Configuração de Atalhos de Teclado Globais (Iguais ao UpNote)
    document.addEventListener('keydown', handleEditorShortcuts);
}

function saveCurrentSelection() {
    const sel = window.getSelection();
    if (sel.rangeCount > 0) {
        savedSelectionRange = sel.getRangeAt(0).cloneRange();
    }
}

function restoreSelection() {
    if (savedSelectionRange) {
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(savedSelectionRange);
    }
}

function triggerAutosaveDirectly() {
    const titleInput = document.getElementById('editor-title');
    const contentArea = document.getElementById('editor-content');
    const noteIdEl = document.getElementById('current-note-id');
    if (!titleInput || !contentArea || !noteIdEl || !noteIdEl.value) return;

    clearTimeout(autosaveTimeout);
    autosaveTimeout = setTimeout(() => {
        performAutosave(noteIdEl.value, titleInput.value, contentArea.innerHTML, contentArea.innerText);
    }, 400);
}

function updateToolbarActiveStates() {
    const isBold = document.queryCommandState('bold');
    const isItalic = document.queryCommandState('italic');
    const isUnderline = document.queryCommandState('underline');
    const isStrike = document.queryCommandState('strikeThrough');

    setButtonActive('btn-bold', isBold);
    setButtonActive('btn-italic', isItalic);
    setButtonActive('btn-underline', isUnderline);
    setButtonActive('btn-strike', isStrike);

    // Detecção de nível de título para destacar botão 'H' em azul igual ao UpNote
    const formatBlock = document.queryCommandValue('formatBlock') || '';
    const isHeading = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].includes(formatBlock.toLowerCase());
    setButtonActive('btn-heading', isHeading);
}

function setButtonActive(buttonId, isActive) {
    const btn = document.getElementById(buttonId);
    if (!btn) return;
    if (isActive) {
        btn.classList.add('active');
    } else {
        btn.classList.remove('active');
    }
}

function handleEditorShortcuts(e) {
    const isCtrlOrCmd = e.ctrlKey || e.metaKey;
    if (!isCtrlOrCmd) return;

    // Ctrl+K -> Link
    if (e.key === 'k' || e.key === 'K') {
        e.preventDefault();
        window.openLinkModal();
    }
    // Ctrl+Shift+H -> Divider
    else if (e.shiftKey && (e.key === 'h' || e.key === 'H')) {
        e.preventDefault();
        window.insertDivider();
    }
    // Ctrl+Shift+M -> TeX
    else if (e.shiftKey && (e.key === 'm' || e.key === 'M')) {
        e.preventDefault();
        window.openTexModal();
    }
    // Ctrl+\ -> Remove formatting
    else if (e.key === '\\') {
        e.preventDefault();
        window.editorFormat('removeFormat');
    }
    // Ctrl+Alt+Up -> Move item up
    else if (e.altKey && e.key === 'ArrowUp') {
        e.preventDefault();
        window.moveListItem('up');
    }
    // Ctrl+Alt+Down -> Move item down
    else if (e.altKey && e.key === 'ArrowDown') {
        e.preventDefault();
        window.moveListItem('down');
    }
    // Ctrl+Alt+1 a 4 -> Headings
    else if (e.altKey && ['1', '2', '3', '4'].includes(e.key)) {
        e.preventDefault();
        window.setHeading(`h${e.key}`);
    }
    else if (e.altKey && e.key === '0') {
        e.preventDefault();
        window.setHeading('p');
    }
}

// Navegação Mobile e Alternância de Telas
function initMobileNavigation() {
    window.openMobileSidebar = () => {
        const sidebar = document.querySelector('.sidebar-col');
        if (sidebar) sidebar.classList.add('open');
    };

    window.closeMobileSidebar = () => {
        const sidebar = document.querySelector('.sidebar-col');
        if (sidebar) sidebar.classList.remove('open');
    };

    window.closeMobileEditor = () => {
        const editor = document.querySelector('.editor-col');
        if (editor) editor.classList.remove('open');
    };

    // Abre editor em telas de smartphone ao clicar em um card
    const cards = document.querySelectorAll('.note-card');
    cards.forEach(card => {
        card.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                const editor = document.querySelector('.editor-col');
                if (editor) editor.classList.add('open');
            }
        });
    });

    // Se houver nota selecionada na carga inicial e estiver no celular, abre o editor
    const noteIdEl = document.getElementById('current-note-id');
    if (noteIdEl && noteIdEl.value && window.innerWidth <= 768) {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('note_id')) {
            const editor = document.querySelector('.editor-col');
            if (editor) editor.classList.add('open');
        }
    }
}

// Abertura e Fechamento de Modais
window.openModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'flex';
};
const openModal = window.openModal;

window.closeModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.style.display = 'none';
};
const closeModal = window.closeModal;

// Gatilho do Paywall (ao atingir 50 notas no plano gratuito)
function checkPaywallTrigger() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('paywall') === '1') {
        openModal('paywall-modal');
    }
}

// Ações Rápidas (Fixar, Favoritar, Lixeira)
function toggleNotePin(noteId) {
    fetch(`/app/${noteId}/pin/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(data => {
        window.location.reload();
    });
}

function toggleNoteFavorite(noteId) {
    fetch(`/app/${noteId}/favorite/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(data => {
        window.location.reload();
    });
}

window.openConfirmDeleteModal = function(noteId, type, noteTitle) {
    if (!noteId) {
        const idInput = document.getElementById('current-note-id');
        noteId = idInput ? idInput.value : null;
    }
    if (!noteId) return;

    if (!noteTitle) {
        const titleEl = document.getElementById('editor-title');
        if (titleEl && titleEl.value) {
            noteTitle = titleEl.value;
        } else {
            const cardTitle = document.querySelector(`.note-card[data-note-id="${noteId}"] .card-title-text`);
            noteTitle = cardTitle ? cardTitle.textContent.trim() : 'Sem título';
        }
    }

    const titleEl = document.getElementById('confirm-delete-title');
    const msgEl = document.getElementById('confirm-delete-message');
    const nameEl = document.getElementById('confirm-delete-note-name');
    const btnEl = document.getElementById('btn-execute-confirmed-delete');

    if (nameEl) nameEl.textContent = noteTitle || 'Sem título';

    if (type === 'permanent') {
        if (titleEl) titleEl.textContent = 'Excluir definitivamente?';
        if (msgEl) msgEl.textContent = 'ATENÇÃO: Esta ação é definitiva e não pode ser desfeita. Todo o conteúdo da anotação será apagado permanentemente.';
        if (btnEl) {
            btnEl.textContent = 'Excluir Definitivamente';
            btnEl.style.background = '#dc2626';
            btnEl.onclick = function() {
                window.closeModal('modal-confirm-delete');
                window.deleteNotePermanently(noteId);
            };
        }
    } else {
        if (titleEl) titleEl.textContent = 'Mover para a Lixeira?';
        if (msgEl) msgEl.textContent = 'Tem certeza que deseja mover esta anotação para a Lixeira? Você poderá restaurá-la a qualquer momento na Lixeira.';
        if (btnEl) {
            btnEl.textContent = 'Mover para Lixeira';
            btnEl.style.background = '#ef4444';
            btnEl.onclick = function() {
                window.closeModal('modal-confirm-delete');
                window.moveNoteToTrash(noteId, false);
            };
        }
    }

    window.openModal('modal-confirm-delete');
};

window.handleHeaderTrashClick = function(e, noteId) {
    if (e && e.preventDefault) e.preventDefault();
    window.openConfirmDeleteModal(noteId, 'trash');
    return false;
};

window.moveNoteToTrash = function(noteId, confirmFirst) {
    if (confirmFirst) {
        window.openConfirmDeleteModal(noteId, 'trash');
        return;
    }
    if (!noteId) {
        const idInput = document.getElementById('current-note-id');
        noteId = idInput ? idInput.value : null;
    }
    if (!noteId) return;

    if (typeof saveTimeout !== 'undefined' && saveTimeout) {
        clearTimeout(saveTimeout);
    }

    const csrf = getCsrfToken();
    const form = document.getElementById(`form-move-trash-${noteId}`);

    fetch(`/app/${noteId}/trash/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => {
        if (!r.ok) throw new Error('Falha HTTP ' + r.status);
        return r.json();
    })
    .then(() => {
        const card = document.querySelector(`.note-card[data-note-id="${noteId}"]`);
        if (card) {
            card.style.transition = 'all 0.25s ease';
            card.style.opacity = '0';
            card.style.transform = 'scale(0.9) translateX(-20px)';
            setTimeout(() => card.remove(), 250);
        }
        window.location.href = '/app/';
    })
    .catch(() => {
        if (form) {
            form.submit();
        } else {
            const fallbackForm = document.createElement('form');
            fallbackForm.method = 'POST';
            fallbackForm.action = `/app/${noteId}/trash/`;
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'csrfmiddlewaretoken';
            input.value = csrf;
            fallbackForm.appendChild(input);
            document.body.appendChild(fallbackForm);
            fallbackForm.submit();
        }
    });
};
const moveNoteToTrash = window.moveNoteToTrash;

window.restoreNoteFromTrash = function(noteId) {
    if (!noteId) {
        const idInput = document.getElementById('current-note-id');
        noteId = idInput ? idInput.value : null;
    }
    if (!noteId) return;

    const csrf = getCsrfToken();
    fetch(`/app/${noteId}/restore/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => {
        if (!r.ok) throw new Error('Falha HTTP ' + r.status);
        return r.json();
    })
    .then(() => {
        const card = document.querySelector(`.note-card[data-note-id="${noteId}"]`);
        if (card) {
            card.style.transition = 'all 0.25s ease';
            card.style.opacity = '0';
            card.style.transform = 'scale(0.9) translateX(20px)';
            setTimeout(() => card.remove(), 250);
        }
        window.location.href = `/app/?note_id=${noteId}`;
    })
    .catch(() => {
        const fallbackForm = document.createElement('form');
        fallbackForm.method = 'POST';
        fallbackForm.action = `/app/${noteId}/restore/`;
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrfmiddlewaretoken';
        input.value = csrf;
        fallbackForm.appendChild(input);
        document.body.appendChild(fallbackForm);
        fallbackForm.submit();
    });
};
const restoreNoteFromTrash = window.restoreNoteFromTrash;

window.deleteNotePermanently = function(noteId) {
    if (!noteId) {
        const idInput = document.getElementById('current-note-id');
        noteId = idInput ? idInput.value : null;
    }
    if (!noteId) return;

    const csrf = getCsrfToken();
    fetch(`/app/${noteId}/delete/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => {
        if (!r.ok) throw new Error('Falha HTTP ' + r.status);
        return r.json();
    })
    .then(() => {
        const card = document.querySelector(`.note-card[data-note-id="${noteId}"]`);
        if (card) {
            card.style.transition = 'all 0.25s ease';
            card.style.opacity = '0';
            card.style.transform = 'scale(0.9) translateX(-20px)';
            setTimeout(() => card.remove(), 250);
        }
        window.location.href = '/app/?filter=trash';
    })
    .catch(() => {
        const fallbackForm = document.createElement('form');
        fallbackForm.method = 'POST';
        fallbackForm.action = `/app/${noteId}/delete/`;
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrfmiddlewaretoken';
        input.value = csrf;
        fallbackForm.appendChild(input);
        document.body.appendChild(fallbackForm);
        fallbackForm.submit();
    });
};
const deleteNotePermanently = window.deleteNotePermanently;

// Helper CSRF robusto
function getCsrfToken() {
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 10) === ('csrftoken=')) {
                cookieValue = decodeURIComponent(cookie.substring(10));
                break;
            }
        }
    }
    return cookieValue || '';
}

// Gestão de Compartilhamento por Link
window.currentShareNoteId = window.currentShareNoteId || null;

window.openShareModal = function(noteId, isShared, token) {
    window.currentShareNoteId = noteId;
    const activePanel = document.getElementById('share-active-panel');
    const inactivePanel = document.getElementById('share-inactive-panel');
    const urlInput = document.getElementById('share-url-input');
    const openLink = document.getElementById('share-open-link');
    const disableBtn = document.getElementById('share-disable-btn');
    const copyBtn = document.getElementById('share-copy-btn');
    if (copyBtn) copyBtn.textContent = 'Copiar';

    if (isShared && token) {
        const fullUrl = `${window.location.origin}/share/${token}/`;
        if (urlInput) urlInput.value = fullUrl;
        if (openLink) openLink.href = fullUrl;
        if (activePanel) activePanel.style.display = 'block';
        if (inactivePanel) inactivePanel.style.display = 'none';
        if (disableBtn) disableBtn.style.display = 'inline-block';
    } else {
        if (activePanel) activePanel.style.display = 'none';
        if (inactivePanel) inactivePanel.style.display = 'block';
        if (disableBtn) disableBtn.style.display = 'none';
    }

    openModal('modal-share-note');
};

window.executeToggleShare = function(action) {
    if (!window.currentShareNoteId) return;
    const formData = new FormData();
    formData.append('action', action);

    fetch(`/app/${window.currentShareNoteId}/share/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'ok') {
            window.openShareModal(window.currentShareNoteId, data.is_shared, data.token);
            const headerBtn = document.getElementById('btn-share-header');
            if (headerBtn) {
                if (data.is_shared) {
                    headerBtn.classList.add('active');
                } else {
                    headerBtn.classList.remove('active');
                }
            }
        }
    })
    .catch(err => {
        console.error('[skdnote] Erro ao alternar compartilhamento:', err);
        alert('Não foi possível alterar o compartilhamento da anotação.');
    });
};

window.copyModalShareLink = function() {
    const input = document.getElementById('share-url-input');
    if (!input || !input.value) return;
    navigator.clipboard.writeText(input.value).then(() => {
        const btn = document.getElementById('share-copy-btn');
        if (btn) btn.textContent = 'Copiado! ✓';
        setTimeout(() => {
            if (btn) btn.textContent = 'Copiar';
        }, 2000);
    }).catch(() => {
        input.select();
        document.execCommand('copy');
    });
};

// Funções de Gestão de Etiquetas / Tags (UpNote Style)
window.toggleTagDropdown = function(e) {
    if (e && e.stopPropagation) e.stopPropagation();
    const dd = document.getElementById('dropdown-tag-selector');
    if (!dd) return;
    const isVisible = dd.style.display !== 'none';
    closeAllPopovers();
    if (!isVisible) {
        dd.style.display = 'block';
        const inp = document.getElementById('quick-tag-input');
        if (inp) { inp.focus(); inp.value = ''; }
    }
};

window.handleQuickTagInputKeydown = function(e, noteId) {
    if (e.key === 'Enter') {
        e.preventDefault();
        const val = e.target.value.trim().replace('#', '');
        if (!val) return;
        window.toggleTagOnCurrentNote(noteId, null, val);
        e.target.value = '';
    }
};

window.toggleTagOnCurrentNote = function(noteId, tagId, tagName) {
    if (!noteId) {
        const idInput = document.getElementById('current-note-id');
        noteId = idInput ? idInput.value : null;
    }
    if (!noteId) return;

    const csrf = getCsrfToken();
    const body = new URLSearchParams();
    if (tagId) body.append('tag_id', tagId);
    if (tagName) body.append('name', tagName);

    fetch(`/app/${noteId}/tags/toggle/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrf,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: body.toString()
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'ok') {
            window.renderNoteTags(data.tags, noteId);
        }
    });
};

window.renderNoteTags = function(tags, noteId) {
    const list = document.getElementById('editor-tags-list');
    if (list) {
        if (!tags || tags.length === 0) {
            list.innerHTML = '<span id="no-tags-placeholder" style="font-size: 12px; color: var(--text-faint); font-style: italic;">Sem etiquetas (digite #etiqueta no texto ou adicione ao lado)</span>';
        } else {
            let html = '';
            for (let i = 0; i < tags.length; i++) {
                const t = tags[i];
                html += `<span class="editor-tag-chip" data-tag-id="${t.id}" style="display: inline-flex; align-items: center; gap: 5px; background: rgba(129, 140, 248, 0.12); color: ${t.color}; border: 1px solid rgba(129, 140, 248, 0.25); border-radius: 6px; padding: 2px 8px; font-size: 11.5px; font-weight: 600;">` +
                        `<span>#${t.name}</span>` +
                        `<button type="button" onclick="toggleTagOnCurrentNote('${noteId}', '${t.id}')" style="background:none; border:none; color:inherit; font-size:13px; line-height:1; cursor:pointer; padding:0; opacity:0.75;" title="Remover etiqueta">&times;</button>` +
                        `</span>`;
            }
            list.innerHTML = html;
        }
    }

    // Atualiza tags no card correspondente na coluna de lista
    const cardTags = document.getElementById(`card-tags-${noteId}`);
    if (cardTags) {
        if (!tags || tags.length === 0) {
            cardTags.innerHTML = '';
        } else {
            let cardHtml = '';
            for (let j = 0; j < tags.length; j++) {
                const cTag = tags[j];
                cardHtml += `<span class="note-card-tag-pill" style="font-size: 10.5px; color: ${cTag.color}; background: rgba(129, 140, 248, 0.1); border-radius: 4px; padding: 1px 6px; font-weight: 500;">#${cTag.name}</span>`;
            }
            cardTags.innerHTML = cardHtml;
        }
    }

    // Atualiza os checks dentro do dropdown
    if (tags) {
        const activeTagIds = tags.map(t => t.id);
        document.querySelectorAll('.quick-tag-item').forEach(item => {
            const check = item.querySelector('.tag-status-icon');
            if (check) {
                const checkId = check.id.replace('tag-check-', '');
                check.textContent = activeTagIds.indexOf(checkId) !== -1 ? '✓' : '';
            }
        });
    }
};

window.deleteTagItem = function(tagId, tagName) {
    if (!confirm(`Deseja excluir a etiqueta #${tagName}? Ela será removida das anotações.`)) return;
    const csrf = getCsrfToken();
    fetch(`/app/tags/${tagId}/delete/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(() => {
        const el = document.getElementById(`nav-tag-wrapper-${tagId}`);
        if (el) el.remove();
        document.querySelectorAll(`.editor-tag-chip[data-tag-id="${tagId}"]`).forEach(chip => chip.remove());
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('tag') === tagId) {
            window.location.href = '/app/';
        }
    });
};
