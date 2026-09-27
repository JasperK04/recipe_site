function showRelevantField() {
    const type = document.getElementById('upload_type')?.value;
    const fields = {
        'url-field': type === 'url',
        'textarea-field': type === 'textarea',
        'json-field': type === 'json',
        'example-json': type === 'json',
        'text-field': type === 'text',
        'blank-field': type === 'blank',
    };

    Object.entries(fields).forEach(([id, visible]) => {
        const field = document.getElementById(id);
        if (field) field.style.display = visible ? 'block' : 'none';
    });
}

document.addEventListener('DOMContentLoaded', () => {
    showRelevantField();
    document.getElementById('upload_type')?.addEventListener('change', showRelevantField);
});

window.addEventListener('pageshow', showRelevantField);