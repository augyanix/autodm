#!/usr/bin/env bash
# Deploy autodm to Google Cloud Run. Safe to re-run. Use a dedicated Google Cloud project for autodm.
#   PROJECT=my-autodm-project ./deploy.sh
# First run asks for your Instagram values (hidden input) and stores the secrets in Secret Manager.
set -euo pipefail
PROJECT=${PROJECT:?Set PROJECT to your Google Cloud project ID}
REGION=${REGION:-asia-south1}
SERVICE=autodm
SA_NAME=autodm-run
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
SECRETS=(autodm-access-token autodm-app-secret autodm-verify-token)

gcloud config set project "$PROJECT" >/dev/null
echo "Enabling APIs (first time takes a minute)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firestore.googleapis.com secretmanager.googleapis.com >/dev/null

if ! gcloud firestore databases describe --database="(default)" >/dev/null 2>&1; then
  echo "Creating Firestore..."
  gcloud firestore databases create --location="$REGION" >/dev/null
fi
# Old records delete themselves (the app stamps each document with an `expires` time).
for c in sent pending; do
  gcloud firestore fields ttls update expires --collection-group="$c" --enable-ttl --async >/dev/null 2>&1 || true
done

# Dedicated identity: it can read only these 3 secrets and use Firestore. Nothing else in the project.
if ! gcloud iam service-accounts describe "$SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --display-name="autodm runtime" >/dev/null
fi
gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" \
  --role=roles/datastore.user --condition=None >/dev/null

ask_secret() {   # name, prompt, [value]  (input is hidden and never echoed or logged)
  local name=$1 prompt=$2 val=${3:-}
  if ! gcloud secrets describe "$name" >/dev/null 2>&1; then
    [ -n "$val" ] || { read -rsp "$prompt (hidden): " val; echo; }
    # Drop invisible bytes a paste can add (bracketed-paste codes, newlines, spaces).
    val=${val//$'\e[200~'/}; val=${val//$'\e[201~'/}; val=$(printf %s "$val" | tr -d '[:space:][:cntrl:]')
    [ -n "$val" ] || { echo "Nothing entered for $name." >&2; exit 1; }
    printf %s "$val" | gcloud secrets create "$name" --data-file=- >/dev/null
    unset val
  fi
  gcloud secrets add-iam-policy-binding "$name" --member="serviceAccount:$SA" \
    --role=roles/secretmanager.secretAccessor >/dev/null
}
# The token saved by ./scripts/meta.sh exchange is reused straight from the macOS Keychain.
KC_TOKEN=$(security find-generic-password -s autodm-meta-token -w 2>/dev/null || true)
ask_secret autodm-access-token "ACCESS_TOKEN (the token generated in the Meta dashboard)" "$KC_TOKEN"
unset KC_TOKEN
ask_secret autodm-app-secret   "APP_SECRET (Meta app secret: App settings > Basic)"
# Verify token: a strong random string we generate; Meta only needs the same value pasted in its webhook form.
if ! gcloud secrets describe autodm-verify-token >/dev/null 2>&1; then
  ask_secret autodm-verify-token "" "$(openssl rand -hex 24)"
else
  ask_secret autodm-verify-token ""
fi

if [ -z "${IG_USER_ID:-}" ]; then read -rp "Instagram account ID (IG_USER_ID, from ./scripts/meta.sh id; not a secret): " IG_USER_ID; fi

echo "Building and deploying..."
gcloud run deploy "$SERVICE" --source . --region "$REGION" --service-account "$SA" --allow-unauthenticated \
  --port 8000 --memory 256Mi --cpu 1 --concurrency 40 --min-instances 1 --max-instances 2 \
  --set-secrets "ACCESS_TOKEN=autodm-access-token:latest,APP_SECRET=autodm-app-secret:latest,VERIFY_TOKEN=autodm-verify-token:latest" \
  --set-env-vars "STORE=firestore,GOOGLE_CLOUD_PROJECT=$PROJECT,IG_USER_ID=$IG_USER_ID" --quiet

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')
echo
echo "Live at: $URL"
curl -s "$URL/health" && echo "  <- health check"
echo "Meta webhook callback URL: $URL/webhook"
echo "Meta webhook verify token: $(gcloud secrets versions access latest --secret=autodm-verify-token)"
echo "  (paste both values into Meta: Use cases > Customize > API setup with Unified login > Configure webhooks)"
