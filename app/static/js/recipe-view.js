document.addEventListener('DOMContentLoaded', () => {
    const shareModal = document.getElementById('shareModal');
    if (shareModal) {
        const pageUrl = shareModal.dataset.shareUrl || window.location.href;
        const shareTitle = shareModal.dataset.shareTitle || document.title;
        const shareText = shareModal.dataset.shareText || shareTitle;
        const encodedUrl = encodeURIComponent(pageUrl);
        const encodedText = encodeURIComponent(`${shareTitle} - ${shareText}`);
        const copyButton = document.getElementById('copyShareLinkBtn');
        const shareInput = document.getElementById('shareLinkInput');

        if (document.getElementById('whatsappShareBtn')) document.getElementById('whatsappShareBtn').href = `https://wa.me/?text=${encodedText}%20${encodedUrl}`;
        if (document.getElementById('facebookShareBtn')) document.getElementById('facebookShareBtn').href = `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`;
        if (document.getElementById('xShareBtn')) document.getElementById('xShareBtn').href = `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedUrl}`;
        copyButton?.addEventListener('click', () => {
            const input = shareInput || Object.assign(document.createElement('textarea'), { value: pageUrl });
            if (!shareInput) {
                input.style.position = 'fixed';
                input.style.left = '-9999px';
                document.body.append(input);
            }
            input.focus();
            input.select();
            const copied = document.execCommand('copy');
            if (!shareInput) input.remove();
            copyButton.classList.toggle('btn-success', copied);
            copyButton.classList.toggle('btn-outline-primary', !copied);
            copyButton.classList.toggle('is-pressed', copied);
            if (copied) window.setTimeout(() => {
                copyButton.classList.remove('btn-success', 'is-pressed');
                copyButton.classList.add('btn-outline-primary');
            }, 1500);
        });
    }

    const favoriteForm = document.querySelector('.fav-form');
    favoriteForm?.addEventListener('submit', async event => {
        event.preventDefault();
        const button = favoriteForm.querySelector('button');
        if (!button) return;
        button.disabled = true;
        try {
            const response = await fetch(favoriteForm.action, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' }, body: new FormData(favoriteForm) });
            const data = await response.json();
            if (!response.ok || data.status !== 'ok') throw new Error(data.message || 'Actie mislukt.');
            const icon = button.querySelector('i.bi');
            icon?.classList.toggle('bi-heart-fill', data.favorited);
            icon?.classList.toggle('bi-heart', !data.favorited);
            button.title = data.favorited ? 'Verwijderen uit favorieten' : 'Toevoegen aan favorieten';
            favoriteForm.action = favoriteForm.action.replace(data.favorited ? '/favorite' : '/unfavorite', data.favorited ? '/unfavorite' : '/favorite');
        } catch (error) {
            console.error(error);
        } finally {
            button.disabled = false;
        }
    });

    const favoriteButton = favoriteForm?.querySelector('button');
    favoriteButton?.addEventListener('mouseenter', () => {
        const icon = favoriteButton.querySelector('i.bi');
        if (!icon || icon.classList.contains('bi-heart-fill')) {
            favoriteButton?.classList.add('faded');
            return;
        }
        icon.classList.add('hover-fill', 'bi-heart-fill');
        icon.classList.remove('bi-heart');
        favoriteButton.classList.add('faded');
    });
    favoriteButton?.addEventListener('mouseleave', () => {
        const icon = favoriteButton.querySelector('i.bi');
        favoriteButton.classList.remove('faded');
        if (icon?.classList.contains('hover-fill')) {
            icon.classList.remove('hover-fill', 'bi-heart-fill');
            icon.classList.add('bi-heart');
        }
    });

    document.querySelectorAll('.moderate-form, .moderate-allow-form').forEach(form => {
        form.addEventListener('submit', async event => {
            event.preventDefault();
            const button = form.querySelector('button');
            if (!button) return;
            button.disabled = true;
            try {
                const response = await fetch(form.action, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' }, body: new FormData(form) });
                const data = await response.json();
                if (!response.ok || data.status !== 'ok') throw new Error(data.message || 'Actie mislukt.');
                if (form.classList.contains('moderate-allow-form')) {
                    document.querySelector('[data-recipe-moderation-alert="1"]')?.remove();
                    form.remove();
                } else {
                    const deactivated = data.new_status === 'deactivated';
                    button.className = deactivated ? 'btn btn-outline-success' : 'btn btn-outline-danger';
                    button.innerHTML = deactivated ? '<i class="bi bi-eye"></i>' : '<i class="bi bi-eye-slash"></i>';
                    button.title = deactivated ? 'Recept reactiveren' : 'Recept deactiveren';
                    form.action = form.action.replace(deactivated ? '/deactivate' : '/reactivate', deactivated ? '/reactivate' : '/deactivate');
                }
                if (typeof data.pending_recipe_moderation === 'number') document.querySelectorAll('[data-recipe-moderation-badge]').forEach(badge => badge.classList.toggle('d-none', data.pending_recipe_moderation <= 0));
            } catch (error) {
                console.error(error);
            } finally {
                button.disabled = false;
            }
        });
    });

    const scoreForm = document.getElementById('score-form');
    if (scoreForm) {
        const stars = [...scoreForm.querySelectorAll('.score-star')];
        const input = scoreForm.querySelector('#score-input');
        const badge = document.getElementById('recipe-score-badge');
        const count = document.getElementById('recipe-score-count');
        const setStars = value => stars.forEach((button, index) => {
            const icon = button.querySelector('i.bi');
            icon?.classList.toggle('bi-star-fill', index < value);
            icon?.classList.toggle('bi-star', index >= value);
            button.classList.remove('faded');
        });
        const render = () => setStars(Number(input.value) || 0);
        if (scoreForm.dataset.ownerDisabled === '1') render();
        else stars.forEach((button, index) => {
            button.addEventListener('mouseenter', () => { setStars(index + 1); stars.slice(0, index + 1).forEach(item => item.classList.add('faded')); });
            button.addEventListener('mouseleave', render);
            button.addEventListener('click', async () => {
                input.value = index + 1;
                stars.forEach(item => { item.disabled = true; });
                try {
                    const response = await fetch(scoreForm.action, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest' }, body: new FormData(scoreForm) });
                    const data = await response.json();
                    if (!response.ok || data.status !== 'ok') throw new Error(data.message || 'Actie mislukt.');
                    setStars(data.score);
                    if (badge) badge.textContent = `Score ${Number(data.score_average).toFixed(1)}/5`;
                    if (count) count.textContent = `(${data.score_count})`;
                } catch (error) { console.error(error); }
                stars.forEach(item => { item.disabled = false; });
            });
        });
    }

    const servingDisplay = document.getElementById('current-serving-count');
    const quantities = [...document.querySelectorAll('[data-original-quantity]')];
    if (servingDisplay) {
        const format = value => Number.isInteger(Math.round(value * 100) / 100) ? String(Math.round(value * 100) / 100) : String(Math.round(value * 100) / 100).replace(/\.0+$/, '').replace(/(\.\d*[1-9])0+$/, '$1').replace('.', ',');
        const update = servings => {
            const base = Number(servingDisplay.dataset.baseServings || 1);
            const target = Math.max(1, Number(servings || base));
            servingDisplay.textContent = String(target);
            quantities.forEach(element => {
                const original = Number(element.dataset.originalQuantity);
                if (Number.isFinite(original)) element.textContent = format(original * (base > 0 ? target / base : 1));
            });
        };
        document.getElementById('servings-decrease')?.addEventListener('click', () => update(Number(servingDisplay.textContent) - 1));
        document.getElementById('servings-increase')?.addEventListener('click', () => update(Number(servingDisplay.textContent) + 1));
        update(servingDisplay.textContent);
    }
});