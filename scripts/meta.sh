#!/usr/bin/env bash
# One-time Meta setup helpers (Instagram API with Unified Login).
#   ./scripts/meta.sh exchange            turn the Login URL's ?code=... into the Business Integration token (copied to clipboard)
#   ./scripts/meta.sh id                  list the Instagram account ID(s) your token can use
#   ./scripts/meta.sh debug               show the token type, permissions and the account IDs they cover
#   ./scripts/meta.sh check IG_ID         confirm the token can read that Instagram account
#   ./scripts/meta.sh subscribe IG_ID     subscribe the app to that account's comments + messages webhooks
# Secrets are read with hidden input (or from env vars) and handed to curl on stdin, so they never
# show up in your shell history, the process list, or the terminal output.
set -euo pipefail
API=${GRAPH_BASE:-https://graph.facebook.com/v26.0}
cmd=${1:-}

# Pasting can add invisible bytes (terminal bracketed-paste codes, newlines, spaces) that make Meta
# reject the whole request, so strip them from anything pasted.
clean() { local v=${1//$'\e[200~'/}; v=${v//$'\e[201~'/}; printf %s "$v" | tr -d '[:space:][:cntrl:]'; }

read_token() {
  if [ -z "${ACCESS_TOKEN:-}" ]; then read -rsp "ACCESS_TOKEN (hidden): " ACCESS_TOKEN; echo; fi
  ACCESS_TOKEN=$(clean "$ACCESS_TOKEN" | tr -cd 'A-Za-z0-9._|-')
  [ -n "$ACCESS_TOKEN" ] || { echo "No token entered." >&2; exit 1; }
  echo "Token: ${#ACCESS_TOKEN} characters, starts with ${ACCESS_TOKEN:0:3}" >&2
}

read_app() {   # App ID + app secret: App settings > Basic
  APP_ID=${APP_ID:-}; [ -n "$APP_ID" ] || read -rp "App ID (App settings > Basic, not secret): " APP_ID
  APP_SECRET=${APP_SECRET:-}; [ -n "$APP_SECRET" ] || { read -rsp "APP_SECRET (hidden): " APP_SECRET; echo; }
  APP_ID=$(printf %s "$APP_ID" | tr -cd '0-9'); APP_SECRET=$(clean "$APP_SECRET")
}

case "$cmd" in
  exchange)
    read_app
    REDIRECT_URI=${REDIRECT_URI:-https://github.com/augyanix/autodm}   # must match the Redirect URL saved in the dashboard
    read -rsp "Paste the whole address-bar URL you landed on after logging in (hidden): " LANDED; echo
    LANDED=$(clean "$LANDED"); CODE=${LANDED#*code=}; CODE=${CODE%%&*}; CODE=${CODE%%#*}
    [ -n "$CODE" ] && [ "$CODE" != "$LANDED" ] || { echo "No ?code= found in that URL." >&2; exit 1; }
    RESP=$(printf 'data-urlencode = "client_id=%s"\ndata-urlencode = "client_secret=%s"\ndata-urlencode = "redirect_uri=%s"\ndata-urlencode = "code=%s"\n' \
             "$APP_ID" "$APP_SECRET" "$REDIRECT_URI" "$CODE" | curl -sS -K - -G "$API/oauth/access_token")
    # Never print the token: copy it to the clipboard and show only harmless details.
    printf %s "$RESP" | python3 -I -c '
import json, subprocess, sys
d = json.load(sys.stdin)
tok = d.pop("access_token", None)
if not tok:
    print(json.dumps(d)); sys.exit(1)
subprocess.run(["pbcopy"], input=tok.encode(), check=True)
print(f"Token copied to clipboard ({len(tok)} characters, starts with {tok[:3]}). Other fields: {json.dumps(d)}")
print("Paste it into Passwords now, then copy something else to clear the clipboard.")'
    ;;
  id)
    read_token
    printf 'header = "Authorization: Bearer %s"\n' "$ACCESS_TOKEN" |
      curl -sS -K - -w '\nHTTP %{http_code}\n' "$API/me/assigned_instagram_accounts?fields=id,username"
    ;;
  debug)
    # Business (system-user) tokens can only be inspected with the app's own credentials (App ID + app secret).
    read_token; read_app
    printf 'data-urlencode = "input_token=%s"\ndata-urlencode = "access_token=%s|%s"\n' "$ACCESS_TOKEN" "$APP_ID" "$APP_SECRET" |
      curl -sS -K - -G -w '\nHTTP %{http_code}\n' "$API/debug_token"
    ;;
  check)
    IG_ID=${2:?usage: meta.sh check IG_ID}; read_token
    printf 'header = "Authorization: Bearer %s"\n' "$ACCESS_TOKEN" |
      curl -sS -K - -w '\nHTTP %{http_code}\n' "$API/$IG_ID?fields=id,username"
    ;;
  subscribe)
    IG_ID=${2:?usage: meta.sh subscribe IG_ID}; read_token
    printf 'data-urlencode = "access_token=%s"\ndata-urlencode = "subscribed_fields=comments,messages"\n' "$ACCESS_TOKEN" |
      curl -sS -K - -w '\nHTTP %{http_code}\n' -X POST "$API/$IG_ID/subscribed_apps"
    ;;
  *)
    echo "usage: $0 exchange | id | debug | check IG_ID | subscribe IG_ID" >&2; exit 2
    ;;
esac
