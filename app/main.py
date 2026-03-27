import os
import re
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent / "static"), static_url_path="")

# Retro Diffusion model identifiers on Replicate
# Update these if model versions change: https://replicate.com/collections/pixel-art
MODELS = {
    "fast": "retro-diffusion/rd-fast",
    "plus": "retro-diffusion/rd-plus",
}

# --- Content Safety ---

BLOCKED_TERMS = frozenset([
    # Violence
    "kill", "murder", "blood", "gun", "weapon", "sword", "fight", "dead",
    "death", "war", "attack", "stab", "shoot", "bomb", "explode", "knife",
    # Horror
    "scary", "horror", "zombie", "skeleton", "ghost", "monster", "demon",
    "devil", "evil", "creepy", "nightmare", "haunted",
    # Inappropriate
    "sexy", "naked", "nude", "drugs", "alcohol", "beer", "wine", "cigarette",
    "smoke", "hate", "stupid",
])

BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in BLOCKED_TERMS) + r")\b",
    re.IGNORECASE,
)

MAX_PROMPT_LENGTH = 200


def check_prompt_safety(prompt):
    """Return an error message if the prompt is unsafe, or None if it's OK."""
    if not prompt or not prompt.strip():
        return "Please type something or pick an idea above!"
    if len(prompt) > MAX_PROMPT_LENGTH:
        return "That's a bit too long! Try a shorter description."
    if BLOCKED_PATTERN.search(prompt):
        return "Hmm, let's try something different! How about a friendly animal or a cool vehicle?"
    return None


def wrap_prompt(user_prompt):
    """Wrap the user's prompt with safe framing for the model."""
    return (
        f"a cute, friendly pixel art sprite of {user_prompt.strip()}, "
        "white background, no text, kid-friendly, cheerful, colorful, 64x64 pixels"
    )


# --- Rate Limiting ---

rate_limit_store = defaultdict(list)
RATE_LIMIT = 5  # requests per window
RATE_WINDOW = 60  # seconds


def is_rate_limited(ip):
    now = time.time()
    timestamps = rate_limit_store[ip]
    # Prune old entries
    rate_limit_store[ip] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(rate_limit_store[ip]) >= RATE_LIMIT:
        return True
    rate_limit_store[ip].append(now)
    return False


# --- Routes ---

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/generate", methods=["POST"])
def generate():
    # Rate limit check
    if is_rate_limited(request.remote_addr):
        return jsonify({"error": "Slow down! Wait a moment before making another sprite."}), 429

    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")
    model_choice = data.get("model", "fast")

    if model_choice not in MODELS:
        model_choice = "fast"

    # Content safety check
    error = check_prompt_safety(prompt)
    if error:
        return jsonify({"error": error}), 400

    safe_prompt = wrap_prompt(prompt)

    try:
        import replicate

        output = replicate.run(
            MODELS[model_choice],
            input={
                "prompt": safe_prompt,
                "width": 64,
                "height": 64,
            },
        )

        # Output may be a URL string, a FileOutput, or a list
        if isinstance(output, list):
            image_url = str(output[0])
        else:
            image_url = str(output)

        return jsonify({
            "image_url": image_url,
            "prompt_used": safe_prompt,
        })

    except Exception as e:
        print(f"Replicate error: {e}")
        return jsonify({
            "error": "Our sprite machine is taking a nap! Try again in a moment."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
