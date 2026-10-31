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
{ "keywords": ["guide"], "follow_gate": true, "reply": "Here you go 🎉 https://example.com" }
```

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

1. Switch your Instagram to a **Professional** account (Settings → Account type).
2. Go to [developers.facebook.com](https://developers.facebook.com) → **Create app** → add the **Instagram** product (*API setup with Instagram login*).
3. Add your Instagram account, then **Generate token** with permissions: `instagram_business_basic`, `instagram_business_manage_comments`, `instagram_business_manage_messages`.
4. Put into `.env`:
   - `ACCESS_TOKEN` = the generated token
   - `IG_USER_ID` = your Instagram account ID (shown next to the token)
   - `APP_SECRET` = App settings → Basic → App secret
   - `VERIFY_TOKEN` = any random string you choose
5. **Webhooks** → set callback URL `https://YOUR_DOMAIN/webhook` and the same verify token → subscribe to `comments` and `messages`.

No App Review is needed while the app stays in *Development* mode and the account is yours.

</details>

<details>
<summary><b>Need a public HTTPS URL? (free, built in)</b></summary>

Point a domain's DNS at your server, set `DOMAIN=yourdomain.com` in `.env`, then:

```bash
docker compose --profile https up -d
```

Caddy gets and renews the certificate automatically. For local testing you can use any tunnel (e.g. Cloudflare Tunnel).

</details>

<details>
<summary><b>Limits & good to know</b></summary>

- One private reply per comment, within 7 days of the comment.
- Access tokens expire after ~60 days; generate a new one and restart (`docker compose up -d`). Auto-refresh is on the roadmap.
- Replies are sent via Meta's official API, so there is no ban risk from scraping.
- Data (who was already replied to) lives in a Docker volume named `autodm-data`.

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
