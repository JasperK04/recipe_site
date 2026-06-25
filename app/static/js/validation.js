(function () {
    const registry = {
        login(form) {
            const username = form.querySelector("#username");
            const password = form.querySelector("#password");
            let valid = true;

            valid = validateText(username, "Gebruikersnaam is verplicht.", { required: true, minLength: 1 }) && valid;
            valid = validateText(password, "Wachtwoord is verplicht.", { required: true, minLength: 1 }) && valid;
            return valid;
        },
        register(form) {
            const username = form.querySelector("#username");
            const email = form.querySelector("#email");
            const password = form.querySelector("#password");
            const confirmPassword = form.querySelector("#confirm_password");
            let valid = true;

            valid = validateText(username, "Gebruikersnaam moet tussen 3 en 80 tekens zijn.", {
                required: true,
                minLength: 3,
                maxLength: 80,
                pattern: /^[A-Za-z0-9_.-]+$/,
                patternMessage: "Gebruikersnaam mag alleen letters, cijfers, punt, streep of underscore bevatten.",
            }) && valid;
            valid = validateText(email, "Voer een geldig e-mailadres in.", {
                required: true,
                pattern: /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/,
            }) && valid;
            valid = validateText(password, "Wachtwoord moet minimaal 6 tekens lang zijn.", {
                required: true,
                minLength: 6,
            }) && valid;
            valid = validateText(confirmPassword, "Wachtwoorden moeten overeenkomen.", {
                required: true,
                match: password,
            }) && valid;
            return valid;
        },
        profileEdit(form) {
            const username = form.querySelector("#username");
            const email = form.querySelector("#email");
            const currentPassword = form.querySelector("#current_password");
            const newPassword = form.querySelector("#new_password");
            const confirmNewPassword = form.querySelector("#confirm_new_password");
            const wantsPasswordChange = Boolean(
                (newPassword && newPassword.value.trim()) ||
                (confirmNewPassword && confirmNewPassword.value.trim())
            );
            let valid = true;

            valid = validateText(username, "Gebruikersnaam moet tussen 3 en 80 tekens zijn.", {
                required: true,
                minLength: 3,
                maxLength: 80,
                pattern: /^[A-Za-z0-9_.-]+$/,
                patternMessage: "Gebruikersnaam mag alleen letters, cijfers, punt, streep of underscore bevatten.",
            }) && valid;
            valid = validateText(email, "Voer een geldig e-mailadres in.", {
                required: true,
                pattern: /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/,
            }) && valid;

            if (wantsPasswordChange) {
                valid = validateText(currentPassword, "Vul je huidige wachtwoord in om het wachtwoord te wijzigen.", {
                    required: true,
                }) && valid;
                valid = validateText(newPassword, "Wachtwoord moet minimaal 6 tekens lang zijn.", {
                    required: true,
                    minLength: 6,
                }) && valid;
                valid = validateText(confirmNewPassword, "Wachtwoorden moeten overeenkomen.", {
                    required: true,
                    match: newPassword,
                }) && valid;
            } else {
                clearFieldError(currentPassword);
                clearFieldError(newPassword);
                clearFieldError(confirmNewPassword);
            }

            return valid;
        },
        recipe(form) {
            const title = form.querySelector("#title");
            const description = form.querySelector("#description");
            const category = form.querySelector("#category");
            const servings = form.querySelector("#servings");
            const prepTime = form.querySelector("#prep_time");
            const cookTime = form.querySelector("#cook_time");
            const image = form.querySelector("#image");
            const ingredientsList = form.querySelector("#ingredients-list");
            const instructionsList = form.querySelector("#instructions-list");
            let valid = true;

            valid = validateText(title, "Titel moet minder dan 200 tekens bevatten.", {
                required: true,
                maxLength: 200,
            }) && valid;
            valid = validateText(description, "Beschrijving moet minder dan 500 tekens zijn.", {
                maxLength: 500,
            }) && valid;
            valid = validateRecipeList(ingredientsList, "Voeg minstens één ingrediënt toe.") && valid;
            valid = validateRecipeList(instructionsList, "Voeg minstens één instructiestap toe.") && valid;
            valid = validateIntegerField(prepTime) && valid;
            valid = validateIntegerField(cookTime) && valid;
            valid = validateIntegerField(servings) && valid;
            clearFieldError(category);
            valid = validateFileField(image, ["jpg", "jpeg", "png", "gif", "webp"], "Kies een geldige afbeelding (jpg, jpeg, png, gif of webp).") && valid;

            return valid;
        },
        upload(form) {
            const uploadType = form.querySelector("#upload_type");
            const url = form.querySelector("#url");
            const textarea = form.querySelector("#textarea");
            const jsonFile = form.querySelector("#json_file");
            const textFile = form.querySelector("#text_file");
            let valid = true;

            valid = validateSelectField(uploadType, "Ongeldig uploadtype.") && valid;

            switch (uploadType ? uploadType.value : "") {
                case "url":
                    valid = validateText(url, "Vul een URL in.", {
                        required: true,
                        pattern: /^(https?:\/\/)?(www\.)?[\w-]+(\.[\w-]+)+[/#?]?.*$/,
                        patternMessage: "Voer een geldige URL in.",
                    }) && valid;
                    clearFieldError(textarea);
                    clearFieldError(jsonFile);
                    clearFieldError(textFile);
                    break;
                case "textarea":
                    valid = validateText(textarea, "Vul de tekst van het recept in.", {
                        required: true,
                        maxLength: 5000,
                    }) && valid;
                    clearFieldError(url);
                    clearFieldError(jsonFile);
                    clearFieldError(textFile);
                    break;
                case "json":
                    valid = validateFileField(jsonFile, ["json", "jsonl"], "Upload een JSON-bestand.") && valid;
                    clearFieldError(url);
                    clearFieldError(textarea);
                    clearFieldError(textFile);
                    break;
                case "text":
                    valid = validateFileField(textFile, ["txt", "docs", "docx", "pdf"], "Upload een tekstbestand.") && valid;
                    clearFieldError(url);
                    clearFieldError(textarea);
                    clearFieldError(jsonFile);
                    break;
                default:
                    valid = false;
                    showFieldError(uploadType, "Ongeldig uploadtype.");
                    break;
            }

            return valid;
        },
    };

    const debounceTimers = new WeakMap();

    function getWrapper(target) {
        if (!target) {
            return null;
        }
        if (target.matches && target.matches(".mb-3, .col-md-3, .col-md-6, .col-md-9, .col-md-12, .list-group")) {
            return target;
        }
        return target.closest(".mb-3, .col-md-3, .col-md-6, .col-md-9, .col-md-12, .list-group") || target.parentElement;
    }

    function clearFieldError(target) {
        const wrapper = getWrapper(target);
        if (!wrapper) {
            return;
        }

        wrapper.querySelectorAll(".invalid-feedback.client-validation-feedback").forEach((node) => node.remove());
        wrapper.querySelectorAll(".is-invalid").forEach((node) => node.classList.remove("is-invalid"));
        wrapper.querySelectorAll("[aria-invalid='true']").forEach((node) => node.removeAttribute("aria-invalid"));
    }

    function showFieldError(target, message) {
        const wrapper = getWrapper(target);
        if (!wrapper) {
            return false;
        }

        clearFieldError(wrapper);

        const feedback = document.createElement("div");
        feedback.className = "invalid-feedback d-block client-validation-feedback";
        feedback.textContent = message;

        const field = target.matches && target.matches("input, textarea, select") ? target : wrapper.querySelector("input, textarea, select");
        if (field) {
            field.classList.add("is-invalid");
            field.setAttribute("aria-invalid", "true");
        }

        wrapper.appendChild(feedback);
        return false;
    }

    function validateText(field, message, options = {}) {
        if (!field) {
            return true;
        }

        clearFieldError(field);

        const value = String(field.value || "").trim();

        if (options.required && !value) {
            return showFieldError(field, message);
        }
        if (!value) {
            return true;
        }
        if (options.minLength && value.length < options.minLength) {
            return showFieldError(field, message);
        }
        if (options.maxLength && value.length > options.maxLength) {
            return showFieldError(field, message);
        }
        if (options.pattern && !options.pattern.test(value)) {
            return showFieldError(field, options.patternMessage || message);
        }
        if (options.match && value !== String(options.match.value || "").trim()) {
            return showFieldError(field, message);
        }

        return true;
    }

    function validateIntegerField(field) {
        if (!field) {
            return true;
        }

        clearFieldError(field);

        const value = String(field.value || "").trim();
        if (!value) {
            return true;
        }
        if (!/^-?\d+$/.test(value)) {
            return showFieldError(field, "Vul een geheel getal in.");
        }

        return true;
    }

    function validateSelectField(field, message = "Maak een geldige keuze.") {
        if (!field) {
            return true;
        }

        clearFieldError(field);

        if (!String(field.value || "").trim()) {
            return showFieldError(field, message);
        }

        return true;
    }

    function validateFileField(field, allowedExtensions, message) {
        if (!field) {
            return true;
        }

        clearFieldError(field);

        const file = field.files && field.files[0];
        if (!file) {
            return true;
        }

        const extension = file.name.split(".").pop().toLowerCase();
        if (!allowedExtensions.includes(extension)) {
            return showFieldError(field, message);
        }

        return true;
    }

    function validateRecipeList(list, message) {
        if (!list) {
            return true;
        }

        const wrapper = list.closest(".mb-3") || list;

        clearFieldError(wrapper);

        const values = Array.from(list.querySelectorAll("input, textarea"))
            .map((field) => String(field.value || "").trim())
            .filter(Boolean);

        if (values.length === 0) {
            return showFieldError(wrapper, message);
        }

        return true;
    }

    function validateForm(form) {
        const validator = registry[form.dataset.clientValidation];
        if (!validator) {
            return true;
        }

        return validator(form);
    }

    window.RecipeForms = {
        validateForm(form) {
            return validateForm(form);
        },
    };

    function validateField(form, field) {
        if (!field || !field.matches || !field.matches("input, textarea, select")) {
            return true;
        }

        const formType = form.dataset.clientValidation;

        switch (formType) {
            case "login":
                if (field.id === "username") {
                    return validateText(field, "Gebruikersnaam is verplicht.", { required: true, minLength: 1 });
                }
                if (field.id === "password") {
                    return validateText(field, "Wachtwoord is verplicht.", { required: true, minLength: 1 });
                }
                return true;
            case "register":
                if (field.id === "username") {
                    return validateText(field, "Gebruikersnaam moet tussen 3 en 80 tekens zijn.", {
                        required: true,
                        minLength: 3,
                        maxLength: 80,
                        pattern: /^[A-Za-z0-9_.-]+$/,
                        patternMessage: "Gebruikersnaam mag alleen letters, cijfers, punt, streep of underscore bevatten.",
                    });
                }
                if (field.id === "email") {
                    return validateText(field, "Voer een geldig e-mailadres in.", {
                        required: true,
                        pattern: /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/,
                    });
                }
                if (field.id === "password") {
                    return validateText(field, "Wachtwoord moet minimaal 6 tekens lang zijn.", {
                        required: true,
                        minLength: 6,
                    });
                }
                if (field.id === "confirm_password") {
                    const password = form.querySelector("#password");
                    return validateText(field, "Wachtwoorden moeten overeenkomen.", {
                        required: true,
                        match: password,
                    });
                }
                return true;
            case "profileEdit":
                if (field.id === "username") {
                    return validateText(field, "Gebruikersnaam moet tussen 3 en 80 tekens zijn.", {
                        required: true,
                        minLength: 3,
                        maxLength: 80,
                        pattern: /^[A-Za-z0-9_.-]+$/,
                        patternMessage: "Gebruikersnaam mag alleen letters, cijfers, punt, streep of underscore bevatten.",
                    });
                }
                if (field.id === "email") {
                    return validateText(field, "Voer een geldig e-mailadres in.", {
                        required: true,
                        pattern: /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/,
                    });
                }
                if (field.id === "current_password") {
                    const newPassword = form.querySelector("#new_password");
                    const confirmNewPassword = form.querySelector("#confirm_new_password");
                    if (newPassword && newPassword.value.trim()) {
                        return validateText(field, "Vul je huidige wachtwoord in om het wachtwoord te wijzigen.", {
                            required: true,
                        });
                    }
                    if (confirmNewPassword && confirmNewPassword.value.trim()) {
                        return validateText(field, "Vul je huidige wachtwoord in om het wachtwoord te wijzigen.", {
                            required: true,
                        });
                    }
                    clearFieldError(field);
                    return true;
                }
                if (field.id === "new_password") {
                    return validateText(field, "Wachtwoord moet minimaal 6 tekens lang zijn.", {
                        required: false,
                        minLength: 6,
                    });
                }
                if (field.id === "confirm_new_password") {
                    const newPassword = form.querySelector("#new_password");
                    return validateText(field, "Wachtwoorden moeten overeenkomen.", {
                        required: false,
                        match: newPassword,
                    });
                }
                return true;
            case "recipe":
                if (field.id === "title") {
                    return validateText(field, "Titel moet minder dan 200 tekens bevatten.", {
                        required: true,
                        maxLength: 200,
                    });
                }
                if (field.id === "description") {
                    return validateText(field, "Beschrijving moet minder dan 500 tekens zijn.", {
                        maxLength: 500,
                    });
                }
                if (field.id === "servings" || field.id === "prep_time" || field.id === "cook_time") {
                    return validateIntegerField(field);
                }
                if (field.id === "category") {
                    clearFieldError(field);
                    return true;
                }
                if (field.id === "image") {
                    return validateFileField(field, ["jpg", "jpeg", "png", "gif", "webp"], "Kies een geldige afbeelding (jpg, jpeg, png, gif of webp).");
                }
                if (field.closest && (field.closest("#ingredients-list") || field.closest("#instructions-list"))) {
                    const list = field.closest("#ingredients-list") || field.closest("#instructions-list");
                    const message = list.id === "ingredients-list"
                        ? "Voeg minstens één ingrediënt toe."
                        : "Voeg minstens één instructiestap toe.";
                    return validateRecipeList(list, message);
                }
                return true;
            case "upload":
                if (field.id === "upload_type") {
                    clearFieldError(form.querySelector("#url"));
                    clearFieldError(form.querySelector("#textarea"));
                    clearFieldError(form.querySelector("#json_file"));
                    clearFieldError(form.querySelector("#text_file"));
                    return validateSelectField(field, "Ongeldig uploadtype.");
                }
                if (field.id === "url") {
                    if (form.querySelector("#upload_type")?.value !== "url") {
                        clearFieldError(field);
                        return true;
                    }
                    return validateText(field, "Vul een URL in.", {
                        required: true,
                        pattern: /^(https?:\/\/)?(www\.)?[\w-]+(\.[\w-]+)+[/#?]?.*$/,
                        patternMessage: "Voer een geldige URL in.",
                    });
                }
                if (field.id === "textarea") {
                    if (form.querySelector("#upload_type")?.value !== "textarea") {
                        clearFieldError(field);
                        return true;
                    }
                    return validateText(field, "Vul de tekst van het recept in.", {
                        required: true,
                        maxLength: 5000,
                    });
                }
                if (field.id === "json_file") {
                    if (form.querySelector("#upload_type")?.value !== "json") {
                        clearFieldError(field);
                        return true;
                    }
                    return validateFileField(field, ["json", "jsonl"], "Upload een JSON-bestand.");
                }
                if (field.id === "text_file") {
                    if (form.querySelector("#upload_type")?.value !== "text") {
                        clearFieldError(field);
                        return true;
                    }
                    return validateFileField(field, ["txt", "docs", "docx", "pdf"], "Upload een tekstbestand.");
                }
                return true;
            default:
                return true;
        }
    }

    function scheduleValidation(form, field) {
        const currentTimer = debounceTimers.get(form);
        if (currentTimer) {
            window.clearTimeout(currentTimer);
        }

        const nextTimer = window.setTimeout(() => {
            validateField(form, field);
        }, 600);

        debounceTimers.set(form, nextTimer);
    }

    document.addEventListener("submit", async (event) => {
        const form = event.target.closest("form[data-client-validation]");

        if (form && window.RecipeForms && typeof window.RecipeForms.validateForm === "function") {
            if (!window.RecipeForms.validateForm(form)) {
                event.preventDefault();
                return;
            }
        }

        const apiForm = event.target.closest("form[data-api-form='1']");

        if (!apiForm) {
            return;
        }

        event.preventDefault();

        const submitButtons = Array.from(
            apiForm.querySelectorAll("button[type='submit'], input[type='submit']")
        );

        submitButtons.forEach((button) => {
            button.disabled = true;
        });

        try {
            const response = await fetch(apiForm.action, {
                method: apiForm.method || "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: new FormData(apiForm),
                credentials: "same-origin",
            });
            const data = await response.json();

            if (!response.ok || data.status === "error") {
                throw new Error(data.message || "Actie mislukt.");
            }

            if (data.redirect_url) {
                window.location.assign(data.redirect_url);
            }
        } catch (error) {
            window.alert(error.message || "Actie mislukt.");
        } finally {
            submitButtons.forEach((button) => {
                button.disabled = false;
            });
        }
    });

    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("form[data-client-validation]").forEach((form) => {
            form.addEventListener("input", (event) => scheduleValidation(form, event.target));
            form.addEventListener("focusout", (event) => validateField(form, event.target));
            form.addEventListener("change", (event) => scheduleValidation(form, event.target));

            if (form.dataset.clientValidationOnLoad === "1") {
                validateForm(form);
            }
        });
    });
})();
