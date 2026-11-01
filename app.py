"""autodm - self-hosted Instagram comment-to-DM bot with an optional "follow me first" gate."""
import hashlib, hmac, json, logging, os, time
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from store import PENDING_TTL, FirestoreStore, SqliteStore

def env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise RuntimeError(f"Missing required setting {name}. Copy .env.example to .env and fill it in.")
    return val

VERIFY_TOKEN = env("VERIFY_TOKEN")
APP_SECRET = env("APP_SECRET")
ACCESS_TOKEN = env("ACCESS_TOKEN")
IG_USER_ID = env("IG_USER_ID")
API = env("GRAPH_BASE", "https://graph.facebook.com/v26.0")    # Instagram API with Unified Login
RULES_FILE = env("RULES_FILE", "rules.json")
DB_FILE = env("DB_FILE", "autodm.db")
STORE = env("STORE", "sqlite")      # "firestore" on Cloud Run (no disk there)
FOLLOW_CHECK = env("FOLLOW_CHECK", "on")   # "off": trust that they followed (use if Meta refuses the follow lookup)
CHECK_PAYLOAD = "FOLLOW_CHECK"
MAX_BODY = 256 * 1024            # Meta webhooks are a few KB; refuse anything big before buffering it

class DropQuery(logging.Filter):
    """Access logs must not contain query strings: Meta's handshake puts hub.verify_token there."""
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            args = list(record.args); args[2] = str(args[2]).split("?", 1)[0]; record.args = tuple(args)
        return True
logging.getLogger("uvicorn.access").addFilter(DropQuery())

# No /docs, /redoc or /openapi.json: nothing on the public URL except the webhook and health check.
app = FastAPI(title="autodm", docs_url=None, redoc_url=None, openapi_url=None)
if STORE not in ("sqlite", "firestore"):
    raise RuntimeError(f"STORE must be 'sqlite' or 'firestore', not {STORE!r}")
store = (FirestoreStore(os.environ.get("GOOGLE_CLOUD_PROJECT"), env("FIRESTORE_DATABASE", "(default)"))
         if STORE == "firestore" else SqliteStore(DB_FILE))

# ---- Instagram API helpers (kept tiny so tests can replace them) -------------------------------
log = logging.getLogger("autodm")

def log_api_error(what: str, r: httpx.Response):
    """Say why Meta refused (its error text never contains our token), so a live test is debuggable."""
    try:
        err = r.json().get("error", {})
    except ValueError:
        err = {}
    log.warning("Instagram API %s failed: HTTP %s, code %s: %s", what, r.status_code, err.get("code"), err.get("message", ""))

async def graph_post(path: str, payload: dict) -> int:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{API}/{path}", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}, json=payload)
    if r.status_code >= 300:
        log_api_error("send", r)
    return r.status_code

async def graph_get(path: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API}/{path}", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}, params=params)
    if r.status_code != 200:
        log_api_error("lookup", r)
        return {}
    return r.json()

def check_button(label="I'm following ✅"):
    return [{"content_type": "text", "title": label, "payload": CHECK_PAYLOAD}]

# ---- webhook endpoints --------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/webhook")
def verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and hmac.compare_digest(q.get("hub.verify_token", ""), VERIFY_TOKEN):
        return Response(q.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403)

@app.post("/webhook")
async def webhook(request: Request):
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY:
            raise HTTPException(413)
    expected = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get("x-hub-signature-256", ""), expected):
        raise HTTPException(403, "bad signature")
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(400)
    with open(RULES_FILE) as f:
        rules = json.load(f)["rules"]
    for entry in payload.get("entry", []):
        for ch in entry.get("changes", []):
            if ch.get("field") == "comments":
                v = ch["value"]
                if v.get("from", {}).get("id") != IG_USER_ID:
                    # Unified Login sends comment_id; the older Instagram-login shape used id
                    await on_comment(v.get("comment_id") or v["id"], v["from"]["id"], v.get("text", ""),
                                     v.get("media", {}).get("id"), rules)
        for m in entry.get("messaging", []):
            await on_message(m)
    return {"ok": True}

# ---- logic --------------------------------------------------------------------------------------
async def on_comment(comment_id, user_id, text, media_id, rules):
    for r in rules:
        if r.get("media_id") and r["media_id"] != media_id:
            continue
        kw = next((k for k in r["keywords"] if k.lower() in text.lower()), None)
        if not kw:
            continue
        if not await store.claim_comment(comment_id, kw):   # Meta allows only one private reply per comment
            return
        if r.get("follow_gate"):
            retry = r.get("gate_retry", "Looks like you're not following yet. Follow me, then tap the button 👇")
            await store.set_pending(user_id, r["reply"], retry)
            message = {"text": r.get("gate_ask", "Follow me first, then tap the button below 👇"), "quick_replies": check_button()}
        else:
            message = {"text": r["reply"]}
        await graph_post(f"{IG_USER_ID}/messages", {"recipient": {"comment_id": comment_id}, "message": message})
        return

async def on_message(m):
    user_id = m.get("sender", {}).get("id")
    msg = m.get("message")
    if not msg or msg.get("is_echo") or user_id == IG_USER_ID:
        return
    row = await store.get_pending(user_id)
    if not row or time.time() - row[2] > PENDING_TTL:
        return
    reply, retry, _ = row
    if FOLLOW_CHECK == "off":
        following = True
    else:
        following = (await graph_get(user_id, {"fields": "is_user_follow_business"})).get("is_user_follow_business")
        if following is None:
            log.warning("Could not tell whether a user follows us; set FOLLOW_CHECK=off to skip the check")
    if following:
        await store.clear_pending(user_id)
        await graph_post(f"{IG_USER_ID}/messages", {"recipient": {"id": user_id}, "message": {"text": reply}})
    else:
        await graph_post(f"{IG_USER_ID}/messages",
                         {"recipient": {"id": user_id}, "message": {"text": retry, "quick_replies": check_button("Check again ✅")}})
