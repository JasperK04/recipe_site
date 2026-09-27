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
            if (icon) icon.className = dark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
            if (toggle) toggle.setAttribute('title', dark ? 'Schakel naar licht thema' : 'Schakel naar donker thema');
        }

        try {
            const stored = localStorage.getItem('theme');
            applyTheme(stored || (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
        } catch (error) {
            applyTheme('light');
        }

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

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.navbar-search').forEach(initializeSearch);
        initializeTheme();
    });
})();