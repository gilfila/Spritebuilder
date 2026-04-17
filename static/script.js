document.addEventListener("DOMContentLoaded", function () {
    // If no token, redirect to login
    if (!localStorage.getItem("sprite_token")) {
        window.location.href = "/";
        return;
    }

    var promptInput = document.getElementById("prompt-input");
    var generateBtn = document.getElementById("generate-btn");
    var generateTextBtn = document.getElementById("generate-text-btn");
    var loadingSection = document.getElementById("loading");
    var resultSection = document.getElementById("result");
    var spriteImg = document.getElementById("sprite-img");
    var saveBtn = document.getElementById("save-btn");
    var resetBtn = document.getElementById("reset-btn");
    var errorMsg = document.getElementById("error-msg");
    var carouselSection = document.getElementById("carousel-section");
    var carousel = document.getElementById("carousel");

    var slotRow = document.getElementById("slot-row");
    var slotButtons = slotRow.querySelectorAll(".slot");
    var modal = document.getElementById("slot-modal");
    var modalGrid = document.getElementById("modal-grid");
    var modalTitle = document.getElementById("modal-title");

    var micBtn = document.getElementById("mic-btn");
    var micStatus = document.getElementById("mic-status");

    var loadingMessages = [
        "Creating your sprite...",
        "Drawing tiny pixels...",
        "Adding fun colors...",
        "Almost done..."
    ];

    var loadingInterval = null;

    // Slot state — chosen IDs per slot
    var slotState = { character: null, color: null, style: null, vibe: null };
    // Catalog from server — { slot: [{id, emoji, label}, ...] }
    var slotCatalog = null;
    var requiredSlots = ["character", "color"];

    var spriteHistory = loadHistory();
    renderCarousel();

    // --- Load slot catalog ---
    fetch("/api/slots", {
        headers: { "Authorization": "Bearer " + localStorage.getItem("sprite_token") }
    })
        .then(function (res) {
            if (res.status === 401) {
                localStorage.removeItem("sprite_token");
                window.location.href = "/";
                return null;
            }
            return res.json();
        })
        .then(function (data) {
            if (!data) return;
            slotCatalog = data.slots;
            if (Array.isArray(data.required)) requiredSlots = data.required;
        })
        .catch(function () {
            showError("Could not load sprite choices. Refresh to try again.");
        });

    // --- Slot builder ---

    slotButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            openSlotModal(btn.getAttribute("data-slot"));
        });
    });

    function openSlotModal(slot) {
        if (!slotCatalog || !slotCatalog[slot]) return;
        modalTitle.textContent = "Pick a " + capitalize(slot);
        modalGrid.innerHTML = "";
        slotCatalog[slot].forEach(function (choice) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "choice-btn";
            btn.innerHTML =
                '<span class="choice-emoji">' + escapeHtml(choice.emoji) + '</span>' +
                '<span class="choice-label">' + escapeHtml(choice.label) + '</span>';
            btn.addEventListener("click", function () {
                setSlot(slot, choice);
                closeModal();
            });
            modalGrid.appendChild(btn);
        });
        modal.hidden = false;
        document.addEventListener("keydown", onModalKey);
    }

    function closeModal() {
        modal.hidden = true;
        document.removeEventListener("keydown", onModalKey);
    }

    function onModalKey(e) {
        if (e.key === "Escape") closeModal();
    }

    modal.querySelectorAll("[data-close]").forEach(function (el) {
        el.addEventListener("click", closeModal);
    });

    function setSlot(slot, choice) {
        slotState[slot] = choice.id;
        var btn = slotRow.querySelector('.slot[data-slot="' + slot + '"]');
        var valueEl = btn.querySelector(".slot-value");
        var hintEl = btn.querySelector(".slot-hint");
        var isNone = choice.id === "none";

        valueEl.textContent = isNone ? "\u2014" : choice.emoji;
        valueEl.classList.remove("slot-placeholder");
        hintEl.textContent = isNone ? "(skipped)" : choice.label;
        btn.classList.toggle("filled", !isNone);

        updateGenerateButton();
    }

    function updateGenerateButton() {
        var ready = requiredSlots.every(function (s) {
            return slotState[s] && slotState[s] !== "none";
        });
        generateBtn.disabled = !ready;
    }

    // --- Generate ---

    generateBtn.addEventListener("click", function () {
        hideError();

        var ready = requiredSlots.every(function (s) {
            return slotState[s] && slotState[s] !== "none";
        });
        if (!ready) {
            showError("Pick a character and a color first!");
            return;
        }

        var label = buildLabelFromSlots();
        submitGenerate({ slots: slotState }, label);
    });

    generateTextBtn.addEventListener("click", function () {
        hideError();
        var prompt = promptInput.value.trim();
        if (!prompt) {
            showError("Type something or use the mic!");
            return;
        }
        submitGenerate({ prompt: prompt }, prompt);
    });

    promptInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") generateTextBtn.click();
    });

    function submitGenerate(body, label) {
        setLoading(true);
        fetch("/api/generate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("sprite_token")
            },
            body: JSON.stringify(body)
        })
            .then(function (res) {
                if (res.status === 401) {
                    localStorage.removeItem("sprite_token");
                    window.location.href = "/";
                    return null;
                }
                return res.json().then(function (data) {
                    return { ok: res.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result) return;
                if (!result.ok) {
                    showError(result.data.error || "Something went wrong. Try again!");
                    return;
                }

                var entry = {
                    label: label,
                    idle: result.data.image_idle,
                    flap: result.data.image_flap,
                    id: Date.now()
                };

                spriteHistory.unshift(entry);
                if (spriteHistory.length > 20) spriteHistory.pop();
                saveHistory();
                renderCarousel();

                selectSprite(entry);
                showResult();
            })
            .catch(function () {
                showError("Could not connect to the sprite machine. Try again!");
            })
            .finally(function () {
                setLoading(false);
            });
    }

    function buildLabelFromSlots() {
        if (!slotCatalog) return "my sprite";
        var parts = [];
        ["color", "character", "style", "vibe"].forEach(function (slot) {
            var id = slotState[slot];
            if (!id || id === "none") return;
            var choice = (slotCatalog[slot] || []).find(function (c) { return c.id === id; });
            if (choice) parts.push(choice.label.toLowerCase());
        });
        return parts.join(" ") || "my sprite";
    }

    // --- Voice-to-text ---

    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    var recognition = null;
    var isListening = false;

    if (SpeechRecognition) {
        micBtn.hidden = false;
        recognition = new SpeechRecognition();
        recognition.lang = "en-US";
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onresult = function (event) {
            var transcript = event.results[0][0].transcript;
            promptInput.value = transcript;
            setMicStatus("Got it! \u2728", false);
        };

        recognition.onerror = function (event) {
            if (event.error === "not-allowed" || event.error === "service-not-allowed") {
                setMicStatus("Please allow microphone access.", true);
            } else if (event.error === "no-speech") {
                setMicStatus("I didn't hear anything. Try again!", true);
            } else {
                setMicStatus("Mic trouble — try typing instead.", true);
            }
        };

        recognition.onend = function () {
            isListening = false;
            micBtn.classList.remove("listening");
            micBtn.setAttribute("aria-label", "Speak your idea");
        };

        micBtn.addEventListener("click", function () {
            if (isListening) {
                recognition.stop();
                return;
            }
            try {
                setMicStatus("Listening... say your idea!", false);
                recognition.start();
                isListening = true;
                micBtn.classList.add("listening");
                micBtn.setAttribute("aria-label", "Stop listening");
            } catch (e) {
                setMicStatus("Mic trouble — try typing instead.", true);
            }
        });
    }

    function setMicStatus(msg, isError) {
        micStatus.textContent = msg;
        micStatus.classList.toggle("error", !!isError);
        micStatus.hidden = false;
    }

    // --- Result actions ---

    saveBtn.addEventListener("click", function () {
        var src = spriteImg.src;
        if (!src) return;
        var link = document.createElement("a");
        link.download = "my-sprite.png";
        link.href = src;
        link.click();
    });

    resetBtn.addEventListener("click", function () {
        promptInput.value = "";
        hideError();
    });

    // --- Carousel ---

    function selectSprite(entry) {
        spriteImg.src = entry.idle;
        showResult();

        if (window.setGameSprite) {
            window.setGameSprite(entry.idle, entry.flap);
        }

        var cards = carousel.querySelectorAll(".carousel-card");
        cards.forEach(function (card) {
            card.classList.toggle("selected", card.dataset.id === String(entry.id));
        });
    }

    function renderCarousel() {
        carousel.innerHTML = "";

        if (spriteHistory.length === 0) {
            carouselSection.hidden = true;
            return;
        }

        carouselSection.hidden = false;

        spriteHistory.forEach(function (entry) {
            var card = document.createElement("div");
            card.className = "carousel-card";
            card.dataset.id = String(entry.id);

            var img = document.createElement("img");
            img.src = entry.idle;
            img.alt = entry.label;

            var label = document.createElement("div");
            label.className = "card-label";
            label.textContent = entry.label;
            label.title = entry.label;

            var actions = document.createElement("div");
            actions.className = "card-actions";

            var playBtn = document.createElement("button");
            playBtn.className = "card-btn card-play";
            playBtn.textContent = "\u25B6 Play";
            playBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                selectSprite(entry);
            });

            var dlBtn = document.createElement("button");
            dlBtn.className = "card-btn card-download";
            dlBtn.textContent = "\u2B73 Save";
            dlBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                var link = document.createElement("a");
                link.download = entry.label.replace(/[^a-z0-9]/gi, "-") + ".png";
                link.href = entry.idle;
                link.click();
            });

            actions.appendChild(playBtn);
            actions.appendChild(dlBtn);

            card.appendChild(img);
            card.appendChild(label);
            card.appendChild(actions);

            card.addEventListener("click", function () {
                selectSprite(entry);
            });

            carousel.appendChild(card);
        });
    }

    function saveHistory() {
        try {
            localStorage.setItem("sprite_history", JSON.stringify(spriteHistory));
        } catch (e) {
            while (spriteHistory.length > 5) {
                spriteHistory.pop();
            }
            try {
                localStorage.setItem("sprite_history", JSON.stringify(spriteHistory));
            } catch (e2) {}
        }
    }

    function loadHistory() {
        try {
            var data = localStorage.getItem("sprite_history");
            if (data) return JSON.parse(data);
        } catch (e) {}
        return [];
    }

    // --- UI helpers ---

    function setLoading(on) {
        generateBtn.disabled = on || !requiredSlotsFilled();
        generateTextBtn.disabled = on;
        loadingSection.hidden = !on;
        if (on) {
            var msgIndex = 0;
            var loadingText = loadingSection.querySelector(".loading-text");
            loadingText.textContent = loadingMessages[0];
            loadingInterval = setInterval(function () {
                msgIndex = (msgIndex + 1) % loadingMessages.length;
                loadingText.textContent = loadingMessages[msgIndex];
            }, 2500);
        } else if (loadingInterval) {
            clearInterval(loadingInterval);
            loadingInterval = null;
        }
    }

    function requiredSlotsFilled() {
        return requiredSlots.every(function (s) {
            return slotState[s] && slotState[s] !== "none";
        });
    }

    function showError(msg) {
        errorMsg.textContent = msg;
        errorMsg.hidden = false;
    }

    function hideError() {
        errorMsg.hidden = true;
    }

    function showResult() {
        resultSection.hidden = false;
    }

    function capitalize(s) {
        return s.charAt(0).toUpperCase() + s.slice(1);
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }
});
