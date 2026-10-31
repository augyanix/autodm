"""autodm - self-hosted Instagram comment-to-DM bot with an optional "follow me first" gate."""
import hashlib, hmac, json, os, sqlite3, time
import httpx
from fastapi import FastAPI, HTTPException, Request, Response

def env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise RuntimeError(f"Missing required setting {name}. Copy .env.example to .env and fill it in.")
    return val

VERIFY_TOKEN = env("VERIFY_TOKEN")
APP_SECRET = env("APP_SECRET")
ACCESS_TOKEN = env("ACCESS_TOKEN")
IG_USER_ID = env("IG_USER_ID")
API = env("GRAPH_BASE", "https://graph.instagram.com/v21.0")
RULES_FILE = env("RULES_FILE", "rules.json")
DB_FILE = env("DB_FILE", "autodm.db")
PENDING_TTL = 24 * 3600          # Meta only lets us message a user for 24h after their last message
CHECK_PAYLOAD = "FOLLOW_CHECK"

app = FastAPI(title="autodm")
db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.execute("create table if not exists sent(comment_id text primary key, ts real, keyword text)")
db.execute("create table if not exists pending(user_id text primary key, reply text, retry text, ts real)")

# ---- Instagram API helpers (kept tiny so tests can replace them) -------------------------------
async def graph_post(path: str, payload: dict) -> int:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f"{API}/{path}", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}, json=payload)
    return r.status_code

async def graph_get(path: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{API}/{path}", headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}, params=params)
    return r.json() if r.status_code == 200 else {}

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
    body = await request.body()
    expected = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get("x-hub-signature-256", ""), expected):
        raise HTTPException(403, "bad signature")
    with open(RULES_FILE) as f:
        rules = json.load(f)["rules"]
    for entry in json.loads(body).get("entry", []):
        for ch in entry.get("changes", []):
            if ch.get("field") == "comments":
                v = ch["value"]
                if v.get("from", {}).get("id") != IG_USER_ID:
                    await on_comment(v["id"], v["from"]["id"], v.get("text", ""), v.get("media", {}).get("id"), rules)
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
        try:                                        # Meta allows only one private reply per comment
            db.execute("insert into sent values (?,?,?)", (comment_id, time.time(), kw)); db.commit()
        except sqlite3.IntegrityError:
            return
        if r.get("follow_gate"):
            retry = r.get("gate_retry", "Looks like you're not following yet. Follow me, then tap the button 👇")
            db.execute("insert or replace into pending values (?,?,?,?)", (user_id, r["reply"], retry, time.time())); db.commit()
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
    row = db.execute("select reply, retry, ts from pending where user_id=?", (user_id,)).fetchone()
    if not row or time.time() - row[2] > PENDING_TTL:
        return
    reply, retry, _ = row
    info = await graph_get(user_id, {"fields": "is_user_follow_business"})
    if info.get("is_user_follow_business"):
        db.execute("delete from pending where user_id=?", (user_id,)); db.commit()
        await graph_post(f"{IG_USER_ID}/messages", {"recipient": {"id": user_id}, "message": {"text": reply}})
    else:
        await graph_post(f"{IG_USER_ID}/messages",
                         {"recipient": {"id": user_id}, "message": {"text": retry, "quick_replies": check_button("Check again ✅")}})
