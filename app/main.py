import base64
import hashlib
import hmac
import io
import json
import os
import re
import sys
import time
from collections import defaultdict
from functools import wraps
from pathlib import Path

import pyotp
import segno
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__, static_folder=str(PROJECT_ROOT / "static"), static_url_path="")

AUTH_USER = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASS = os.environ.get("AUTH_PASSWORD", "cheese")
# Token is a hash of the credentials — deterministic so it works across serverless invocations
AUTH_TOKEN = hashlib.sha256(f"{AUTH_USER}:{AUTH_PASS}".encode()).hexdigest()

# --- TOTP state ---
# Resolution order for the TOTP secret:
#   1. AUTH_TOTP_SECRET env var (read-only; overrides everything)
#   2. AUTH_STATE_PATH file contents (defaults to <project>/.auth_state.json;
#      override on serverless hosts where the repo dir is read-only)
# Enrollment via the web UI writes to the file. Serverless deployments can
# promote the file-stored secret to an env var to survive cold starts.
AUTH_STATE_PATH = Path(os.environ.get("AUTH_STATE_PATH") or (PROJECT_ROOT / ".auth_state.json"))
_ENV_TOTP_SECRET = (os.environ.get("AUTH_TOTP_SECRET") or "").strip() or None


def _load_stored_secret() -> str | None:
    if _ENV_TOTP_SECRET:
        return _ENV_TOTP_SECRET
    try:
        data = json.loads(AUTH_STATE_PATH.read_text())
        secret = (data.get("totp_secret") or "").strip()
        return secret or None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _save_stored_secret(secret: str) -> None:
    if _ENV_TOTP_SECRET:
        # Env var wins; file would be ignored. Refuse so the UI can surface it.
        raise RuntimeError("AUTH_TOTP_SECRET is set via env var; unset it to enroll via the app.")
    try:
        AUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUTH_STATE_PATH.write_text(json.dumps({"totp_secret": secret}))
        try:
            os.chmod(AUTH_STATE_PATH, 0o600)
        except OSError:
            pass
    except OSError as exc:
        raise RuntimeError(
            f"Could not persist MFA secret to {AUTH_STATE_PATH}. "
            "On Vercel/serverless, set AUTH_TOTP_SECRET as an env var instead."
        ) from exc


def _current_totp() -> pyotp.TOTP | None:
    secret = _load_stored_secret()
    return pyotp.TOTP(secret) if secret else None


if AUTH_USER == "admin" and AUTH_PASS == "cheese":
    print(
        "WARNING: using default credentials. Set AUTH_USERNAME and AUTH_PASSWORD in .env.",
        file=sys.stderr,
    )
if _current_totp() is None:
    print(
        "INFO: MFA not configured yet. Log in once, then follow the in-app setup prompt.",
        file=sys.stderr,
    )

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


# --- Slot Builder ---
# Allowlisted picture-grid choices. Each value is (emoji, display label, prompt phrase).
# Keeping everything server-side means the client only sends slot IDs, so no free
# text from the kid ever hits the model.

