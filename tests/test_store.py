import asyncio, os, tempfile, time
os.environ.update(VERIFY_TOKEN="v", APP_SECRET="s", ACCESS_TOKEN="t", IG_USER_ID="ME", DB_FILE=tempfile.mktemp())
import pytest
from google.api_core.exceptions import AlreadyExists
from store import SqliteStore, FirestoreStore, SENT_TTL, PENDING_TTL

class FakeSnap:
    def __init__(self, data): self.data = data; self.exists = data is not None
    def to_dict(self): return self.data

class FakeDoc:
    def __init__(self, docs, key): self.docs, self.key = docs, key
    def create(self, data):
        if self.key in self.docs: raise AlreadyExists("exists")
        self.docs[self.key] = data
    def set(self, data): self.docs[self.key] = data
    def get(self): return FakeSnap(self.docs.get(self.key))
    def delete(self): self.docs.pop(self.key, None)

class FakeFirestore:
    """Just enough of google.cloud.firestore.Client: client.collection(name).document(id)."""
    def __init__(self): self.data = {}
    def collection(self, name):
        docs = self.data.setdefault(name, {})
        return type("Coll", (), {"document": lambda _, key: FakeDoc(docs, key)})()

@pytest.fixture(params=["sqlite", "firestore"])
def store(request):
    return SqliteStore(":memory:") if request.param == "sqlite" else FirestoreStore(client=FakeFirestore())

def run(coro): return asyncio.run(coro)

def test_claim_comment_only_once(store):
    assert run(store.claim_comment("c1", "guide")) is True
    assert run(store.claim_comment("c1", "guide")) is False
    assert run(store.claim_comment("c2", "guide")) is True

def test_pending_roundtrip_and_clear(store):
    assert run(store.get_pending("U1")) is None
    run(store.set_pending("U1", "the reply", "the retry"))
    reply, retry, ts = run(store.get_pending("U1"))
    assert (reply, retry) == ("the reply", "the retry") and abs(ts - time.time()) < 5
    run(store.clear_pending("U1"))
    assert run(store.get_pending("U1")) is None

def test_pending_overwritten_by_newer_comment(store):
    run(store.set_pending("U1", "old", "r")); run(store.set_pending("U1", "new", "r"))
    assert run(store.get_pending("U1"))[0] == "new"

def test_firestore_documents_carry_ttl_field():
    fake = FakeFirestore(); s = FirestoreStore(client=fake)
    run(s.claim_comment("c1", "guide")); run(s.set_pending("U1", "r", "t"))
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    assert 0 < (fake.data["sent"]["c1"]["expires"] - now).total_seconds() <= SENT_TTL
    assert 0 < (fake.data["pending"]["U1"]["expires"] - now).total_seconds() <= PENDING_TTL

def test_unknown_store_setting_fails_loudly():
    import importlib, app
    os.environ["STORE"] = "firestor"
    try:
        with pytest.raises(RuntimeError, match="STORE must be"):
            importlib.reload(app)
    finally:
        del os.environ["STORE"]; importlib.reload(app)
