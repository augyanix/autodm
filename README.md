# autodm

Self-hosted Instagram **comment-to-DM** automation: a free, open-source ManyChat alternative.
Someone comments a keyword on your reel → they get a DM with your link. Optional **"follow me first"** gate to grow followers.

**Cost:** Instagram API is free. Hosting ≈ $0–6/month.

## Quick start

1. **Get your Instagram credentials** (one-time, ~10 min) → [Meta setup](#meta-setup-one-time)
2. **Configure**
   ```bash
   cp .env.example .env     # fill in the 4 values
   ```
3. **Edit `rules.json`** (keywords and replies) → [Rules](#rules)
4. **Run**
   ```bash
   docker compose up -d
   ```
5. **Point Meta's webhook** to `https://YOUR_DOMAIN/webhook` with your `VERIFY_TOKEN`, and subscribe to **comments** and **messages**.

Check it's alive: `curl http://localhost:8000/health` → `{"ok":true}`

## Rules

`rules.json` — edit anytime, no restart needed.

```json
{ "rules": [
  { "keywords": ["guide"], "follow_gate": true, "reply": "Here you go 🎉 https://example.com" }
] }
```

Each rule supports:

| Field | Meaning |
|---|---|
| `keywords` | Comment contains any of these (case-insensitive) |
| `reply` | The DM that delivers your link |
| `follow_gate` | `true` = ask them to follow first, send `reply` only once they do |
| `gate_ask` / `gate_retry` | Optional wording for the follow request / "not following yet" message |
| `media_id` | Optional: only trigger on one specific post or reel |

<details>
<summary><b>How the follow gate works</b></summary>

1. They comment `guide` → we DM: "Follow me first, then tap **I'm following ✅**".
2. They tap the button (or send any message) → we check Instagram's `is_user_follow_business`.
3. Following → we send `reply`. Not yet → we politely ask again (they can retry for 24 h).

</details>

## Meta setup (one-time)

<details>
<summary><b>Step-by-step</b></summary>

1. Switch your Instagram to a **Professional** account (Settings → Account type). It must be **public**, or Instagram sends no comment notifications.
2. Go to [developers.facebook.com](https://developers.facebook.com) (first time: register as a developer) → **My Apps → Create app**.
   - App name must not contain "Instagram", "IG", "Meta" or "FB".
   - Use case: **Manage messaging & content on Instagram** (under the *Content management* filter).
   - Business: skip for now.
3. Create a free **business portfolio** at [business.facebook.com](https://business.facebook.com) (brand-new Facebook accounts may have to wait an hour or more) and turn on two-factor authentication for it. In the app: **Use cases → Customize → API setup with Unified login → + Business portfolio**. New Meta apps only offer *Unified login* (the older *Instagram login* is not available for them).
4. **Create new configuration** and keep the default permissions (`instagram_basic`, `instagram_manage_messages`, `instagram_manage_comments`). Choose **never expires** if offered. **Use this configuration**.
5. **Generate access tokens → Add account** → invite your Instagram as an *Instagram Tester*, accept it on instagram.com (Settings → Website permissions → Apps and websites → Tester invites), then **Generate token**. It is shown once: copy it straight into `.env` (or the hidden prompt of `deploy.sh`).
6. Find your Instagram account ID: `./scripts/meta.sh id` (token entered hidden).
7. Put into `.env`:
   - `ACCESS_TOKEN` = the generated token
   - `IG_USER_ID` = the Instagram account ID from step 6
   - `APP_SECRET` = the **Meta app secret**: App settings → Basic → App secret
   - `VERIFY_TOKEN` = any random string you choose
8. Start the bot (so Meta can reach it), then **Webhooks** (dashboard) → callback URL `https://YOUR_DOMAIN/webhook` and the same verify token → **Verify and save**, and subscribe the account: `./scripts/meta.sh subscribe YOUR_IG_ID`.

Meta's docs say the app must be *Live* to receive notifications for app users but don't say whether your own tester account is enough in *Development* mode; if no webhooks arrive, publish the app (no App Review is needed for your own account).

</details>

<details>
<summary><b>Run it in the cloud instead of your laptop (Google Cloud Run)</b></summary>

Recommended for anything beyond testing: always on, a permanent HTTPS URL, no tunnel, and nothing sensitive on your laptop.

```bash
gcloud auth login
PROJECT=your-autodm-project ./deploy.sh
```

Use a project dedicated to autodm. The script enables the APIs, creates Firestore (the bot's memory; Cloud Run has no disk), stores your tokens in Secret Manager (hidden prompts, never in the repo or your shell history), runs the bot as its own service account that can read only those 3 secrets and use Firestore, and prints the callback URL for Meta's webhook page. Re-run it to redeploy, e.g. after editing `rules.json` (the rules ship inside the image on Cloud Run).

Cost is a few dollars a month for one always-on instance (`--min-instances 1` in `deploy.sh`; set `0` to scale to zero, at the price of a slow first reply after quiet periods).

</details>

<details>
<summary><b>Need a public HTTPS URL? (free, built in)</b></summary>

Point a domain's DNS at your server, set `DOMAIN=yourdomain.com` in `.env`, then:

```bash
docker compose --profile https up -d
```

Caddy gets and renews the certificate automatically.

**Testing from your laptop, no domain:** a sandboxed Cloudflare quick tunnel is built in.

```bash
docker compose --profile tunnel up -d
docker compose logs tunnel | grep trycloudflare.com   # your public URL; changes every run
docker compose stop tunnel                            # close it when you're done
```

</details>

<details>
<summary><b>Security guardrails</b></summary>

- The public URL serves only `/webhook` and `/health`; API docs pages are disabled.
- Every webhook must carry Meta's `X-Hub-Signature-256` signed with your app secret; anything else gets 403. Bodies over 256 KB are refused before processing.
- Port 8000 is published on `127.0.0.1` only, so it isn't reachable from your Wi-Fi/LAN.
- Containers run read-only, as a non-root user (autodm), with all Linux capabilities dropped, no privilege escalation, and memory/process limits.
- The tunnel is outbound-only (no ports opened on your router), runs in its own locked-down container with no access to your files, can only forward to `autodm:8000`, and never restarts on its own.
- Access logs drop query strings, so tokens never land in logs. Keep `.env` private: `chmod 600 .env`.
- CI runs `pip-audit`; Dependabot proposes weekly updates for Python packages, images and Actions.

</details>

<details>
<summary><b>Limits & good to know</b></summary>

- One private reply per comment, within 7 days of the comment.
- Choose "never expires" when creating the Meta configuration. If you picked an expiry, generate a new token before it lapses and restart (`docker compose up -d`), or on Cloud Run add a new version of the `autodm-access-token` secret and re-run `./deploy.sh`.
- The token stops working if the app is removed from the business portfolio or the Instagram account moves to another one.
- Not yet verified live: the follow check (`is_user_follow_business`) with this token type. If Meta refuses it the logs say so; set `FOLLOW_CHECK=off` to deliver the reply when they tap the button.
- Replies are sent via Meta's official API, so there is no ban risk from scraping.
- Data (who was already replied to) lives in a Docker volume named `autodm-data`, or in Firestore on Cloud Run (`STORE=firestore`; records expire on their own).

</details>

<details>
<summary><b>Development</b></summary>

```bash
pip install -r requirements-dev.txt
pytest
```

</details>

## Roadmap
- [x] Keyword → DM
- [x] Follow-me-first gate
- [x] Docker + optional HTTPS
- [ ] Auto-reply to the comment itself
- [ ] Token auto-refresh
- [ ] Multiple messages / buttons / email capture
- [ ] Simple stats page

## Contributing & security
PRs welcome. Report vulnerabilities privately, see [SECURITY.md](SECURITY.md). Licensed under [MIT](LICENSE).
Not affiliated with Meta or ManyChat.
