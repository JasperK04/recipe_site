function updateNavbarModerationBadge(pendingCount) {
    document.querySelectorAll("[data-recipe-moderation-badge]").forEach(badge => {
        badge.classList.toggle("d-none", pendingCount <= 0)
    })
}

function updateRecipeStatusBadge(row, status) {
    const badge = row.querySelector('[data-label="Status"] .badge')
    if (!badge) {
        return
    }

    badge.className = "badge"
    if (status === "public") {
        badge.classList.add("bg-success")
        badge.textContent = "Openbaar"
    } else if (status === "private") {
        badge.classList.add("bg-secondary")
        badge.textContent = "Privé"
    } else {
        badge.classList.add("bg-danger")
        badge.textContent = "Gedeactiveerd"
    }
}

function updateRecipeModerationBadge(row, moderationStatus) {
    const badge = row.querySelector('[data-label="Moderatie"] .badge')
    if (!badge) {
        return
    }

    badge.className = "badge"
    if (moderationStatus === "flagged") {
        badge.classList.add("bg-danger")
        badge.textContent = "Gevlagd"
    } else {
        badge.classList.add("bg-success")
        badge.textContent = "Toegestaan"
    }
}

function updateRecipeAction(form, status) {
    const button = form.querySelector('button[type="submit"]')
    if (!button) {
        return
    }

    if (status === "deactivated") {
        form.action = form.dataset.reactivateEndpoint
        button.className = "btn btn-sm btn-outline-success"
        button.textContent = "Reactiveer"
    } else {
        form.action = form.dataset.deactivateEndpoint
        button.className = "btn btn-sm btn-outline-danger"
        button.textContent = "Deactiveer"
    }
}

function updateModerationAction(form, moderationStatus) {
    const button = form.querySelector('button[type="submit"]')
    if (!button) {
        return
    }

    if (moderationStatus === "flagged") {
        form.action = form.dataset.allowEndpoint
        button.className = "btn btn-sm btn-outline-success"
        button.textContent = "Sta toe"
    } else {
        form.remove()
    }
}

document.addEventListener("submit", async event => {
    const form = event.target.closest("form[data-admin-recipe-toggle='1']")
    const moderationForm = event.target.closest("form[data-admin-recipe-moderation='1']")
    if (!form && !moderationForm) {
        return
    }

    event.preventDefault()

    const activeForm = form || moderationForm
    const submitButton = activeForm.querySelector("button[type='submit']")
    const row = activeForm.closest("tr")
    if (submitButton) {
        submitButton.disabled = true
    }

    try {
        const response = await fetch(activeForm.action, {
            method: activeForm.method || "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
            body: new FormData(activeForm),
            credentials: "same-origin",
        })

        const data = await response.json()
        if (!response.ok || data.status !== "ok") {
            throw new Error(data.message || "Actie mislukt.")
        }

        if (row && data.new_status) {
            updateRecipeStatusBadge(row, data.new_status)
            if (activeForm.dataset.adminRecipeToggle === "1") {
                updateRecipeAction(activeForm, data.new_status)
            }
        }
        if (row && data.moderation_status) {
            updateRecipeModerationBadge(row, data.moderation_status)
            updateModerationAction(activeForm, data.moderation_status)
        }
        if (typeof data.pending_recipe_moderation === "number") {
            updateNavbarModerationBadge(data.pending_recipe_moderation)
        }
    } catch (error) {
        window.alert(error.message || "Actie mislukt.")
    } finally {
        if (submitButton) {
            submitButton.disabled = false
        }
    }
})
