(function () {
    const dialog = document.getElementById('cookie-consent');
    if (!dialog) return;
    const hasChoice = dialog.dataset.hasConsent === 'true';
    let previousFocus = null;

    function openDialog() {
        previousFocus = document.activeElement;
        dialog.hidden = false;
        document.body.classList.add('cookie-dialog-open');
        dialog.querySelector('[data-cookie-choice]')?.focus();
    }

    function closeDialog() {
        dialog.hidden = true;
        document.body.classList.remove('cookie-dialog-open');
        previousFocus?.focus?.();
    }

    async function saveChoice(analytics) {
        const buttons = dialog.querySelectorAll('[data-cookie-choice]');
        const error = dialog.querySelector('.cookie-error');
        buttons.forEach(button => { button.disabled = true; });
        error.hidden = true;
        try {
            const response = await fetch('/privacy/cookies/consent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                },
                body: JSON.stringify({ analytics }),
                credentials: 'same-origin',
            });
            if (!response.ok) throw new Error('Could not save consent');
            dialog.dataset.hasConsent = 'true';
            closeDialog();
        } catch (errorSaving) {
            error.hidden = false;
        } finally {
            buttons.forEach(button => { button.disabled = false; });
        }
    }

    dialog.addEventListener('click', event => {
        const button = event.target.closest('[data-cookie-choice]');
        if (button) saveChoice(button.dataset.cookieChoice === 'accept');
    });
    document.addEventListener('click', event => {
        if (event.target.closest('[data-open-cookie-settings]')) openDialog();
    });
    document.addEventListener('keydown', event => {
        if (dialog.hidden) return;
        if (event.key === 'Escape') event.preventDefault();
        if (event.key === 'Tab') {
            const focusable = [...dialog.querySelectorAll('a[href], button:not(:disabled)')];
            if (!focusable.length) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
    });

    if (!hasChoice()) openDialog();
})();
