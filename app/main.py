import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

load_dotenv()

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent / "static"), static_url_path="")

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_KEY"))

GRID_SIZE = 16
SPRITE_PROMPT = """\
You are a pixel art sprite generator. Given a description, produce a {size}x{size} pixel art sprite \
as a JSON array of arrays. Each cell is a hex color string like "#FF0000". \
Use transparent pixels as "#00000000" for the background around the sprite.

Rules:
- Output ONLY the JSON array, no markdown, no explanation, no code fences.
- The sprite must be cute, friendly, colorful, and kid-appropriate.
- Use a limited palette (8-12 colors max) for an authentic pixel art look.
- Make the sprite recognizable and charming at {size}x{size}.
- Center the sprite in the grid.
"""

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

    safe_description = f"a cute, friendly pixel art sprite of {prompt.strip()}"

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=SPRITE_PROMPT.format(size=GRID_SIZE),
            messages=[{"role": "user", "content": safe_description}],
        )

        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        grid = json.loads(raw)

        # Validate grid structure
        if (
            not isinstance(grid, list)
            or len(grid) != GRID_SIZE
            or not all(isinstance(row, list) and len(row) == GRID_SIZE for row in grid)
        ):
            return jsonify({"error": "The sprite came out funny! Try again."}), 500

        return jsonify({"grid": grid, "size": GRID_SIZE})

    except json.JSONDecodeError:
        import traceback
        traceback.print_exc()
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
