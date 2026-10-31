# autodm — project instructions

Self-hosted Instagram comment-to-DM bot (ManyChat alternative). Goal: grow the owner's followers cheaply; keep it simple, minimal UI, ManyChat's basic features added step by step.

## Layout
- `app.py` — whole service (FastAPI): webhook verify + signature check, comment → rule match → DM, follow-gate flow (`on_comment`, `on_message`).
- `rules.json` — keywords/replies; read on every webhook, no restart needed.
- `tests/test_app.py` — pytest; Instagram API calls are faked via `graph_post` / `graph_get`.
- `Dockerfile`, `docker-compose.yml`, `Caddyfile` — deploy (Caddy only under `--profile https`, sandboxed cloudflared quick tunnel under `--profile tunnel`).

## Commands
- Test: `pip install -r requirements-dev.txt && pytest -q`
- Run: `docker compose up -d` (needs `.env` from `.env.example`)

## Rules for changes
- Keep the README quick-start short; push detail into `<details>` blocks.
- Every new behaviour needs a test. Never commit `.env`, tokens or `*.db`.
- Always verify `X-Hub-Signature-256`; never log tokens.
- Meta constraints: one private reply per comment (within 7 days); 24h messaging window; tokens expire ~60 days.
- Unverified against live Instagram: quick-reply buttons on private replies. Fallback is "any message triggers the follow check".

## Roadmap (do in order)
1. Live test with real Meta app 2. Comment auto-reply 3. Token auto-refresh 4. Multi-message/buttons/email capture 5. Simple stats page
