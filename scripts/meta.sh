#!/usr/bin/env bash
# One-time Meta setup helpers (Instagram API with Unified Login).
#   ./scripts/meta.sh id                  list the Instagram account ID(s) your token can use
#   ./scripts/meta.sh check IG_ID         confirm the token can read that Instagram account
#   ./scripts/meta.sh subscribe IG_ID     subscribe the app to that account's comments + messages webhooks
# The token is read with hidden input (or from $ACCESS_TOKEN) and handed to curl on stdin, so it never
# shows up in your shell history or in the process list.
set -euo pipefail
API=${GRAPH_BASE:-https://graph.facebook.com/v26.0}
cmd=${1:-}

if [ -z "${ACCESS_TOKEN:-}" ]; then read -rsp "ACCESS_TOKEN (hidden): " ACCESS_TOKEN; echo; fi
# Pasting can add invisible bytes (terminal bracketed-paste codes, newlines, spaces) that make Meta
# reject the whole request. Tokens are plain letters/digits, so drop everything else.
ACCESS_TOKEN=${ACCESS_TOKEN//$'\e[200~'/}; ACCESS_TOKEN=${ACCESS_TOKEN//$'\e[201~'/}
ACCESS_TOKEN=$(printf %s "$ACCESS_TOKEN" | tr -cd 'A-Za-z0-9._|-')
[ -n "$ACCESS_TOKEN" ] || { echo "No token entered." >&2; exit 1; }
echo "Token: ${#ACCESS_TOKEN} characters, starts with ${ACCESS_TOKEN:0:3}" >&2

case "$cmd" in
  id)
    printf 'header = "Authorization: Bearer %s"\n' "$ACCESS_TOKEN" |
      curl -sS -K - -w '\nHTTP %{http_code}\n' "$API/me/assigned_instagram_accounts?fields=id,username"
    ;;
  check)
    IG_ID=${2:?usage: meta.sh check IG_ID}
    printf 'header = "Authorization: Bearer %s"\n' "$ACCESS_TOKEN" |
      curl -sS -K - -w '\nHTTP %{http_code}\n' "$API/$IG_ID?fields=id,username"
    ;;
  subscribe)
    IG_ID=${2:?usage: meta.sh subscribe IG_ID}
    printf 'data-urlencode = "access_token=%s"\ndata-urlencode = "subscribed_fields=comments,messages"\n' "$ACCESS_TOKEN" |
      curl -sS -K - -w '\nHTTP %{http_code}\n' -X POST "$API/$IG_ID/subscribed_apps"
    ;;
  *)
    echo "usage: $0 id | check IG_ID | subscribe IG_ID" >&2; exit 2
    ;;
esac
