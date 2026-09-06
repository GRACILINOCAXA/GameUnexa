(() => {
    if (window.__gameLinkLibraryViewController) return;

    const validViews = new Set(['2d', '3d']);
    const storageKey = 'libraryView';
    const legacyStorageKey = 'gamelink_library_view';
    let libraryView = '3d';

    function normalizeView(value) {
        return validViews.has(value) ? value : '3d';
    }

    function closeMenus() {
        document.querySelectorAll('[data-library-view-menu]').forEach((menu) => {
            menu.hidden = true;
            menu.classList.remove('show');
        });
        document.querySelectorAll('[data-library-view-toggle]').forEach((toggle) => {
            toggle.setAttribute('aria-expanded', 'false');
        });
    }

    function updatePicker(view) {
        document.querySelectorAll('[data-library-view-picker]').forEach((picker) => {
            const label = picker.querySelector('[data-library-view-label]');
            if (label) label.textContent = view.toUpperCase();
            picker.querySelectorAll('[data-library-view-option]').forEach((option) => {
                const selected = option.dataset.libraryViewOption === view;
                option.classList.toggle('active', selected);
                option.setAttribute('aria-selected', selected ? 'true' : 'false');
            });
        });
    }

    function renderedView() {
        return normalizeView(document.body?.dataset.libraryView || document.querySelector('[data-library-view]')?.dataset.libraryView);
    }

    function loadLibraryView() {
        // The rendered document comes from the server and is the source of truth.
        libraryView = renderedView();
        return libraryView;
    }

    function saveLibraryView(view) {
        libraryView = normalizeView(view);
        localStorage.setItem(storageKey, libraryView);
        localStorage.removeItem(legacyStorageKey);
        return libraryView;
    }

    async function persistView(view) {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const response = await fetch('/jogar/configuracoes/estilo', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRF-Token': csrfToken,
            },
            body: new URLSearchParams({ library_view: view }),
        });
        const payload = await response.json().catch(() => null);
        if (!response.ok || !payload?.ok) {
            const detail = payload?.erro || `HTTP ${response.status}`;
            console.error('[MODE] Erro ao salvar modo:', detail);
            throw new Error(`Não foi possível salvar o modo da biblioteca (${detail}).`);
        }
        console.info('[MODE] Modo salvo:', view);
    }

    async function renderLibraryView(view) {
        view = normalizeView(view);
        if (renderedView() === view) {
            saveLibraryView(view);
            updatePicker(view);
            closeMenus();
            return;
        }

        closeMenus();
        document.documentElement.classList.add('library-view-switching');
        try {
            await persistView(view);
            saveLibraryView(view);
            window.location.assign(`/jogar?view=${encodeURIComponent(view)}`);
        } catch (error) {
            saveLibraryView(renderedView());
            window.alert(error.message || 'Não foi possível trocar a visualização da biblioteca.');
        } finally {
            document.documentElement.classList.remove('library-view-switching');
        }
    }

    async function switchLibraryView(view) {
        return renderLibraryView(view);
    }

    document.addEventListener('click', (event) => {
        const toggle = event.target.closest('[data-library-view-toggle]');
        if (toggle) {
            event.preventDefault();
            event.stopPropagation();
            const menu = toggle.closest('[data-library-view-picker]')?.querySelector('[data-library-view-menu]');
            if (!menu) return;
            const open = !menu.hidden;
            closeMenus();
            menu.hidden = open;
            menu.classList.toggle('show', !open);
            toggle.setAttribute('aria-expanded', open ? 'false' : 'true');
            return;
        }

        const option = event.target.closest('[data-library-view-option]');
        if (option) {
            event.preventDefault();
            event.stopPropagation();
            switchLibraryView(option.dataset.libraryViewOption).catch((error) => {
                console.error('[MODE] Erro ao trocar modo:', error);
            });
            return;
        }

        if (!event.target.closest('[data-library-view-picker]')) closeMenus();
    });

    document.addEventListener('DOMContentLoaded', () => {
        const currentView = renderedView();
        loadLibraryView();
        saveLibraryView(currentView);
        updatePicker(currentView);
    });

    window.__gameLinkLibraryViewController = {
        loadLibraryView,
        saveLibraryView,
        renderLibraryView,
        switchLibraryView,
    };
})();

