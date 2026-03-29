import base64
import os
import re
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent / "static"), static_url_path="")

gemini_client = genai.Client(api_key=os.environ.get("GEMINI_KEY"))

# --- Content Safety ---

BLOCKED_TERMS = frozenset([
    "kill", "murder", "blood", "gun", "weapon", "sword", "fight", "dead",
    "death", "war", "attack", "stab", "shoot", "bomb", "explode", "knife",
    "scary", "horror", "zombie", "skeleton", "ghost", "monster", "demon",
    "devil", "evil", "creepy", "nightmare", "haunted",
    "sexy", "naked", "nude", "drugs", "alcohol", "beer", "wine", "cigarette",
    "smoke", "hate", "stupid",
])

BLOCKED_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in BLOCKED_TERMS) + r")\b",
    re.IGNORECASE,
)

MAX_PROMPT_LENGTH = 200


def check_prompt_safety(prompt: str) -> str | None:
    if not prompt or not prompt.strip():
        return "Please type something or pick an idea above!"
    if len(prompt) > MAX_PROMPT_LENGTH:
        return "That's a bit too long! Try a shorter description."
    if BLOCKED_PATTERN.search(prompt):
        return "Hmm, let's try something different! How about a friendly animal or a cool vehicle?"
    return None


def wrap_prompt(user_prompt: str) -> str:
    return (
        f"A cute, friendly 32x32 pixel art sprite of {user_prompt.strip()}. "
        "Retro game style, colorful, kid-friendly, transparent background, "
        "centered, clean pixel edges, limited color palette."
    )


# --- Rate Limiting ---

rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 5
RATE_WINDOW = 60


def is_rate_limited(ip: str) -> bool:
    now = time.time()
    rate_limit_store[ip] = [t for t in rate_limit_store[ip] if now - t < RATE_WINDOW]
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
    if is_rate_limited(request.remote_addr):
        return jsonify({"error": "Slow down! Wait a moment before making another sprite."}), 429

    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")

    error = check_prompt_safety(prompt)
    if error:
        return jsonify({"error": error}), 400

    safe_prompt = wrap_prompt(prompt)

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=safe_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1",
                ),
            ),
        )

        # Extract image data from response
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                mime_type = part.inline_data.mime_type or "image/png"
                return jsonify({
                    "image_data": f"data:{mime_type};base64,{image_b64}",
                })

        return jsonify({"error": "The sprite came out funny! Try again."}), 500

    except Exception:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Our sprite machine is taking a nap! Try again in a moment."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
