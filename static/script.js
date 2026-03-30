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

    var loadingMessages = [
        "Creating your sprite...",
        "Drawing tiny pixels...",
        "Adding fun colors...",
        "Almost done..."
    ];

    var loadingInterval = null;

    ideaButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            promptInput.value = btn.getAttribute("data-prompt");
            promptInput.focus();
        });
    });

    generateBtn.addEventListener("click", function () {
        var prompt = promptInput.value.trim();

        hideError();
        hideResult();

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
                spriteImg.src = result.data.image_idle;
                showResult();
                // Pass both sprite frames to the game
                if (window.setGameSprite) {
                    window.setGameSprite(result.data.image_idle, result.data.image_flap);
                }
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
        hideResult();
        hideError();
        promptInput.focus();
    });

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

    function hideResult() {
        resultSection.hidden = true;
        spriteImg.src = "";
    }
});
