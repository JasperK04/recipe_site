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

    updateImportStatus();
}

function updateImportStatus() {
    const type = document.getElementById('upload_type')?.value;
    const line = document.getElementById('recipe-editor-status-line');
    const text = document.getElementById('recipe-editor-status-text');
    if (!line || !text) return;

    const url = document.getElementById('url');
    const textarea = document.getElementById('textarea');
    const jsonFile = document.getElementById('json_file');
    const textFile = document.getElementById('text_file');
    let ready = false;
    let hasValue = false;

    switch (type) {
        case 'url':
            hasValue = Boolean(url?.value.trim());
            ready = Boolean(url?.value.trim()) && /^(https?:\/\/)?(www\.)?[\w-]+(\.[\w-]+)+[/#?]?.*$/.test(url.value.trim());
            break;
        case 'textarea':
            hasValue = Boolean(textarea?.value.trim());
            ready = hasValue && textarea.value.length <= 5000;
            break;
        case 'json':
            hasValue = Boolean(jsonFile?.files?.length);
            ready = hasValue && /\.(json|jsonl)$/i.test(jsonFile.value);
            break;
        case 'text':
            hasValue = Boolean(textFile?.files?.length);
            ready = hasValue && /\.(txt|docs|docx|pdf)$/i.test(textFile.value);
            break;
    }

    line.classList.toggle('is-ready', ready);
    text.textContent = ready
        ? 'Klaar om te importeren'
        : hasValue
            ? 'Controleer de brongegevens'
            : 'Vul de gekozen bron in';
}

document.addEventListener('DOMContentLoaded', () => {
    showRelevantField();
    document.getElementById('upload_type')?.addEventListener('change', showRelevantField);
    document.querySelector('[data-client-validation="upload"]')?.addEventListener('input', updateImportStatus);
    document.querySelector('[data-client-validation="upload"]')?.addEventListener('change', updateImportStatus);
});

window.addEventListener('pageshow', showRelevantField);
