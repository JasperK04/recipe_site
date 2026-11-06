(function () {
    function initializeSearch(form) {
        const input = form.querySelector('.navbar-search-input');
        const suggestions = form.querySelector('.navbar-search-suggestions');
        if (!input || !suggestions) return;

        let requestController = null;
        let hideTimeout = null;

        function clearSuggestions() {
            suggestions.replaceChildren();
            suggestions.hidden = true;
            input.setAttribute('aria-expanded', 'false');
        }

        function showSuggestions(results) {
            suggestions.replaceChildren();
            if (!results.length) {
                const empty = document.createElement('div');
                empty.className = 'list-group-item text-muted';
                empty.textContent = 'Geen resultaten gevonden.';
                suggestions.append(empty);
            } else {
                results.forEach(recipe => {
                    const result = document.createElement('a');
                    result.className = 'list-group-item list-group-item-action navbar-search-result';
                    result.href = recipe.url;
                    const details = document.createElement('span');
                    details.className = 'navbar-search-result-details';
                    const title = document.createElement('span');
                    title.textContent = recipe.title;
                    details.append(title);
                    if (recipe.description) {
                        const description = document.createElement('small');
                        description.className = 'text-muted';
                        description.textContent = recipe.description;
                        details.append(description);
                    }
                    const id = document.createElement('span');
                    id.className = 'text-muted';
                    id.textContent = '#' + recipe.id;
                    result.append(details, id);
                    suggestions.append(result);
                });
            }
            suggestions.hidden = false;
            input.setAttribute('aria-expanded', 'true');
        }

        input.addEventListener('input', async () => {
            const query = input.value.trim();
            window.clearTimeout(hideTimeout);
            requestController?.abort();
            if (!query) {
                clearSuggestions();
                return;
            }

            requestController = new AbortController();
            try {
                const response = await fetch('/recept/zoeken/suggesties?q=' + encodeURIComponent(query), {
                    signal: requestController.signal,
                });
                if (!response.ok || input.value.trim() !== query) return;
                const data = await response.json();
                showSuggestions(data.results || []);
            } catch (error) {
                if (error.name !== 'AbortError') clearSuggestions();
            }
        });

        input.addEventListener('focus', () => {
            window.clearTimeout(hideTimeout);
            if (input.value.trim()) input.dispatchEvent(new Event('input'));
        });
        input.addEventListener('blur', () => {
            hideTimeout = window.setTimeout(clearSuggestions, 150);
        });
    }

    function initializeTheme() {
        const body = document.documentElement;
        const toggle = document.getElementById('theme-toggle');
        const icon = document.getElementById('theme-icon');

        function applyTheme(theme) {
            const dark = theme === 'dark';
            body.classList.toggle('dark-mode', dark);
            body.classList.toggle('light-mode', !dark);
            body.style.colorScheme = theme;
            if (icon) icon.className = dark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
            if (toggle) toggle.setAttribute('title', dark ? 'Schakel naar licht thema' : 'Schakel naar donker thema');
        }

        applyTheme(body.classList.contains('dark-mode') ? 'dark' : 'light');

        toggle?.addEventListener('click', event => {
            event.preventDefault();
            const newTheme = body.classList.contains('dark-mode') ? 'light' : 'dark';
            try {
                localStorage.setItem('theme', newTheme);
            } catch (error) {
                // Theme preference is optional.
            }
            applyTheme(newTheme);
        });
    }

    function initializeRecipeBookmarks() {
        document.querySelectorAll('.recipe-card__bookmark-form').forEach(form => {
            form.addEventListener('submit', async event => {
                event.preventDefault();
                const button = form.querySelector('button');
                if (!button) return;
                button.disabled = true;
                try {
                    const response = await fetch(form.action, {
                        method: 'POST',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' },
                        body: new FormData(form),
                    });
                    const data = await response.json();
                    if (!response.ok || data.status !== 'ok') throw new Error(data.message || 'Actie mislukt.');
                    const bookmarkd = data.bookmarkd;
                    const icon = button.querySelector('i.bi');
                    icon?.classList.toggle('bi-bookmark-fill', bookmarkd);
                    icon?.classList.toggle('bi-bookmark', !bookmarkd);
                    button.title = bookmarkd ? 'Verwijderen uit opgeslagen recepten' : 'Opslaan';
                    const title = form.closest('.recipe-card')?.querySelector('.recipe-card__title')?.textContent.trim() || 'recept';
                    button.setAttribute('aria-label', `${bookmarkd ? 'Verwijder' : 'Sla op'} ${title}${bookmarkd ? ' uit opgeslagen recepten' : ''}`);
                    form.action = form.action.replace(/\/bookmark(?:-verwijderen)?$/, bookmarkd ? '/bookmark-verwijderen' : '/bookmark');
                } catch (error) {
                    console.error(error);
                } finally {
                    button.disabled = false;
                }
            });
        });
    }

    function initializePagination() {
        document.querySelectorAll('.pagination-page-input').forEach(input => {
            input.addEventListener('focus', () => {
                input.dataset.previousValue = input.value;
                input.value = '';
            });
            input.addEventListener('blur', () => {
                if (!input.value) input.value = input.dataset.previousValue || '';
            });
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.navbar-search').forEach(initializeSearch);
        initializeTheme();
        initializeRecipeBookmarks();
        initializePagination();
    });
})();
// Small native replacements for the navigation and modal interactions previously
// provided by Bootstrap. Modal's tiny compatibility surface keeps existing page
// scripts working while the styling and behavior remain application owned.
(function () {
    const openModal = modal => {
        if (!modal) return;
        modal.classList.add('show');
        modal.removeAttribute('aria-hidden');
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        document.body.classList.add('modal-open');
        modal.querySelector('button, a, input, select, textarea')?.focus();
    };
    const closeModal = modal => {
        if (!modal) return;
        modal.classList.remove('show');
        modal.setAttribute('aria-hidden', 'true');
        modal.removeAttribute('aria-modal');
        if (!document.querySelector('.modal.show')) document.body.classList.remove('modal-open');
    };

    window.bootstrap = window.bootstrap || {};
    window.bootstrap.Modal = class {
        constructor(element) { this.element = element; }
        static getInstance(element) { return element?._nativeModal || null; }
        static getOrCreateInstance(element) {
            if (!element) return null;
            return element._nativeModal || (element._nativeModal = new window.bootstrap.Modal(element));
        }
        show() { openModal(this.element); }
        hide() { closeModal(this.element); }
    };

    let lastMenuTrigger = null;

    function setNavigation(open) {
        const panel = document.getElementById('navbarNav');
        const toggler = document.querySelector('.navbar-toggler');
        if (!panel || !toggler) return;
        panel.classList.toggle('show', open);
        toggler.setAttribute('aria-expanded', String(open));
        toggler.setAttribute('aria-label', open ? 'Sluit navigatie' : 'Open navigatie');
        if (open) {
            lastMenuTrigger = toggler;
            panel.querySelector('a, input, button')?.focus();
        } else {
            lastMenuTrigger?.focus();
        }
    }

    document.addEventListener('click', event => {
        const toggler = event.target.closest('.navbar-toggler');
        if (toggler) {
            const panel = document.getElementById('navbarNav');
            setNavigation(!panel?.classList.contains('show'));
            return;
        }
        const modalTrigger = event.target.closest('[data-bs-toggle="modal"]');
        if (modalTrigger) {
            const target = document.querySelector(modalTrigger.getAttribute('data-bs-target'));
            if (target) { event.preventDefault(); window.bootstrap.Modal.getOrCreateInstance(target).show(); }
            return;
        }
        const dismiss = event.target.closest('[data-bs-dismiss="modal"]');
        if (dismiss) { closeModal(dismiss.closest('.modal')); return; }
        const alertDismiss = event.target.closest('[data-bs-dismiss="alert"]');
        if (alertDismiss) { alertDismiss.closest('.alert')?.remove(); return; }
        const dropdownToggle = event.target.closest('.dropdown-toggle[data-bs-toggle="dropdown"]');
        if (dropdownToggle) {
            event.preventDefault();
            const dropdown = dropdownToggle.closest('.dropdown');
            const open = dropdown?.classList.toggle('show') || false;
            dropdownToggle.setAttribute('aria-expanded', String(open));
            return;
        }
        if (event.target.classList.contains('modal')) closeModal(event.target);
        document.querySelectorAll('.dropdown.show').forEach(dropdown => {
            if (!dropdown.contains(event.target)) {
                dropdown.classList.remove('show');
                dropdown.querySelector('[data-bs-toggle="dropdown"]')?.setAttribute('aria-expanded', 'false');
            }
        });
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            if (document.getElementById('navbarNav')?.classList.contains('show')) setNavigation(false);
            document.querySelectorAll('.modal.show').forEach(closeModal);
            document.querySelectorAll('.dropdown.show').forEach(el => el.classList.remove('show'));
        }
    });
})();
