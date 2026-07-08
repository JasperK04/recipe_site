(function () {
    const ASPECT_RATIO = 320 / 180;
    const SMALL_SCREEN_QUERY = window.matchMedia("(max-width: 767.98px)");

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function getFileBaseName(name) {
        return String(name || "recipe-image").replace(/\.[^.]+$/, "");
    }

    function setInputFile(input, file) {
        if (!input) {
            return;
        }

        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        input.files = dataTransfer.files;
    }

    function revokeObjectUrl(url) {
        if (url && url.startsWith("blob:")) {
            URL.revokeObjectURL(url);
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const form = document.getElementById("recipe-form");
        if (!form) {
            return;
        }

        const cropEnabled = form.dataset.imageCropEnabled !== "0";
        const preview = document.getElementById("image-preview");
        const placeholder = document.getElementById("image-placeholder");
        const actions = document.getElementById("image-actions");
        const clearBtn = document.getElementById("image-clear-btn");
        const removeFlag = document.getElementById("remove_image");
        const fileInput = form.querySelector('input[type="file"][name="image"]');
        const imageFrame = document.querySelector(".image-frame");
        const originalPreviewSrc = preview ? (preview.dataset.originalSrc || "") : "";

        function showControls() {
            if (actions) {
                actions.style.display = "flex";
            }
        }

        function hideControls() {
            if (actions) {
                actions.style.display = "none";
            }
        }

        function showPlaceholder() {
            if (placeholder) {
                placeholder.hidden = false;
                placeholder.style.display = "flex";
            }
        }

        function hidePlaceholder() {
            if (placeholder) {
                placeholder.hidden = true;
                placeholder.style.display = "none";
            }
        }

        let previewObjectUrl = "";

        function showPreview(url, rememberObjectUrl = false) {
            if (!preview) {
                return;
            }

            preview.setAttribute("src", url);
            preview.style.display = "block";
            if (imageFrame) {
                imageFrame.style.display = "block";
            }
            hidePlaceholder();
            showControls();

            if (rememberObjectUrl) {
                if (previewObjectUrl && previewObjectUrl !== url) {
                    revokeObjectUrl(previewObjectUrl);
                }
                previewObjectUrl = url;
            }

        }

        function clearPreview() {
            if (previewObjectUrl) {
                revokeObjectUrl(previewObjectUrl);
                previewObjectUrl = "";
            }

            if (preview) {
                preview.removeAttribute("src");
                preview.style.display = "none";
            }

            if (imageFrame) {
                imageFrame.style.display = "none";
            }

            showPlaceholder();
            hideControls();
        }

        function restorePersistedPreview() {
            if (originalPreviewSrc && (!removeFlag || removeFlag.value !== "1")) {
                if (preview) {
                    preview.setAttribute("src", originalPreviewSrc);
                    preview.style.display = "block";
                }
                if (imageFrame) {
                    imageFrame.style.display = "block";
                }
                hidePlaceholder();
                showControls();
                return;
            }
            clearPreview();
        }

        const modalEl = document.getElementById("recipe-image-crop-modal");
        const cropStage = document.getElementById("recipe-image-crop-stage");
        const cropImage = document.getElementById("recipe-image-crop-image");
        const cropSelection = document.getElementById("recipe-image-crop-selection");
        const cropSlider = document.getElementById("recipe-image-crop-slider");
        const confirmBtn = document.getElementById("recipe-image-crop-confirm");
        const cropModal = modalEl && window.bootstrap ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;

        let pendingFile = null;
        let pendingFileUrl = "";
        let crop = null;
        let cropInitialized = false;
        let modalConfirmed = false;
        let cropSessionActive = false;
        let pendingStartWasEmpty = true;
        let pointerState = null;
        let currentSmallMode = SMALL_SCREEN_QUERY.matches;

        function setConfirmReady(isReady) {
            if (confirmBtn) {
                confirmBtn.disabled = !isReady;
            }
        }

        function getNaturalSize() {
            return {
                width: cropImage ? cropImage.naturalWidth : 0,
                height: cropImage ? cropImage.naturalHeight : 0,
            };
        }

        function getScale() {
            if (!cropImage || !cropImage.naturalWidth) {
                return 0;
            }

            return cropImage.getBoundingClientRect().width / cropImage.naturalWidth;
        }

        function getMaxCropWidth() {
            const { width, height } = getNaturalSize();
            if (!width || !height) {
                return 0;
            }

            return Math.min(width, height * ASPECT_RATIO);
        }

        function getMinCropWidth() {
            const maxWidth = getMaxCropWidth();
            if (!maxWidth) {
                return 0;
            }

            return Math.min(maxWidth, Math.max(96, Math.round(maxWidth * 0.3)));
        }

        function normalizeCrop(nextCrop) {
            const { width, height } = getNaturalSize();
            const maxWidth = getMaxCropWidth();
            const minWidth = getMinCropWidth();

            if (!width || !height || !maxWidth || !minWidth) {
                return nextCrop;
            }

            const cropWidth = clamp(nextCrop.width, minWidth, maxWidth);
            const cropHeight = cropWidth / ASPECT_RATIO;

            return {
                width: cropWidth,
                height: cropHeight,
                x: clamp(nextCrop.x, 0, width - cropWidth),
                y: clamp(nextCrop.y, 0, height - cropHeight),
            };
        }

        function centerCrop(width) {
            const { width: imageWidth, height: imageHeight } = getNaturalSize();
            const cropWidth = clamp(width, getMinCropWidth(), getMaxCropWidth());
            const cropHeight = cropWidth / ASPECT_RATIO;

            return normalizeCrop({
                width: cropWidth,
                height: cropHeight,
                x: (imageWidth - cropWidth) / 2,
                y: (imageHeight - cropHeight) / 2,
            });
        }

        function renderCrop() {
            if (!crop || !cropImage || !cropSelection) {
                return;
            }

            const scale = getScale();
            if (!scale) {
                return;
            }

            cropSelection.style.display = "block";
            cropSelection.style.left = `${crop.x * scale}px`;
            cropSelection.style.top = `${crop.y * scale}px`;
            cropSelection.style.width = `${crop.width * scale}px`;
            cropSelection.style.height = `${crop.height * scale}px`;

            if (cropSlider && currentSmallMode) {
                const minWidth = getMinCropWidth();
                const maxWidth = getMaxCropWidth();
                const ratio = maxWidth === minWidth ? 0 : (crop.width - minWidth) / (maxWidth - minWidth);
                cropSlider.value = String(Math.round(clamp(ratio, 0, 1) * 100));
            }
        }

        function syncMode() {
            if (!cropSelection) {
                return;
            }

            cropSelection.classList.toggle("is-resizing", Boolean(pointerState && pointerState.mode === "resize"));
        }

        function initializeCropper() {
            if (!cropImage || !cropImage.complete || !cropImage.naturalWidth || !cropImage.naturalHeight) {
                setConfirmReady(false);
                return;
            }

            currentSmallMode = SMALL_SCREEN_QUERY.matches;
            const initialWidth = Math.max(getMinCropWidth(), Math.round(getMaxCropWidth() * 0.9));
            crop = centerCrop(initialWidth);
            cropInitialized = true;
            renderCrop();
            setConfirmReady(true);
        }

        function resetCropperState() {
            crop = null;
            cropInitialized = false;
            pointerState = null;
            modalConfirmed = false;
            setConfirmReady(false);

            if (cropSelection) {
                cropSelection.style.display = "none";
                cropSelection.classList.remove("is-resizing");
            }

            if (cropImage) {
                cropImage.removeAttribute("src");
            }

            if (cropSlider) {
                cropSlider.value = "50";
            }
        }

        function discardPendingSelection() {
            if (pendingFileUrl) {
                revokeObjectUrl(pendingFileUrl);
            }
            pendingFileUrl = "";
            pendingFile = null;
            resetCropperState();
            if (fileInput) {
                fileInput.value = "";
            }
            if (removeFlag) {
                removeFlag.value = "0";
            }
            if (pendingStartWasEmpty) {
                clearPreview();
            } else {
                restorePersistedPreview();
            }
        }

        function setPendingFile(file) {
            pendingStartWasEmpty = !preview
                || !preview.getAttribute("src")
                || (removeFlag ? removeFlag.value === "1" : false)
                || (preview ? preview.style.display === "none" : false);
            hidePlaceholder();
            pendingFile = file;
            cropSessionActive = true;
            if (pendingFileUrl) {
                revokeObjectUrl(pendingFileUrl);
            }
            pendingFileUrl = URL.createObjectURL(file);
            resetCropperState();
            if (cropImage) {
                setConfirmReady(false);
                cropImage.src = pendingFileUrl;
            }
            if (cropModal) {
                cropModal.show();
            }
        }

        function resizeCrop(handle, startCrop, dx, dy) {
            const { width: imageWidth, height: imageHeight } = getNaturalSize();
            const minWidth = getMinCropWidth();

            let anchorX = 0;
            let anchorY = 0;
            let currentX = 0;
            let currentY = 0;
            let maxWidth = 0;
            let width = 0;

            switch (handle) {
                case "nw":
                    anchorX = startCrop.x + startCrop.width;
                    anchorY = startCrop.y + startCrop.height;
                    currentX = startCrop.x + dx;
                    currentY = startCrop.y + dy;
                    width = Math.max(anchorX - currentX, (anchorY - currentY) * ASPECT_RATIO);
                    maxWidth = Math.min(anchorX, anchorY * ASPECT_RATIO);
                    width = clamp(width, minWidth, maxWidth);
                    return normalizeCrop({
                        width,
                        height: width / ASPECT_RATIO,
                        x: anchorX - width,
                        y: anchorY - (width / ASPECT_RATIO),
                    });
                case "ne":
                    anchorX = startCrop.x;
                    anchorY = startCrop.y + startCrop.height;
                    currentX = startCrop.x + startCrop.width + dx;
                    currentY = startCrop.y + dy;
                    width = Math.max(currentX - anchorX, (anchorY - currentY) * ASPECT_RATIO);
                    maxWidth = Math.min(imageWidth - anchorX, anchorY * ASPECT_RATIO);
                    width = clamp(width, minWidth, maxWidth);
                    return normalizeCrop({
                        width,
                        height: width / ASPECT_RATIO,
                        x: anchorX,
                        y: anchorY - (width / ASPECT_RATIO),
                    });
                case "sw":
                    anchorX = startCrop.x + startCrop.width;
                    anchorY = startCrop.y;
                    currentX = startCrop.x + dx;
                    currentY = startCrop.y + startCrop.height + dy;
                    width = Math.max(anchorX - currentX, (currentY - anchorY) * ASPECT_RATIO);
                    maxWidth = Math.min(anchorX, (imageHeight - anchorY) * ASPECT_RATIO);
                    width = clamp(width, minWidth, maxWidth);
                    return normalizeCrop({
                        width,
                        height: width / ASPECT_RATIO,
                        x: anchorX - width,
                        y: anchorY,
                    });
                case "se":
                default:
                    anchorX = startCrop.x;
                    anchorY = startCrop.y;
                    currentX = startCrop.x + startCrop.width + dx;
                    currentY = startCrop.y + startCrop.height + dy;
                    width = Math.max(currentX - anchorX, (currentY - anchorY) * ASPECT_RATIO);
                    maxWidth = Math.min(imageWidth - anchorX, (imageHeight - anchorY) * ASPECT_RATIO);
                    width = clamp(width, minWidth, maxWidth);
                    return normalizeCrop({
                        width,
                        height: width / ASPECT_RATIO,
                        x: anchorX,
                        y: anchorY,
                    });
            }
        }

        function moveCrop(startCrop, dx, dy) {
            return normalizeCrop({
                width: startCrop.width,
                height: startCrop.height,
                x: startCrop.x + dx,
                y: startCrop.y + dy,
            });
        }

        async function cropPendingFile() {
            if (!pendingFile || !cropImage || !crop) {
                return null;
            }

            const canvas = document.createElement("canvas");
            canvas.width = Math.max(1, Math.round(crop.width));
            canvas.height = Math.max(1, Math.round(crop.height));

            const context = canvas.getContext("2d");
            if (!context) {
                return null;
            }

            context.drawImage(
                cropImage,
                crop.x,
                crop.y,
                crop.width,
                crop.height,
                0,
                0,
                canvas.width,
                canvas.height,
            );

            const blob = await new Promise((resolve) => {
                canvas.toBlob((value) => resolve(value), "image/webp", 0.92);
            }) || await new Promise((resolve) => {
                canvas.toBlob((value) => resolve(value), "image/png");
            });

            if (!blob) {
                return null;
            }

            const baseName = getFileBaseName(pendingFile.name);
            const mimeType = blob.type || "image/webp";
            const extension = mimeType === "image/png" ? "png" : "webp";
            const outputFile = new File([blob], `${baseName}-cropped.${extension}`, {
                type: mimeType,
            });
            return outputFile;
        }

        function finishCropConfirm() {
            modalConfirmed = true;
            if (cropModal) {
                cropModal.hide();
            }
        }

        if (SMALL_SCREEN_QUERY.addEventListener) {
            SMALL_SCREEN_QUERY.addEventListener("change", () => {
                currentSmallMode = SMALL_SCREEN_QUERY.matches;
                if (cropInitialized) {
                    renderCrop();
                }
            });
        }

        if (cropImage) {
            cropImage.addEventListener("load", () => {
                initializeCropper();
            });
        }

        if (modalEl) {
            modalEl.addEventListener("shown.bs.modal", () => {
                initializeCropper();
            });

            modalEl.addEventListener("hidden.bs.modal", () => {
                if (!cropSessionActive) {
                    return;
                }

                const shouldDiscard = !modalConfirmed;
                modalConfirmed = false;
                cropSessionActive = false;

                if (shouldDiscard) {
                    discardPendingSelection();
                } else {
                    if (pendingFileUrl) {
                        revokeObjectUrl(pendingFileUrl);
                    }
                    pendingFileUrl = "";
                    pendingFile = null;
                    resetCropperState();
                }
            });
        }

        if (cropSelection) {
            cropSelection.addEventListener("pointerdown", (event) => {
                if (!crop) {
                    return;
                }

                const handle = event.target instanceof Element
                    ? event.target.closest("[data-crop-handle]")?.dataset.cropHandle || ""
                    : "";

                pointerState = {
                    mode: handle ? "resize" : "move",
                    handle,
                    pointerId: event.pointerId,
                    startX: event.clientX,
                    startY: event.clientY,
                    startCrop: { ...crop },
                };

                cropSelection.setPointerCapture(event.pointerId);
                event.preventDefault();
                syncMode();
            });
        }

        if (document) {
            document.addEventListener("pointermove", (event) => {
                if (!pointerState || event.pointerId !== pointerState.pointerId || !crop) {
                    return;
                }

                const scale = getScale();
                if (!scale) {
                    return;
                }

                const dx = (event.clientX - pointerState.startX) / scale;
                const dy = (event.clientY - pointerState.startY) / scale;

                crop = pointerState.mode === "resize"
                    ? resizeCrop(pointerState.handle, pointerState.startCrop, dx, dy)
                    : moveCrop(pointerState.startCrop, dx, dy);
                renderCrop();
            });

            const finishPointer = (event) => {
                if (!pointerState || event.pointerId !== pointerState.pointerId) {
                    return;
                }

                pointerState = null;
                syncMode();
            };

            document.addEventListener("pointerup", finishPointer);
            document.addEventListener("pointercancel", finishPointer);
        }

        if (cropSlider) {
            cropSlider.addEventListener("input", () => {
                if (!crop) {
                    return;
                }

                const ratio = Number(cropSlider.value || 0) / 100;
                const minWidth = getMinCropWidth();
                const maxWidth = getMaxCropWidth();
                const targetWidth = minWidth + ((maxWidth - minWidth) * clamp(ratio, 0, 1));
                const currentCenterX = crop.x + (crop.width / 2);
                const currentCenterY = crop.y + (crop.height / 2);
                crop = normalizeCrop({
                    width: targetWidth,
                    height: targetWidth / ASPECT_RATIO,
                    x: currentCenterX - (targetWidth / 2),
                    y: currentCenterY - ((targetWidth / ASPECT_RATIO) / 2),
                });
                renderCrop();
            });
        }

        if (confirmBtn) {
            confirmBtn.addEventListener("click", async () => {
                if (!pendingFile || !cropInitialized) {
                    return;
                }

                let confirmed = false;
                setConfirmReady(false);
                try {
                    const croppedFile = await cropPendingFile();
                    if (!croppedFile) {
                        setConfirmReady(true);
                        return;
                    }

                    setInputFile(fileInput, croppedFile);
                    if (removeFlag) {
                        removeFlag.value = "0";
                    }
                    const previewUrl = URL.createObjectURL(croppedFile);
                    showPreview(previewUrl, true);
                    confirmed = true;
                    finishCropConfirm();
                } finally {
                    if (!confirmed && pendingFile) {
                        setConfirmReady(true);
                    }
                }
            });
        }

        if (fileInput) {
            fileInput.addEventListener("change", (event) => {
                const target = event.target;
                const file = target && target.files && target.files[0];

                if (!file) {
                    return;
                }

                if (removeFlag) {
                    removeFlag.value = "0";
                }

                if (cropModal) {
                    setPendingFile(file);
                }
                target.value = "";
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener("click", () => {
                if (pendingFile) {
                    discardPendingSelection();
                    return;
                }

                if (fileInput) {
                    fileInput.value = "";
                }

                if (removeFlag) {
                    removeFlag.value = originalPreviewSrc ? "1" : "0";
                }

                clearPreview();
            });
        }

        if (form) {
            form.addEventListener("submit", (event) => {
                if (pendingFile) {
                    event.preventDefault();
                    if (cropModal) {
                        cropModal.show();
                    }
                }
            }, true);
        }

        if (preview) {
            const src = preview.getAttribute("src");
            if (src && src.trim() !== "") {
                hidePlaceholder();
                if (imageFrame) {
                    imageFrame.style.display = "block";
                }
                showControls();
                preview.style.display = "block";
            } else {
                clearPreview();
            }
        }
    });
})();
