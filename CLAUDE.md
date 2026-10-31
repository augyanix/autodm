# autodm — project instructions

Self-hosted Instagram comment-to-DM bot (ManyChat alternative). Goal: grow the owner's followers cheaply; keep it simple, minimal UI, ManyChat's basic features added step by step.

## Layout
- `app.py` — whole service (FastAPI): webhook verify + signature check, comment → rule match → DM, follow-gate flow (`on_comment`, `on_message`).
- `store.py` — where state lives: `SqliteStore` (Docker/local) or `FirestoreStore` (Cloud Run, `STORE=firestore`). Both have the same 4 async methods; keep them in sync.
- `rules.json` — keywords/replies; read on every webhook, no restart needed.
- `tests/` — pytest; Instagram API calls are faked via `graph_post` / `graph_get`; `test_store.py` runs the same checks on SQLite and a fake Firestore.
- `scripts/meta.sh` — one-time Meta helpers (find account ID, subscribe webhooks); token read hidden, passed to curl on stdin.
- `deploy.sh`, `.gcloudignore` — Cloud Run deploy (dedicated service account, secrets in Secret Manager). Never run it against the owner's account without being asked.
- `Dockerfile`, `docker-compose.yml`, `Caddyfile` — deploy (Caddy only under `--profile https`, sandboxed cloudflared quick tunnel under `--profile tunnel`).

## Commands
- Test: `pip install -r requirements-dev.txt && pytest -q`
- Run: `docker compose up -d` (needs `.env` from `.env.example`). Cloud: `PROJECT=<id> ./deploy.sh`.
- New source files must be added to the Dockerfile `COPY` line, or the container crashes on import.

## Rules for changes
- Keep the README quick-start short; push detail into `<details>` blocks.
- Every new behaviour needs a test. Never commit `.env`, tokens or `*.db`.
- Always verify `X-Hub-Signature-256`; never log tokens.
- Meta constraints: one private reply per comment (within 7 days); 24h messaging window; system-user token expiry is chosen in the Meta configuration (pick never).
- API is Instagram API with Unified Login (`graph.facebook.com`, system-user token, Meta app secret signs webhooks). Meta's docs only cover private replies for it; the rest is unverified against live Instagram: send-DM endpoint, quick-reply buttons on private replies, `is_user_follow_business` with this token, whether Development mode delivers webhooks. Fallbacks: "any message triggers the follow check", `FOLLOW_CHECK=off`.

## Roadmap (do in order)
1. Live test with real Meta app 2. Comment auto-reply 3. Token auto-refresh 4. Multi-message/buttons/email capture 5. Simple stats page
