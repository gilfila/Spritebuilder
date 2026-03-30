import base64
import hashlib
import io
import os
import re
import time
from collections import defaultdict
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent / "static"), static_url_path="")

AUTH_USER = "admin"
AUTH_PASS = "cheese"
# Token is a hash of the credentials — deterministic so it works across serverless invocations
AUTH_TOKEN = hashlib.sha256(f"{AUTH_USER}:{AUTH_PASS}".encode()).hexdigest()

gemini_client = genai.Client(api_key=os.environ.get("GEMINI_KEY"))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token != AUTH_TOKEN:
            return jsonify({"error": "Not authorized"}), 401
        return f(*args, **kwargs)
    return decorated


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


def make_idle_prompt(user_prompt: str) -> str:
    return (
        f"A cute, friendly 32x32 pixel art character sprite of {user_prompt.strip()}, "
        "standing idle pose, facing right, arms at sides. "
        "Retro game style, colorful, kid-friendly, transparent PNG background, "
        "centered on transparent checkerboard, clean pixel edges, limited color palette. "
        "NO background, NO ground, NO shadow — only the character on transparency."
    )


def make_flap_prompt(user_prompt: str) -> str:
    return (
        f"A cute, friendly 32x32 pixel art character sprite of {user_prompt.strip()}, "
        "flying pose with arms raised up high above its head, facing right. "
        "Retro game style, colorful, kid-friendly, transparent PNG background, "
        "centered on transparent checkerboard, clean pixel edges, limited color palette. "
        "Same character style. "
        "NO background, NO ground, NO shadow — only the character on transparency."
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
def login_page():
    return send_from_directory(app.static_folder, "login.html")


@app.route("/favicon.ico")
@app.route("/favicon.png")
def favicon():
    return "", 204


@app.route("/app")
def app_page():
    return send_from_directory(app.static_folder, "app.html")


@app.route("/style.css")
def serve_css():
    return send_from_directory(app.static_folder, "style.css")


@app.route("/script.js")
def serve_js():
    return send_from_directory(app.static_folder, "script.js")


@app.route("/game.js")
def serve_game_js():
    return send_from_directory(app.static_folder, "game.js")


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")

    if username == AUTH_USER and password == AUTH_PASS:
        return jsonify({"token": AUTH_TOKEN})

    return jsonify({"error": "Wrong username or password!"}), 401


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/generate", methods=["POST"])
@login_required
def generate():
    if is_rate_limited(request.remote_addr):
        return jsonify({"error": "Slow down! Wait a moment before making another sprite."}), 429

    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")

    error = check_prompt_safety(prompt)
    if error:
        return jsonify({"error": error}), 400

    idle_prompt = make_idle_prompt(prompt)
    flap_prompt = make_flap_prompt(prompt)

    try:
        image_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="1:1",
            ),
        )

        # Generate idle frame
        idle_response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=idle_prompt,
            config=image_config,
        )

        idle_data = _extract_image(idle_response)
        if not idle_data:
            return jsonify({"error": "The sprite came out funny! Try again."}), 500

        # Generate flap frame
        flap_response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=flap_prompt,
            config=image_config,
        )

        flap_data = _extract_image(flap_response)
        if not flap_data:
            # Fall back to idle for both if flap fails
            flap_data = idle_data

        return jsonify({
            "image_idle": idle_data,
            "image_flap": flap_data,
        })

    except Exception:
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Our sprite machine is taking a nap! Try again in a moment."
        }), 500


def _extract_image(response) -> str | None:
    for part in response.candidates[0].content.parts:
        if part.inline_data:
            raw_bytes = part.inline_data.data
            img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

            # Remove background: make the corner color transparent
            # Sample corners to find the dominant background color
            pixels = img.load()
            w, h = img.size
            corners = [pixels[0, 0], pixels[w - 1, 0], pixels[0, h - 1], pixels[w - 1, h - 1]]
            bg_color = max(set(corners), key=corners.count)

            # Make all pixels close to the background color transparent
            tolerance = 30
            for y in range(h):
                for x in range(w):
                    r, g, b, a = pixels[x, y]
                    br, bg, bb = bg_color[0], bg_color[1], bg_color[2]
                    if abs(r - br) < tolerance and abs(g - bg) < tolerance and abs(b - bb) < tolerance:
                        pixels[x, y] = (0, 0, 0, 0)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{image_b64}"
    return None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
