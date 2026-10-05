(function () {
    const instances = new WeakMap();
    let activeModal = null;

    function createInstance(element) {
        const instance = {
            show() {
                if (activeModal && activeModal !== element) {
                    hide(activeModal);
                }
                activeModal = element;
                element.hidden = false;
                document.body.classList.add("modal-open");
                window.requestAnimationFrame(() => element.classList.add("is-visible"));
                element.dispatchEvent(new Event("shown.bs.modal"));
                element.querySelector("input, button")?.focus();
            },
            hide() {
                hide(element);
            },
        };
        instances.set(element, instance);
        return instance;
    }

    function getInstance(element) {
        if (!element) return null;
        return instances.get(element) || createInstance(element);
    }

    function hide(element) {
        if (!element || element.hidden) return;
        element.classList.remove("is-visible");
        window.setTimeout(() => {
            element.hidden = true;
            if (activeModal === element) {
                activeModal = null;
                document.body.classList.remove("modal-open");
            }
            element.dispatchEvent(new Event("hidden.bs.modal"));
        }, 160);
    }

    window.RecipeModals = { getInstance, getOrCreateInstance: getInstance, hide };

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll(".form-modal").forEach(getInstance);
        document.addEventListener("click", (event) => {
            const target = event.target instanceof Element ? event.target : null;
            const opener = target?.closest("[data-modal-target]");
            const closer = target?.closest("[data-modal-close]");
            if (opener) {
                getInstance(document.getElementById(opener.dataset.modalTarget))?.show();
            } else if (closer) {
                hide(document.getElementById(closer.dataset.modalClose));
            } else if (target?.classList.contains("form-modal")) {
                hide(target);
            }
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && activeModal) hide(activeModal);
        });
    });
})();
