document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-submit-on-change]').forEach(control => {
        control.addEventListener('change', () => control.form?.submit());
    });

    document.querySelectorAll('[data-confirm-message]').forEach(form => {
        form.addEventListener('submit', event => {
            if (!window.confirm(form.dataset.confirmMessage)) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll('[data-recipe-status]').forEach(button => {
        button.addEventListener('click', () => {
            const statusField = document.getElementById('status-field');
            if (statusField) statusField.value = button.dataset.recipeStatus;
        });
    });
});