SLOT_CHOICES: dict[str, dict[str, tuple[str, str, str]]] = {
    "character": {
        "cat":      ("\U0001F431", "Cat",      "cat"),
        "dog":      ("\U0001F436", "Puppy",    "puppy dog"),
        "fox":      ("\U0001F98A", "Fox",      "fox"),
        "bunny":    ("\U0001F430", "Bunny",    "bunny rabbit"),
        "bear":     ("\U0001F43B", "Bear",     "bear cub"),
        "lion":     ("\U0001F981", "Lion",     "lion cub"),
        "tiger":    ("\U0001F42F", "Tiger",    "tiger cub"),
        "frog":     ("\U0001F438", "Frog",     "frog"),
        "owl":      ("\U0001F989", "Owl",      "owl"),
        "dragon":   ("\U0001F409", "Dragon",   "friendly baby dragon"),
        "unicorn":  ("\U0001F984", "Unicorn",  "unicorn"),
        "dino":     ("\U0001F996", "Dino",     "little dinosaur"),
        "robot":    ("\U0001F916", "Robot",    "round friendly robot"),
        "alien":    ("\U0001F47D", "Alien",    "cute alien"),
        "astronaut":("\U0001F9D1\u200D\U0001F680", "Astronaut", "kid astronaut"),
        "wizard":   ("\U0001F9D9", "Wizard",   "young wizard"),
    },
    "color": {
        "red":     ("\U0001F534", "Red",     "bright red"),
        "orange":  ("\U0001F7E0", "Orange",  "orange"),
        "yellow":  ("\U0001F7E1", "Yellow",  "sunny yellow"),
        "green":   ("\U0001F7E2", "Green",   "grass green"),
        "blue":    ("\U0001F535", "Blue",    "sky blue"),
        "purple":  ("\U0001F7E3", "Purple",  "purple"),
        "pink":    ("\U0001F338", "Pink",    "bubblegum pink"),
        "white":   ("\u2B1C",     "White",   "snowy white"),
        "brown":   ("\U0001F7E4", "Brown",   "warm brown"),
        "black":   ("\u2B1B",     "Black",   "inky black"),
        "rainbow": ("\U0001F308", "Rainbow", "rainbow colored"),
        "gold":    ("\u2B50",     "Gold",    "shiny gold"),
    },
    "style": {
        "none":     ("\u274C",     "None",      ""),
        "hat":      ("\U0001F3A9", "Top Hat",   "wearing a tiny top hat"),
        "wizard":   ("\U0001F9D9", "Wiz Hat",   "wearing a pointy wizard hat with stars"),
        "crown":    ("\U0001F451", "Crown",     "wearing a golden crown"),
        "cape":     ("\U0001F9E5", "Cape",      "wearing a flowing cape"),
        "scarf":    ("\U0001F9E3", "Scarf",     "wearing a cozy scarf"),
        "glasses":  ("\U0001F576", "Shades",    "wearing cool sunglasses"),
        "bowtie":   ("\U0001F380", "Bow Tie",   "wearing a fancy bow tie"),
        "backpack": ("\U0001F392", "Backpack",  "wearing a little backpack"),
        "headband": ("\U0001F9E2", "Headband",  "wearing a sporty headband"),
        "wings":    ("\U0001FAB6", "Wings",     "with tiny feathery wings"),
        "bandana":  ("\U0001F3F4", "Bandana",   "wearing a polka-dot bandana"),
    },
    "vibe": {
        "none":     ("\u274C",     "None",     ""),
        "happy":    ("\U0001F600", "Happy",    "with a big happy smile"),
        "excited":  ("\U0001F929", "Excited",  "looking super excited and starry-eyed"),
        "silly":    ("\U0001F61D", "Silly",    "making a silly face with tongue out"),
        "cool":     ("\U0001F60E", "Cool",     "looking relaxed and cool"),
        "brave":    ("\U0001F642", "Brave",    "standing tall and brave"),
        "sleepy":   ("\U0001F634", "Sleepy",   "looking sleepy and yawning"),
        "curious":  ("\U0001F914", "Curious",  "looking curious"),
        "love":     ("\U0001F60D", "Love",     "with heart eyes"),
        "dance":    ("\U0001F483", "Dancy",    "striking a dance pose"),
        "surprised":("\U0001F62E", "Wow",      "looking surprised"),
        "proud":    ("\U0001F60A", "Proud",    "looking proud and cheerful"),
    },
}

REQUIRED_SLOTS = ("character", "color")


def get_slot_catalog() -> dict:
    return {
        slot: [
            {"id": choice_id, "emoji": emoji, "label": label}
            for choice_id, (emoji, label, _phrase) in choices.items()
        ]
        for slot, choices in SLOT_CHOICES.items()
    }


