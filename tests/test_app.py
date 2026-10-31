import hashlib, hmac, json, os, tempfile
os.environ.update(VERIFY_TOKEN="v", APP_SECRET="s", ACCESS_TOKEN="t", IG_USER_ID="ME",
                  DB_FILE=tempfile.mktemp(), RULES_FILE=os.path.join(os.path.dirname(__file__), "..", "rules.json"))
import pytest
from fastapi.testclient import TestClient
import app as a

client = TestClient(a.app)
sent, follows = [], {"U1": False}

@pytest.fixture(autouse=True)
def fake_graph(monkeypatch):
    sent.clear()
    async def post(path, payload): sent.append(payload); return 200
    async def get(path, params): return {"is_user_follow_business": follows[path]}
    monkeypatch.setattr(a, "graph_post", post); monkeypatch.setattr(a, "graph_get", get)

def post(payload, sig=None):
    body = json.dumps(payload).encode()
    sig = sig or "sha256=" + hmac.new(b"s", body, hashlib.sha256).hexdigest()
    return client.post("/webhook", content=body, headers={"x-hub-signature-256": sig})

def comment(cid, text, user="U1"):
    return {"entry": [{"changes": [{"field": "comments", "value": {"id": cid, "text": text, "from": {"id": user}, "media": {"id": "M"}}}]}]}

def dm(user="U1"):
    return {"entry": [{"messaging": [{"sender": {"id": user}, "message": {"text": "done"}}]}]}

def test_verify_handshake():
    assert client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "v", "hub.challenge": "42"}).text == "42"
    assert client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "42"}).status_code == 403

def test_bad_signature_rejected():
    assert post(comment("c0", "link"), sig="sha256=bad").status_code == 403

def test_api_docs_not_exposed():
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404

def test_oversized_body_rejected_before_signature_check():
    assert post({"pad": "x" * (a.MAX_BODY + 1)}).status_code == 413

def test_malformed_json_with_valid_signature_is_400():
    body = b"not json"
    sig = "sha256=" + hmac.new(b"s", body, hashlib.sha256).hexdigest()
    assert client.post("/webhook", content=body, headers={"x-hub-signature-256": sig}).status_code == 400

def test_access_log_drops_query_string():
    import logging
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("1.2.3.4", "GET", "/webhook?hub.verify_token=v&hub.challenge=1", "1.1", 200), None)
    a.DropQuery().filter(rec)
    assert "verify_token" not in rec.getMessage() and "/webhook" in rec.getMessage()

def test_plain_keyword_sends_reply_once():
    post(comment("c1", "send LINK pls")); post(comment("c1", "send LINK pls"))
    assert len(sent) == 1 and "example.com" in sent[0]["message"]["text"]

def test_no_keyword_no_reply():
    post(comment("c2", "nice reel")); assert sent == []

def test_follow_gate_flow():
    post(comment("c3", "guide")); assert "quick_replies" in sent[0]["message"]
    post(dm()); assert "quick_replies" in sent[1]["message"]
    follows["U1"] = True
    post(dm()); assert "example.com/guide" in sent[2]["message"]["text"]
    post(dm()); assert len(sent) == 3
