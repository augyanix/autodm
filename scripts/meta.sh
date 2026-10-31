#!/usr/bin/env bash
# One-time Meta setup helpers (Instagram API with Unified Login).
#   ./scripts/meta.sh id                  list the Instagram account ID(s) your token can use
#   ./scripts/meta.sh subscribe IG_ID     subscribe the app to that account's comments + messages webhooks
# The token is read with hidden input (or from $ACCESS_TOKEN) and handed to curl on stdin, so it never
# shows up in your shell history or in the process list.
set -euo pipefail
API=${GRAPH_BASE:-https://graph.facebook.com/v26.0}
cmd=${1:-}

if [ -z "${ACCESS_TOKEN:-}" ]; then read -rsp "ACCESS_TOKEN (hidden): " ACCESS_TOKEN; echo; fi

case "$cmd" in
  id)
    printf 'header = "Authorization: Bearer %s"\n' "$ACCESS_TOKEN" |
      curl -sS -K - "$API/me/assigned_instagram_accounts?fields=id,username"; echo
    ;;
  subscribe)
    IG_ID=${2:?usage: meta.sh subscribe IG_ID}
    printf 'data-urlencode = "access_token=%s"\ndata-urlencode = "subscribed_fields=comments,messages"\n' "$ACCESS_TOKEN" |
      curl -sS -K - -X POST "$API/$IG_ID/subscribed_apps"; echo
    ;;
  *)
    echo "usage: $0 id | subscribe IG_ID" >&2; exit 2
    ;;
esac