def compose_prompt_from_slots(slots: dict) -> tuple[str | None, str | None]:
    """Returns (prompt, error). Prompt is None when validation fails."""
    if not isinstance(slots, dict):
        return None, "Pick a character and a color to get started!"

    resolved: dict[str, str] = {}
    for slot, choices in SLOT_CHOICES.items():
        value = slots.get(slot)
        if value is None or value == "":
            if slot in REQUIRED_SLOTS:
                return None, "Pick a character and a color to get started!"
            continue
        if not isinstance(value, str) or value not in choices:
            return None, "That's not a choice I know. Tap a picture to pick one!"
        resolved[slot] = choices[value][2]

    if "character" not in resolved or "color" not in resolved:
        return None, "Pick a character and a color to get started!"

    parts = [f"a {resolved['color']} {resolved['character']}"]
    if resolved.get("style"):
        parts.append(resolved["style"])
    if resolved.get("vibe"):
        parts.append(resolved["vibe"])
    return ", ".join(parts), None


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
    # Per-IP rate limit on login to blunt credential stuffing.
    login_key = f"login:{request.remote_addr}"
    if is_rate_limited(login_key):
        return jsonify({"error": "Too many tries. Wait a moment and try again."}), 429

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", ""))
    password = str(data.get("password", ""))
    code = str(data.get("code", "")).strip()

    user_ok = hmac.compare_digest(username, AUTH_USER)
    pass_ok = hmac.compare_digest(password, AUTH_PASS)
    if not (user_ok and pass_ok):
        return jsonify({"error": "Wrong username or password!"}), 401

    totp = _current_totp()
    if totp is None:
        # First login — direct the browser to the in-app enrollment flow.
        # The session token is still returned so the setup endpoints can authenticate.
        return jsonify({"token": AUTH_TOKEN, "mfa_setup_required": True})

    if not code:
        return jsonify({"error": "Enter your 6-digit code.", "mfa_required": True}), 401
    # valid_window=1 tolerates one 30-second step of clock drift
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "That code didn't match. Try the current one.", "mfa_required": True}), 401

    return jsonify({"token": AUTH_TOKEN})


@app.route("/api/auth/config")
def auth_config():
    return jsonify({"mfa_required": _current_totp() is not None})


# --- In-app MFA enrollment ---

@app.route("/api/mfa/status")
@login_required
def mfa_status():
    return jsonify({
        "configured": _current_totp() is not None,
        "env_locked": _ENV_TOTP_SECRET is not None,
    })


@app.route("/api/mfa/setup/begin", methods=["POST"])
@login_required
def mfa_setup_begin():
    if _current_totp() is not None:
        return jsonify({"error": "MFA is already set up."}), 400
    if _ENV_TOTP_SECRET is not None:
        return jsonify({"error": "MFA secret is controlled by the AUTH_TOTP_SECRET env var."}), 400

    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=AUTH_USER, issuer_name="Sprite Builder")
    qr_svg = segno.make(uri, error="m").svg_inline(scale=6, border=2, dark="#222", light="#fff")
    return jsonify({"secret": secret, "uri": uri, "qr_svg": qr_svg})


@app.route("/api/mfa/setup/verify", methods=["POST"])
@login_required
def mfa_setup_verify():
    if _current_totp() is not None:
        return jsonify({"error": "MFA is already set up."}), 400

    data = request.get_json(silent=True) or {}
    secret = str(data.get("secret", "")).strip().upper()
    code = str(data.get("code", "")).strip()

    if not secret or not re.fullmatch(r"[A-Z2-7]+=*", secret):
        return jsonify({"error": "Setup got out of sync. Start over."}), 400
    if not code.isdigit() or len(code) != 6:
        return jsonify({"error": "Enter the 6-digit code from your app."}), 400

    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return jsonify({"error": "That code didn't match. Try the current one."}), 400

    try:
        _save_stored_secret(secret)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"ok": True})


@app.route("/setup-mfa")
def setup_mfa_page():
    return send_from_directory(app.static_folder, "setup.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/slots")
@login_required
def slots_catalog():
    return jsonify({"slots": get_slot_catalog(), "required": list(REQUIRED_SLOTS)})


@app.route("/api/generate", methods=["POST"])
@login_required
def generate():
    if is_rate_limited(request.remote_addr):
        return jsonify({"error": "Slow down! Wait a moment before making another sprite."}), 429

    data = request.get_json(silent=True) or {}
    slots = data.get("slots")
    prompt = data.get("prompt", "")

    if slots:
        composed, slot_error = compose_prompt_from_slots(slots)
        if slot_error:
            return jsonify({"error": slot_error}), 400
        prompt = composed

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
