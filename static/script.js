document.addEventListener("DOMContentLoaded", function () {
    // If no token, redirect to login
    if (!localStorage.getItem("sprite_token")) {
        window.location.href = "/";
        return;
    }

    var promptInput = document.getElementById("prompt-input");
    var generateBtn = document.getElementById("generate-btn");
    var loadingSection = document.getElementById("loading");
    var resultSection = document.getElementById("result");
    var spriteImg = document.getElementById("sprite-img");
    var saveBtn = document.getElementById("save-btn");
    var resetBtn = document.getElementById("reset-btn");
    var errorMsg = document.getElementById("error-msg");
    var ideaButtons = document.querySelectorAll(".idea-btn");
    var carouselSection = document.getElementById("carousel-section");
    var carousel = document.getElementById("carousel");

    var loadingMessages = [
        "Creating your sprite...",
        "Drawing tiny pixels...",
        "Adding fun colors...",
        "Almost done..."
    ];

    var loadingInterval = null;

    var prevBtn = document.getElementById("carousel-prev");
    var nextBtn = document.getElementById("carousel-next");
    var dotsContainer = document.getElementById("carousel-dots");
    var PAGE_SIZE = 2;
    var carouselPage = 0;

    // Sprite history stored in memory (and localStorage for persistence)
    var spriteHistory = loadHistory();
    renderCarousel();

    ideaButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            promptInput.value = btn.getAttribute("data-prompt");
            promptInput.focus();
        });
    });

    generateBtn.addEventListener("click", function () {
        var prompt = promptInput.value.trim();

        hideError();

        if (!prompt) {
            showError("Type something or pick an idea above!");
            return;
        }

        setLoading(true);

        fetch("/api/generate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("sprite_token")
            },
            body: JSON.stringify({ prompt: prompt })
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
                    label: prompt,
                    idle: result.data.image_idle,
                    flap: result.data.image_flap,
                    id: Date.now()
                };

                // Add to history
                spriteHistory.unshift(entry);
                if (spriteHistory.length > 20) spriteHistory.pop();
                carouselPage = 0;
                saveHistory();
                renderCarousel();

                // Show and select this sprite
                selectSprite(entry);
                showResult();
            })
            .catch(function () {
                showError("Could not connect to the sprite machine. Try again!");
            })
            .finally(function () {
                setLoading(false);
            });
    });

    promptInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
            generateBtn.click();
        }
    });

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
        promptInput.focus();
    });

    // --- Carousel ---

    prevBtn.addEventListener("click", function () {
        if (carouselPage > 0) {
            carouselPage--;
            renderCarousel();
        }
    });

    nextBtn.addEventListener("click", function () {
        var totalPages = Math.ceil(spriteHistory.length / PAGE_SIZE);
        if (carouselPage < totalPages - 1) {
            carouselPage++;
            renderCarousel();
        }
    });

    function selectSprite(entry) {
        spriteImg.src = entry.idle;
        showResult();

        if (window.setGameSprite) {
            window.setGameSprite(entry.idle, entry.flap);
        }

        // Highlight selected card
        var cards = carousel.querySelectorAll(".carousel-card");
        cards.forEach(function (card) {
            card.classList.toggle("selected", card.dataset.id === String(entry.id));
        });
    }

    function renderCarousel() {
        carousel.innerHTML = "";
        dotsContainer.innerHTML = "";

        if (spriteHistory.length === 0) {
            carouselSection.hidden = true;
            return;
        }

        carouselSection.hidden = false;

        var totalPages = Math.ceil(spriteHistory.length / PAGE_SIZE);

        // Clamp page
        if (carouselPage >= totalPages) carouselPage = totalPages - 1;
        if (carouselPage < 0) carouselPage = 0;

        // Update arrow states
        prevBtn.disabled = carouselPage === 0;
        nextBtn.disabled = carouselPage >= totalPages - 1;

        // Show only the current page of sprites
        var start = carouselPage * PAGE_SIZE;
        var pageItems = spriteHistory.slice(start, start + PAGE_SIZE);

        pageItems.forEach(function (entry) {
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

        // Render page dots (only if more than 1 page)
        if (totalPages > 1) {
            for (var i = 0; i < totalPages; i++) {
                var dot = document.createElement("button");
                dot.className = "carousel-dot" + (i === carouselPage ? " active" : "");
                dot.setAttribute("aria-label", "Page " + (i + 1));
                dot.dataset.page = String(i);
                dot.addEventListener("click", function () {
                    carouselPage = parseInt(this.dataset.page, 10);
                    renderCarousel();
                });
                dotsContainer.appendChild(dot);
            }
        }
    }

    function saveHistory() {
        try {
            localStorage.setItem("sprite_history", JSON.stringify(spriteHistory));
        } catch (e) {
            // localStorage full — drop oldest entries
            while (spriteHistory.length > 5) {
                spriteHistory.pop();
            }
            try {
                localStorage.setItem("sprite_history", JSON.stringify(spriteHistory));
            } catch (e2) {
                // give up on persistence
            }
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
        generateBtn.disabled = on;
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
});
