document.addEventListener("DOMContentLoaded", () => {
	const confirmations = document.querySelectorAll("[data-danger-confirm]");
	confirmations.forEach(button => {
		const field = document.getElementById(button.dataset.dangerConfirm);
		const note = document.getElementById(button.dataset.dangerNote);
		if (!field) return;

		const updateButton = () => {
			button.disabled = !field.value.trim() || !field.checkValidity();
		};
		field.addEventListener("input", updateButton);
		field.closest(".form-modal")?.addEventListener("hidden.bs.modal", () => {
			field.value = "";
			updateButton();
		});
		button.addEventListener("click", () => {
			if (button.disabled) return;
			if (note) note.textContent = "Deze verwijderactie is nog niet beschikbaar.";
		});
		updateButton();
	});
});
