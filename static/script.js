document.addEventListener("DOMContentLoaded", function () {
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

    // Idea buttons fill the input
    ideaButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            promptInput.value = btn.getAttribute("data-prompt");
            promptInput.focus();
        });
    });

    // Generate sprite
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
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: prompt })
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    showError(result.data.error || "Something went wrong. Try again!");
                    return;
                }
                spriteImg.src = result.data.image_url;
                showResult();
            })
            .catch(function () {
                showError("Could not connect to the sprite machine. Try again!");
            })
            .finally(function () {
                setLoading(false);
            });
    });

    // Allow Enter key to trigger generation
    promptInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
            generateBtn.click();
        }
    });

    // Save sprite
    saveBtn.addEventListener("click", function () {
        var url = spriteImg.src;
        if (!url) return;

        var a = document.createElement("a");
        a.href = url;
        a.download = "my-sprite.png";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });

    // Make another
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
