# Spritebuilder

## Project Overview
A web app that lets Tiger Scouts generate fun pixel art sprites using AI, teaching them the basics of working with LLMs in a playful, hands-on way.

## Sprite Generation CLI
This project uses **Replicate CLI with Retro Diffusion** for sprite generation.
- Install: `pip install replicate`
- Retro Diffusion models: `rd-plus` (quality), `rd-fast` (speed), `rd-animation` (animated)
- Produces authentic grid-aligned pixel art at native sprite resolutions (e.g. 32x32, 64x64)
- Requires `REPLICATE_API_TOKEN` environment variable

## Tech Stack
- **Frontend**: HTML/CSS/JavaScript (simple, kid-friendly UI)
- **Backend**: Python (Flask or FastAPI) to proxy Replicate API calls
- **Sprite Generation**: Replicate CLI / Python SDK with Retro Diffusion models
- **No heavy frameworks** — keep it simple and accessible

## Project Structure
```
Spritebuilder/
  CLAUDE.md          # This file
  app/               # Backend (Python)
  static/            # Frontend assets (HTML, CSS, JS)
  requirements.txt   # Python dependencies
```

## Development Guidelines
- Keep the UI simple, colorful, and kid-friendly (Tiger Scouts ages 6-7)
- All API keys must be server-side only; never expose tokens to the frontend
- Use environment variables for secrets (REPLICATE_API_TOKEN)
- Sprites should be small pixel art (32x32 or 64x64) for fast generation
- Include prompt guardrails to keep generated content age-appropriate

## Commands
- `pip install -r requirements.txt` — install dependencies
- `python app/main.py` — run the dev server
- API keys go in `.env` (never committed)

## Key Constraints
- No Cursor CLI — use Replicate CLI / SDK instead
- Target audience is young children; content must be safe and fun
- Minimize latency; prefer `rd-fast` model for interactive use
