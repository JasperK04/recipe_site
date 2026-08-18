(function () {
    const statusText = {
        idle: "Link kopiëren",
        done: "Gekopieerd",
        fail: "Kopiëren mislukt",
    };

    async function copyText(value) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(value);
        }

        const temp = document.createElement("textarea");
        temp.value = value;
        temp.setAttribute("readonly", "readonly");
        temp.style.position = "absolute";
        temp.style.left = "-9999px";
        document.body.appendChild(temp);
        temp.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(temp);

        if (!ok) {
            throw new Error("copy failed");
        }
    }

    document.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-copy-link]");
        if (!button) {
            return;
        }

        const value = button.dataset.copyValue || "";
        const original = button.textContent;
        const originalClasses = button.dataset.originalClasses || button.className;
        button.dataset.originalClasses = originalClasses;

        try {
            await copyText(value);
            button.textContent = statusText.done;
            button.classList.remove("btn-outline-primary", "btn-success");
            button.classList.add("btn-success");
        } catch (error) {
            button.textContent = statusText.fail;
            button.classList.remove("btn-outline-primary", "btn-success");
            button.classList.add("btn-outline-danger");
        } finally {
            window.setTimeout(() => {
                button.textContent = original;
                button.className = originalClasses;
            }, 1200);
        }
    });
})();