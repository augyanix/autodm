"""Where autodm remembers things: SQLite (local/Docker) or Firestore (Cloud Run, which has no disk).

Two facts are stored: which comments we already answered (Meta allows one private reply per comment)
and which people are waiting on the follow check. Pick the backend with STORE=sqlite|firestore.
"""
import asyncio, sqlite3, time
from datetime import datetime, timedelta, timezone

SENT_TTL = 8 * 24 * 3600         # private replies only work within 7 days of the comment
PENDING_TTL = 24 * 3600          # Meta only lets us message a user for 24h after their last message

class SqliteStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("create table if not exists sent(comment_id text primary key, ts real, keyword text)")
        self.db.execute("create table if not exists pending(user_id text primary key, reply text, retry text, ts real)")

    async def claim_comment(self, comment_id, keyword) -> bool:
        """True if this is the first time we see the comment, False if we already answered it."""
        try:
            self.db.execute("insert into sent values (?,?,?)", (comment_id, time.time(), keyword)); self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    async def set_pending(self, user_id, reply, retry):
        self.db.execute("insert or replace into pending values (?,?,?,?)", (user_id, reply, retry, time.time())); self.db.commit()

    async def get_pending(self, user_id):
        """(reply, retry, ts) or None."""
        return self.db.execute("select reply, retry, ts from pending where user_id=?", (user_id,)).fetchone()

    async def clear_pending(self, user_id):
        self.db.execute("delete from pending where user_id=?", (user_id,)); self.db.commit()


class FirestoreStore:
    """Documents carry an `expires` timestamp; enable a Firestore TTL policy on that field to auto-delete them."""
    def __init__(self, project=None, database="(default)", client=None):
        if client is None:
            from google.cloud import firestore
            client = firestore.Client(project=project, database=database)
        self.client = client

    @staticmethod
    def _expires(seconds):
        return datetime.now(timezone.utc) + timedelta(seconds=seconds)

    async def claim_comment(self, comment_id, keyword) -> bool:
        from google.api_core.exceptions import AlreadyExists
        def create():
            try:                                    # create() fails if the document exists: atomic across instances
                self.client.collection("sent").document(comment_id).create(
                    {"ts": time.time(), "keyword": keyword, "expires": self._expires(SENT_TTL)})
                return True
            except AlreadyExists:
                return False
        return await asyncio.to_thread(create)

    async def set_pending(self, user_id, reply, retry):
        await asyncio.to_thread(self.client.collection("pending").document(user_id).set,
                                {"reply": reply, "retry": retry, "ts": time.time(), "expires": self._expires(PENDING_TTL)})

    async def get_pending(self, user_id):
        snap = await asyncio.to_thread(self.client.collection("pending").document(user_id).get)
        if not snap.exists:
            return None
        d = snap.to_dict()
        return d["reply"], d["retry"], d["ts"]

    async def clear_pending(self, user_id):
        await asyncio.to_thread(self.client.collection("pending").document(user_id).delete)
