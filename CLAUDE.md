# Spritebuilder

## Project Overview
A web app that lets Tiger Scouts (ages 6–7) generate fun pixel art sprites using AI, teaching them the basics of working with LLMs in a playful, hands-on way.

## Current State
This project is in its initial setup phase. The repository currently contains only this `CLAUDE.md` file. The application code (backend, frontend, dependencies) has not yet been implemented.

## Sprite Generation
This project uses **Replicate with Retro Diffusion** for sprite generation.
- Python SDK: `pip install replicate`
- Retro Diffusion models:
  - `rd-plus` — higher quality, slower
  - `rd-fast` — lower latency, preferred for interactive use
  - `rd-animation` — animated sprite sheets
- Produces grid-aligned pixel art at native sprite resolutions (32×32 or 64×64)
- Requires `REPLICATE_API_TOKEN` environment variable

## Tech Stack
- **Frontend**: HTML / CSS / JavaScript — simple, no build step
- **Backend**: Python (Flask or FastAPI) — proxies Replicate API calls
- **Sprite Generation**: Replicate Python SDK with Retro Diffusion models
- **No heavy frameworks** — keep it simple and accessible for contributors of all levels

## Project Structure
```
Spritebuilder/
├── CLAUDE.md            # AI assistant instructions (this file)
├── .env                 # Environment variables (never committed)
├── requirements.txt     # Python dependencies
├── app/                 # Backend
│   └── main.py          # Entry point — Flask/FastAPI server
└── static/              # Frontend assets
    ├── index.html        # Main page
    ├── style.css         # Styles
    └── script.js         # Client-side logic
```

## Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run the dev server
python app/main.py

# Environment setup — create .env with:
# REPLICATE_API_TOKEN=<your-token>
```

## Development Guidelines

### Target Audience
- Tiger Scouts, ages 6–7
- UI must be simple, colorful, and kid-friendly
- All generated content must be age-appropriate

### Security
- **Never expose API tokens to the frontend** — all Replicate calls go through the backend
- Store secrets in `.env` (listed in `.gitignore`, never committed)
- Validate and sanitize user input on the server before forwarding to Replicate

### Content Safety
- Implement server-side prompt guardrails to block inappropriate content
- Prepend or wrap user prompts with safe framing (e.g., "a cute, friendly pixel art sprite of…")
- Reject prompts containing violent, scary, or otherwise unsuitable terms

### Performance
- Prefer `rd-fast` model for interactive / real-time generation
- Use `rd-plus` only when higher quality is explicitly needed
- Target 32×32 sprites by default to minimize generation time

### Code Style
- Python: follow PEP 8; use type hints where practical
- JavaScript: vanilla ES6+, no transpilation needed
- HTML/CSS: semantic markup, accessible, large touch targets for young users
- Keep files small and focused — avoid monolithic modules

### Testing
- No test framework is set up yet; when adding tests, prefer `pytest` for Python
- Frontend tests can use simple manual QA given the audience and scope

## Key Constraints
- Do **not** use Cursor CLI — use Replicate CLI / Python SDK instead
- Minimize external dependencies; every added package should have clear justification
- Prioritize fast iteration and simplicity over architectural perfection
