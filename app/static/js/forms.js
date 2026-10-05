(function () {
    function initializeSelect(wrapper) {
        const nativeSelect = wrapper.querySelector('[data-custom-select-native]');
        const trigger = wrapper.querySelector('.form-select-trigger');
        const menu = wrapper.querySelector('.form-select-menu');
        const options = Array.from(wrapper.querySelectorAll('.form-select-option'));
        if (!nativeSelect || !trigger || !menu || !options.length) return;

        wrapper.classList.add('has-custom-select');

        const sync = () => {
            const selected = options.find(option => option.dataset.value === nativeSelect.value) || options[0];
            trigger.textContent = selected.textContent;
            options.forEach(option => {
                const isSelected = option === selected;
                option.classList.toggle('is-selected', isSelected);
                option.setAttribute('aria-selected', String(isSelected));
            });
        };
        const close = () => {
            wrapper.classList.remove('is-open');
            trigger.setAttribute('aria-expanded', 'false');
        };
        const open = () => {
            wrapper.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
        };

        trigger.addEventListener('click', () => {
            if (wrapper.classList.contains('is-open')) close();
            else open();
        });
        trigger.addEventListener('keydown', event => {
            if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                open();
                options.find(option => option.classList.contains('is-selected'))?.focus();
            }
        });
        options.forEach(option => option.addEventListener('click', () => {
            nativeSelect.value = option.dataset.value || '';
            nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
            sync();
            close();
            trigger.focus();
        }));
        nativeSelect.addEventListener('change', sync);
        sync();
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-custom-select]').forEach(initializeSelect);
        document.addEventListener('click', event => {
            document.querySelectorAll('.form-select-wrap.is-open').forEach(wrapper => {
                if (!wrapper.contains(event.target)) {
                    wrapper.classList.remove('is-open');
                    wrapper.querySelector('.form-select-trigger')?.setAttribute('aria-expanded', 'false');
                }
            });
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') {
                document.querySelectorAll('.form-select-wrap.is-open').forEach(wrapper => {
                    wrapper.classList.remove('is-open');
                    wrapper.querySelector('.form-select-trigger')?.setAttribute('aria-expanded', 'false');
                });
            }
        });
    });
})();
