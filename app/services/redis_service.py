# In-memory store — replaces Redis for anti-cheat flagging
_store: dict[str, str] = {}


class _InMemoryStore:
    def set(self, key: str, value: str):
        _store[key] = value

    def get(self, key: str) -> str | None:
        return _store.get(key)


redis_client = _InMemoryStore()
