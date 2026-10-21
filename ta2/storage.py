"""SQLite-backed LangGraph Store, separate from execution checkpoints."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone

from langgraph.store.base import BaseStore, GetOp, PutOp, SearchOp, ListNamespacesOp, Item, SearchItem


class SQLiteStore(BaseStore):
    def __init__(self, path):
        self.connection = sqlite3.connect(str(path), check_same_thread=False, timeout=5)
        self.lock = threading.RLock()
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS ta2_items (namespace TEXT, key TEXT, value TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY(namespace,key))")
        self.connection.commit()

    def close(self):
        self.connection.close()

    def batch(self, ops):
        with self.lock, self.connection:
            return [self._apply(op) for op in ops]

    async def abatch(self, ops):
        # SQLite operations are short and guarded; async callers share this store.
        import asyncio
        return await asyncio.to_thread(self.batch, list(ops))

    def _rows(self):
        rows = self.connection.execute("SELECT namespace,key,value,created,updated FROM ta2_items").fetchall()
        return [Item(namespace=tuple(json.loads(n)), key=k, value=json.loads(v),
                     created_at=datetime.fromisoformat(c), updated_at=datetime.fromisoformat(u))
                for n, k, v, c, u in rows]

    def _apply(self, op):
        if isinstance(op, PutOp):
            if op.ttl is not None:
                raise NotImplementedError("TTL is not supported by this SQLite Store")
            namespace = json.dumps(op.namespace)
            if op.value is None:
                self.connection.execute("DELETE FROM ta2_items WHERE namespace=? AND key=?", (namespace, op.key))
            else:
                now = datetime.now(timezone.utc).isoformat()
                self.connection.execute("INSERT INTO ta2_items VALUES (?,?,?,?,?) ON CONFLICT(namespace,key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
                                        (namespace, op.key, json.dumps(op.value), now, now))
            return None
        if isinstance(op, GetOp):
            return next((r for r in self._rows() if r.namespace == op.namespace and r.key == op.key), None)
        if isinstance(op, SearchOp):
            if op.query is not None:
                raise NotImplementedError("Use Chroma for semantic queries")
            rows = [r for r in self._rows() if r.namespace[:len(op.namespace_prefix)] == op.namespace_prefix
                    and all(r.value.get(k) == v for k, v in (op.filter or {}).items())]
            rows.sort(key=lambda r: (r.namespace, r.key))
            return [SearchItem(namespace=r.namespace, key=r.key, value=r.value,
                               created_at=r.created_at, updated_at=r.updated_at)
                    for r in rows[op.offset:op.offset + op.limit]]
        if isinstance(op, ListNamespacesOp):
            namespaces = set(r.namespace for r in self._rows())
            for condition in op.match_conditions or ():
                p = condition.path
                namespaces = {n for n in namespaces if not p or
                              (n[:len(p)] == p if condition.match_type == "prefix" else n[-len(p):] == p)}
            namespaces = sorted({n[:op.max_depth] if op.max_depth else n for n in namespaces})
            return namespaces[op.offset:op.offset + op.limit]
        raise NotImplementedError(type(op).__name__)
