(function () {
    function reindexList(container) {
        const items = Array.from(container.children).filter(item => item.classList?.contains('list-group-item'));
        items.forEach((item, index) => {
            item.dataset.index = index;
            item.querySelectorAll('input, select, textarea').forEach(input => {
                if (!input.name) return;
                input.name = input.name.replace(/-(\d+)-/, `-${index}-`).replace(/-(\d+)$/, `-${index}`);
                if (input.id) input.id = input.id.replace(/-(\d+)-/, `-${index}-`).replace(/-(\d+)$/, `-${index}`);
            });
            item.classList.remove('sortable-disabled');
        });
        const last = items[items.length - 1];
        const input = last?.querySelector('input, textarea');
        if (input && !input.value.trim()) last.classList.add('sortable-disabled');
    }

    function resetIngredientItem(item) {
        if (!item.classList.contains('ingredient-item')) return;
        const input = item.querySelector('input, textarea, select');
        input?.classList.remove('nested-recipe-selected');
        if (input) delete input.dataset.rawIngredientJson;
        item.classList.remove('has-imported-recipe');
        item.querySelector('.imported-indicator')?.classList.remove('is-visible');
    }

    function ensureOneEmptyAtEnd(list) {
        if (!list) return;
        const items = Array.from(list.querySelectorAll('.list-group-item'));
        const emptyItems = [];
        items.forEach(item => {
            const input = item.querySelector('input, textarea');
            if (!input || !input.value.trim()) {
                resetIngredientItem(item);
                emptyItems.push(item);
            }
        });
        emptyItems.slice(1).forEach(item => item.remove());
        let empty = emptyItems[0];
        if (!empty) {
            empty = items[items.length - 1]?.cloneNode(true);
            if (!empty) return;
            empty.querySelectorAll('input, textarea, select').forEach(input => { input.value = ''; });
            resetIngredientItem(empty);
        }
        list.appendChild(empty);
        reindexList(list);
    }

    function attachTouchReorder(list) {
        let dragState = null;
        const moveItem = (item, reference) => {
            const positions = new Map(Array.from(list.children)
                .filter(child => child.classList?.contains('list-group-item'))
                .map(child => [child, child.getBoundingClientRect()]));
            list.insertBefore(item, reference);
            positions.forEach((before, child) => {
                const offsetY = before.top - child.getBoundingClientRect().top;
                if (offsetY && typeof child.animate === 'function') {
                    child.animate([{ transform: `translateY(${offsetY}px)` }, { transform: 'translateY(0)' }], { duration: 150, easing: 'ease-out' });
                }
            });
        };
        const finish = event => {
            if (!dragState || event.pointerId !== dragState.pointerId) return;
            if (dragState.handle.hasPointerCapture?.(event.pointerId)) dragState.handle.releasePointerCapture(event.pointerId);
            dragState.item.classList.remove('touch-reordering');
            dragState = null;
            ensureOneEmptyAtEnd(list);
        };

        list.addEventListener('pointerdown', event => {
            const target = event.target instanceof Element ? event.target : null;
            const handle = target?.closest('.drag-handle');
            const item = handle?.closest('.list-group-item');
            if (!handle || !item || item.classList.contains('sortable-disabled')) return;
            dragState = { handle, item, pointerId: event.pointerId, startY: event.clientY, isDragging: false };
            handle.setPointerCapture(event.pointerId);
            event.preventDefault();
        });
        list.addEventListener('pointermove', event => {
            if (!dragState || event.pointerId !== dragState.pointerId) return;
            if (!dragState.isDragging) {
                if (Math.abs(event.clientY - dragState.startY) < 4) return;
                dragState.isDragging = true;
                dragState.item.classList.add('touch-reordering');
            }
            const target = document.elementFromPoint(event.clientX, event.clientY)?.closest('.list-group-item');
            if (!target || target.parentElement !== list || target === dragState.item) return;
            const bounds = target.getBoundingClientRect();
            moveItem(dragState.item, event.clientY < bounds.top + bounds.height / 2 ? target : target.nextElementSibling);
            event.preventDefault();
        });
        list.addEventListener('pointerup', finish);
        list.addEventListener('pointercancel', finish);
    }

    function attachListHandlers(listSelector, itemSelector, isIngredient) {
        const list = document.querySelector(listSelector);
        if (!list || typeof Sortable === 'undefined') return;
        const useTouchReorder = window.matchMedia('(pointer: coarse)').matches && 'PointerEvent' in window;
        new Sortable(list, {
            animation: 150,
            handle: '.drag-handle',
            disabled: useTouchReorder,
            onMove(event) { return !event.dragged.classList.contains('sortable-disabled'); },
            onEnd(event) {
                window.requestAnimationFrame(() => {
                    if (Number.isInteger(event.newIndex) && event.item.parentElement === list) {
                        const items = Array.from(list.children).filter(item => item.classList?.contains('list-group-item') && item !== event.item);
                        list.insertBefore(event.item, items[event.newIndex] || null);
                    }
                    ensureOneEmptyAtEnd(list);
                });
            },
        });
        if (useTouchReorder) attachTouchReorder(list);
        list.addEventListener('input', event => {
            const target = event.target;
            const items = Array.from(list.querySelectorAll(itemSelector));
            const last = items[items.length - 1];
            if (last && target.closest(itemSelector) === last && target.value.trim()) {
                const clone = last.cloneNode(true);
                clone.querySelectorAll('input, textarea, select').forEach(input => { input.value = ''; });
                resetIngredientItem(clone);
                list.appendChild(clone);
                ensureOneEmptyAtEnd(list);
            }
            if (isIngredient && target.matches('input, textarea, select') && !target.value.trim()) resetIngredientItem(target.closest('.ingredient-item'));
        });
        list.addEventListener('focusout', event => {
            if (event.target.matches('input, textarea, select') && !event.target.value.trim()) window.setTimeout(() => ensureOneEmptyAtEnd(list), 50);
        });
    }

    function ingredientToDisplayString(value) {
        if (!value || typeof value !== 'object') return String(value ?? '');
        const parts = [];
        if (value.quantity !== undefined && value.quantity !== null && value.quantity !== '') parts.push(String(value.quantity));
        if (value.unit) parts.push(String(value.unit));
        if (value.display_name || value.name || value.name_) parts.push(String(value.display_name || value.name || value.name_));
        return parts.join(' ');
    }

    document.addEventListener('DOMContentLoaded', () => {
        const ingredientsList = document.getElementById('ingredients-list');
        const instructionsList = document.getElementById('instructions-list');
        if (!ingredientsList && !instructionsList) return;
        attachListHandlers('#ingredients-list', '.ingredient-item', true);
        attachListHandlers('#instructions-list', '.instruction-item', false);
        ensureOneEmptyAtEnd(ingredientsList);
        ensureOneEmptyAtEnd(instructionsList);

        ingredientsList?.querySelectorAll('input, textarea, select').forEach(input => {
            const raw = input.value.trim();
            if (!raw.startsWith('{')) return;
            try {
                const parsed = JSON.parse(raw);
                if (!parsed || typeof parsed !== 'object') return;
                input.dataset.rawIngredientJson = raw;
                input.value = ingredientToDisplayString(parsed);
                if (parsed.type === 'recipe') {
                    input.closest('.ingredient-item')?.classList.add('has-imported-recipe');
                    input.closest('.ingredient-item')?.querySelector('.imported-indicator')?.classList.add('is-visible');
                }
            } catch (error) {
                // Plain text ingredient values are valid input.
            }
        });

        const modal = document.getElementById('nestedRecipeModal');
        const search = document.getElementById('nestedRecipeSearch');
        const results = document.getElementById('nestedRecipeResults');
        const displayName = document.getElementById('nestedRecipeDisplayName');
        const quantity = document.getElementById('nestedRecipeQuantity');
        const unit = document.getElementById('nestedRecipeUnit');
        const confirmButton = document.getElementById('nestedRecipeConfirmBtn');
        if (!modal || !search || !results || !displayName || !quantity || !unit || !confirmButton) return;
        let selectedRecipe = null;

        function renderResults(items, hasMore) {
            results.replaceChildren();
            if (!items.length) {
                results.innerHTML = '<div class="list-group-item text-muted">Geen resultaten gevonden.</div>';
                confirmButton.disabled = true;
                selectedRecipe = null;
                return;
            }
            items.forEach(item => {
                const row = document.createElement('button');
                row.type = 'button';
                row.className = 'list-group-item list-group-item-action nested-recipe-result';
                row.innerHTML = `<span>${item.title}</span><span class="text-muted">#${item.id}</span>`;
                row.addEventListener('click', () => {
                    selectedRecipe = item;
                    displayName.value = item.title;
                    confirmButton.disabled = false;
                    results.querySelectorAll('.nested-recipe-result').forEach(element => element.classList.remove('active'));
                    row.classList.add('active');
                });
                results.appendChild(row);
            });
            if (hasMore) {
                const more = document.createElement('div');
                more.className = 'list-group-item nested-recipe-more text-muted';
                more.textContent = '+ meer';
                results.appendChild(more);
            }
        }

        search.addEventListener('input', async () => {
            const query = search.value.trim();
            if (!query) { results.replaceChildren(); confirmButton.disabled = true; selectedRecipe = null; return; }
            const response = await fetch(`/recept/genest/zoeken?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            renderResults(data.results || [], !!data.has_more);
        });
        document.querySelectorAll('.nested-recipe-trigger').forEach(button => button.addEventListener('click', () => {
            selectedRecipe = null;
            displayName.value = '';
            quantity.value = '1';
            unit.value = '';
            search.value = '';
            results.replaceChildren();
            confirmButton.disabled = true;
        }));
        confirmButton.addEventListener('click', () => {
            if (!selectedRecipe || !ingredientsList) return;
            const payload = { type: 'recipe', recipe_id: selectedRecipe.id, display_name: displayName.value.trim() || selectedRecipe.title, quantity: Number(quantity.value) || 1, unit: unit.value.trim() || '' };
            const emptyItem = Array.from(ingredientsList.querySelectorAll('.ingredient-item')).find(item => !item.querySelector('input')?.value.trim());
            if (!emptyItem) return;
            const importedItem = emptyItem.cloneNode(true);
            resetIngredientItem(importedItem);
            const input = importedItem.querySelector('input');
            input.dataset.rawIngredientJson = JSON.stringify(payload);
            input.value = ingredientToDisplayString(payload);
            input.classList.add('nested-recipe-selected');
            importedItem.classList.add('has-imported-recipe');
            importedItem.querySelector('.imported-indicator')?.classList.add('is-visible');
            ingredientsList.insertBefore(importedItem, emptyItem);
            reindexList(ingredientsList);
            bootstrap.Modal.getInstance(modal)?.hide();
        });
    });
})();